"""
src/core/session.py - 会话状态管理
功能: 管理单个用户的对话会话，包含管线各阶段的状态机、
      音频帧缓冲、转录文本、LLM上下文等功能。
      对应工单需求: "多并发支持: 能够同时支持多个用户的交互"
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import uuid
import time
import asyncio
from enum import Enum
from dataclasses import dataclass, field
from collections import deque
import logging

logger = logging.getLogger(__name__)


class SessionState(Enum):
    """会话状态枚举，对应数字人对话生命周期。"""
    IDLE = "idle"                # 空闲，等待用户输入
    LISTENING = "listening"      # 正在监听/接收语音
    THINKING = "thinking"        # 正在处理(ASR+LLM生成)
    SPEAKING = "speaking"        # 正在播放TTS+唇形同步
    INTERRUPTED = "interrupted"  # 被用户打断


@dataclass
class Session:
    """
    单个用户会话，包含完整的对话状态和管线缓冲。

    对应工单需求:
      - "数字人应能够实时接收用户的语音输入"
      - "数字人应能够自然地被打断，并在中断后恢复对话"
    """
    session_id: str                            # 会话唯一ID
    state: SessionState = SessionState.IDLE     # 当前状态
    created_at: float = field(default_factory=time.time)  # 创建时间戳
    last_active: float = field(default_factory=time.time)  # 最后活跃时间

    # 音频缓冲 — PCM float32队列 (maxlen=30s@16kHz防止内存泄漏)
    audio_buffer: deque = field(default_factory=lambda: deque(maxlen=480000))
    # 转录文本缓冲
    transcript: str = ""                        # 当前识别到的用户输入文本
    # LLM对话历史 (最多保留20轮)
    chat_history: list = field(default_factory=list)
    # TTS生成的音频数据 (PCM bytes队列)
    tts_audio_queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=50))
    # 唇形同步帧队列
    video_frame_queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=30))

    # TTS音频缓存 (最后一次生成的音频，前端通过API获取播放)
    last_tts_audio: any = None                  # numpy数组或None
    # 视频帧缓冲 (用于MJPEG流式推送到前端，最多保留最近60帧)
    video_frame_buffer: deque = field(default_factory=lambda: deque(maxlen=60))

    # 打断标志
    interrupt_flag: bool = False                # 是否收到打断信号
    # 空闲计时
    silence_start: float = 0.0                  # 静音开始时间戳
    is_silent: bool = True                      # 当前是否静音

    # 会话设置 (可运行时通过API修改)
    language: str = "zh-CN"                     # 对话语言
    scenario: str = "default"                   # 对话场景
    voice: str = "zh-CN-XiaoxiaoNeural"         # TTS语音角色
    custom_system_prompt: str = ""              # 自定义系统提示词(空则使用默认)

    # 性能统计(per-session)
    total_turns: int = 0                        # 总对话轮次
    interrupt_count: int = 0                    # 被打断次数
    last_ttff_ms: float = 0.0                   # 最近一次首帧延迟(ms)
    last_total_ms: float = 0.0                  # 最近一次端到端延迟(ms)

    def mark_active(self) -> None:
        """更新最后活跃时间(收到用户输入时调用)。"""
        self.last_active = time.time()

    def is_expired(self, timeout_s: int = 300) -> bool:
        """判断会话是否超时（默认300秒无活动）。"""
        return (time.time() - self.last_active) > timeout_s

    def add_chat_message(self, role: str, content: str) -> None:
        """
        添加一条消息到对话历史。

        参数:
            role: "user" 或 "assistant"
            content: 消息文本内容
        """
        self.chat_history.append({"role": role, "content": content})
        # 保留最近20轮对话，防止上下文过长
        if len(self.chat_history) > 40:  # 20轮 = 40条消息(user+assistant)
            self.chat_history = self.chat_history[-40:]

    def trigger_interrupt(self) -> None:
        """触发打断信号，停止当前TTS播放。"""
        logger.info(f"会话 {self.session_id[:8]} 触发打断")
        self.interrupt_flag = True
        self.interrupt_count += 1
        self.state = SessionState.INTERRUPTED
        # 清空TTS音频队列
        while not self.tts_audio_queue.empty():
            try:
                self.tts_audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    def reset_interrupt(self) -> None:
        """重置打断标志，准备下一轮对话。"""
        self.interrupt_flag = False

    def start_listening(self) -> None:
        """开始监听用户语音。"""
        self.state = SessionState.LISTENING
        self.transcript = ""
        self.mark_active()

    def start_thinking(self) -> None:
        """进入思考状态(ASR/LLM处理中)。"""
        self.state = SessionState.THINKING

    def start_speaking(self) -> None:
        """开始播放TTS+唇形同步。"""
        self.state = SessionState.SPEAKING

    def go_idle(self) -> None:
        """回到空闲状态。"""
        self.state = SessionState.IDLE


class SessionManager:
    """
    会话管理器，负责会话的创建、销毁和并发控制。
    对应工单需求: "多并发支持" — 通过 max_concurrent 控制最大并行会话数。
    """

    def __init__(self, max_concurrent: int = 3, timeout_s: int = 300):
        """初始化会话管理器。"""
        self._sessions: dict[str, Session] = {}  # session_id → Session
        self.max_concurrent = max_concurrent      # 最大并发数
        self.timeout_s = timeout_s                # 超时时间(秒)

    def create_session(self) -> Session:
        """
        创建新会话。
        如果超过最大并发数，抛出 RuntimeError。
        """
        if len(self._sessions) >= self.max_concurrent:
            raise RuntimeError(
                f"已达到最大并发会话数 ({self.max_concurrent})，请稍后再试"
            )
        session_id = str(uuid.uuid4())
        session = Session(session_id=session_id)
        self._sessions[session_id] = session
        logger.info(f"创建会话 {session_id[:8]}，当前并发: {len(self._sessions)}")
        return session

    def get_session(self, session_id: str) -> Session:
        """根据ID获取会话，不存在则返回None。"""
        return self._sessions.get(session_id)

    def destroy_session(self, session_id: str) -> bool:
        """销毁会话并释放资源。"""
        session = self._sessions.pop(session_id, None)
        if session:
            logger.info(f"销毁会话 {session_id[:8]}，剩余并发: {len(self._sessions)}")
            return True
        return False

    def cleanup_expired(self) -> int:
        """清理超时会话，返回清理数量。"""
        expired_ids = [
            sid for sid, s in self._sessions.items()
            if s.is_expired(self.timeout_s)
        ]
        for sid in expired_ids:
            self.destroy_session(sid)
        if expired_ids:
            logger.info(f"清理 {len(expired_ids)} 个超时会话")
        return len(expired_ids)

    @property
    def active_count(self) -> int:
        """当前活跃会话数。"""
        return len(self._sessions)

    @property
    def has_capacity(self) -> bool:
        """是否还有容量创建新会话。"""
        return len(self._sessions) < self.max_concurrent
