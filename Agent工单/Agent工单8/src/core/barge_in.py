"""
src/core/barge_in.py - 打断检测模块
功能: 实时监测输入音频能量，检测用户是否在数字人说话时打断。
      实现对应用户打断后平滑中断当前TTS并进入聆听状态。
      对应工单需求: "数字人应能够自然地被打断，并在中断后恢复对话"
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import numpy as np
import asyncio
import logging

logger = logging.getLogger(__name__)


class BargeInDetector:
    """
    打断检测器。
    通过实时监测音频RMS能量判断用户是否在打断。
    工作原理: 当数字人处于SPEAKING状态时持续监测输入音频，
    如果连续N毫秒检测到高于阈值的语音能量，判定为用户打断。
    """

    def __init__(self, energy_threshold: float = 0.02,
                 trigger_duration_ms: int = 200,
                 sample_rate: int = 16000):
        """
        初始化打断检测器。
        参数:
            energy_threshold: RMS能量阈值，高于此值视为语音活动
            trigger_duration_ms: 连续高于阈值时长才触发(毫秒)
            sample_rate: 输入音频采样率
        """
        self.energy_threshold = energy_threshold
        self.trigger_samples = int(trigger_duration_ms * sample_rate / 1000)
        self.sample_rate = sample_rate
        self._consecutive_above = 0  # 连续高于阈值的采样点数

    def process_chunk(self, audio_chunk: np.ndarray) -> bool:
        """
        处理一个音频块，返回是否检测到打断。
        参数:
            audio_chunk: float32数组，shape (n_samples,)，值[-1.0, 1.0]
        返回:
            True表示检测到用户打断
        """
        if not isinstance(audio_chunk, np.ndarray):
            audio_chunk = np.array(audio_chunk, dtype=np.float32)
        n = len(audio_chunk)
        if n == 0:
            return False
        # 计算RMS能量 = sqrt(mean(x^2))
        energy = float(np.sqrt(np.mean(audio_chunk ** 2)))
        if energy > self.energy_threshold:
            self._consecutive_above += n  # 累加计数
        else:
            self._consecutive_above = 0   # 重置
        # 连续高于阈值达到触发条件
        if self._consecutive_above >= self.trigger_samples:
            logger.info(f"检测到打断: energy={energy:.4f}, "
                         f"dur={self._consecutive_above/self.sample_rate*1000:.0f}ms")
            self._consecutive_above = 0
            return True
        return False

    def reset(self) -> None:
        """重置检测状态(每轮新对话开始时调用)。"""
        self._consecutive_above = 0


class InterruptHandler:
    """
    打断处理器。
    处理打断后的平滑淡出、队列清理和状态恢复。
    """

    def __init__(self, fade_out_ms: int = 100, sample_rate: int = 16000):
        """初始化处理器，设置淡出参数。"""
        self.fade_out_samples = int(fade_out_ms * sample_rate / 1000)

    def fade_out(self, audio: np.ndarray) -> np.ndarray:
        """
        对音频结尾做线性淡出，避免突然切断产生爆音。
        参数:
            audio: float32音频数组
        返回:
            淡出后的音频数组
        """
        if len(audio) <= self.fade_out_samples:
            return audio
        # 线性淡出包络: 1.0 → 0.0
        ramp = np.linspace(1.0, 0.0, self.fade_out_samples)
        result = audio.copy()
        result[-self.fade_out_samples:] *= ramp
        return result

    async def handle(self, session) -> None:
        """
        处理一次打断: 清空TTS队列→标记打断→切换到聆听状态。
        修复: 不再立即reset_interrupt(), 由pipeline消费interrupt_flag后自行reset。
        参数:
            session: 被中断的Session对象
        """
        session.trigger_interrupt()
        session.start_listening()
        logger.info(f"会话 {session.session_id[:8]} 打断处理完成")
