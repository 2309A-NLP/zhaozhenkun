"""
================================================================================
文件名:   tts_client.py
功能:     TTS 语音合成客户端 + 数字人语音管线
          —— 使用 EdgeTTS（免费微软语音合成）实现文字转语音
          —— 数字人管线：ASR→LLM→TTS 完整语音对话流程
所属项目: 医疗智能体-Agent 数字人项目
工单编号: 人工智能 NLP-Agent 数字人项目-医疗智能体-实时语音识别 V1.0

TTS 引擎:
  EdgeTTS: Microsoft Edge 免费 TTS，无需 API Key，中文质量高
  音色: zh-CN-XiaoxiaoNeural（女声）/ zh-CN-YunxiNeural（男声）

数字人管线:
  语音输入 → ASR → 文本 → Agent(DeepSeek) → 回复文本 → TTS → 语音输出
                 翻译              会议纪要
================================================================================
"""
import io, base64, logging, tempfile, os, asyncio, subprocess  # 导入：io（字节流处理）、base64（音频编码）、logging（日志）、tempfile（临时文件）、os（系统操作）、asyncio（异步IO）、subprocess（子进程调用）
from pathlib import Path  # 导入Path用于文件路径操作
from typing import Optional, AsyncGenerator  # 导入类型提示：Optional表示可选类型，AsyncGenerator表示异步生成器

_log = logging.getLogger("medical_agent.tts")  # 创建模块级日志记录器，标识为"medical_agent.tts"

# ================================================================
# 默认音色配置
# ================================================================
VOICES = {  # 定义音色名称到EdgeTTS语音标识的映射字典
    "xiaoxiao": "zh-CN-XiaoxiaoNeural",   # 女声-温柔（晓晓）
    "yunxi":    "zh-CN-YunxiNeural",       # 男声-新闻（云希）
    "xiaoyi":   "zh-CN-XiaoyiNeural",      # 女声-活泼（晓伊）
    "yunyang":  "zh-CN-YunyangNeural",     # 男声-专业（云扬）
}


class TTSClient:  # 定义TTS语音合成客户端类
    """
    TTS 语音合成客户端（EdgeTTS + 备用方案）

    使用方法:
      client = TTSClient()
      audio_bytes = await client.synthesize("你好，我是数字人医生")
      # 返回 MP3 音频 bytes，可直接播放
    """

    def __init__(self, voice: str = "xiaoxiao"):  # 构造函数：voice参数指定默认音色，默认为晓晓女声
        self.voice = VOICES.get(voice, VOICES["xiaoxiao"])  # 根据输入名称查找对应的EdgeTTS语音标识，未找到则默认晓晓
        self.rate = "+0%"    # 语速修正值：+0%表示使用默认语速（正向为加速，负向为减速）
        self.pitch = "+0Hz"  # 音调修正值：+0Hz表示使用默认音高（正向为升高，负向为降低）

    async def synthesize(self, text: str, voice: str = None) -> bytes:  # 异步文字转语音方法：输入文本返回MP3音频字节
        """
        文字转语音（异步）

        参数:
          text:  待合成的文本（中文）
          voice: 音色名（xiaoxiao/yunxi/xiaoyi/yunyang）

        返回:
          MP3 音频的 bytes（可直接 base64 编码发送前端）

        实现:
          1. 优先使用 edge-tts Python 包
          2. 备用: 调用系统 edge-playback 命令
          3. 兜底: 返回空（前端不播放但有文字显示）
        """
        v = VOICES.get(voice, self.voice) if voice else self.voice  # 如果指定了voice参数则映射为EdgeTTS标识，否则使用实例默认音色

        try:  # 第一层异常捕获：尝试方式1
            # 方式1: edge-tts Python 包
            return await self._edge_tts_sdk(text, v)  # 调用Python SDK方式合成语音，成功则直接返回音频字节
        except ImportError:  # 捕获ImportError：说明edge-tts包未安装
            pass  # 静默跳过，继续尝试下一种方式
        except Exception as e:  # 捕获其他异常（网络、超时等）
            _log.warning("edge-tts SDK 失败: %s，尝试命令行方式", e)  # 记录警告日志，准备降级到命令行方式

        try:  # 第二层异常捕获：尝试方式2
            # 方式2: 命令行 edge-tts
            return await self._edge_tts_cli(text, v)  # 调用命令行方式合成语音
        except Exception as e:  # 捕获命令行方式的异常
            _log.warning("edge-tts CLI 也失败: %s", e)  # 记录警告日志

        # 兜底：返回空 bytes，前端只显示文字
        return b""  # 所有方式都失败时返回空字节，前端将只显示文字不播放音频

    async def _edge_tts_sdk(self, text: str, voice: str) -> bytes:  # 使用edge-tts Python SDK合成语音的私有方法
        """使用 edge-tts Python SDK"""
        import edge_tts  # 动态导入edge_tts包（延迟导入，避免未安装时影响模块加载）
        communicate = edge_tts.Communicate(text, voice, rate=self.rate, pitch=self.pitch)  # 创建Communicate对象，传入文本、音色、语速、音调
        audio_data = b""  # 初始化空字节用于累积音频数据
        async for chunk in communicate.stream():  # 异步遍历语音合成流，逐块获取音频数据
            if chunk["type"] == "audio":  # 判断当前块类型是否为音频数据
                audio_data += chunk["data"]  # 将音频数据块拼接到总数据中
        return audio_data  # 返回完整的MP3音频字节数据

    async def _edge_tts_cli(self, text: str, voice: str) -> bytes:  # 使用edge-tts命令行工具合成语音的私有方法（备用方案）
        """使用 edge-tts 命令行工具"""
        loop = asyncio.get_event_loop()  # 获取当前事件循环，用于在异步上下文中运行同步子进程
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:  # 创建临时文件存储音频输出，delete=False表示手动管理生命周期
            tmp_path = f.name  # 记录临时文件的完整路径

        try:  # 异常捕获和资源清理
            # 执行 edge-tts 命令
            cmd = ["edge-tts", "--voice", voice, "--text", text,  # 构建命令行参数：指定音色和待合成文本
                   "--write-media", tmp_path]  # 指定输出音频文件路径
            proc = await loop.run_in_executor(  # 在线程池中运行子进程（避免阻塞事件循环）
                None,  # 使用默认线程池执行器
                lambda: subprocess.run(cmd, capture_output=True, timeout=30)  # 执行子进程命令：捕获输出，30秒超时
            )
            if proc.returncode == 0 and os.path.exists(tmp_path):  # 检查命令是否成功执行且输出文件存在
                with open(tmp_path, "rb") as f:  # 以二进制读取模式打开临时音频文件
                    return f.read()  # 读取并返回文件中的全部音频字节
            return b""  # 命令失败或文件不存在时返回空字节
        finally:  # 无论成功与否都执行的清理代码块
            if os.path.exists(tmp_path):  # 检查临时文件是否仍然存在
                os.unlink(tmp_path)  # 删除临时文件，释放磁盘空间

    def synthesize_sync(self, text: str, voice: str = None) -> bytes:  # 同步版本的语音合成方法（用于非异步环境调用）
        """同步版本（用于非异步环境）"""
        import asyncio as aio  # 导入asyncio并重命名为aio（避免与参数名冲突）
        try:  # 异常捕获
            loop = aio.get_event_loop()  # 获取当前线程的事件循环
            if loop.is_running():  # 如果事件循环已在运行中（例如在Jupyter notebook中）
                return aio.run_coroutine_threadsafe(  # 使用线程安全方式在运行中的循环里调度协程
                    self.synthesize(text, voice), loop).result(timeout=30)  # 调度异步合成方法并等待结果，30秒超时
            return aio.run(self.synthesize(text, voice))  # 事件循环未运行：直接使用aio.run()执行异步方法
        except:  # 捕获所有异常
            return b""  # 任何错误都返回空字节作为安全兜底


# ================================================================
# 数字人语音管线
# ================================================================
class VoicePipeline:  # 定义数字人完整语音管线类：整合ASR→LLM→TTS的端到端流程
    """
    数字人完整语音管线

    流程:
      Step 1: 语音输入（前端录音/WebSocket）
      Step 2: ASR 转文字（通义听悟/DashScope 实时识别）
      Step 3: Agent 回复（DeepSeek 健康助理）
      Step 4: TTS 语音合成（EdgeTTS）
      Step 5: 返回音频 + 文字（前端播放+显示）
    """

    def __init__(self):  # 构造函数：初始化语音管线
        self.tts = TTSClient(voice="xiaoxiao")  # 创建TTS客户端实例，默认使用晓晓女声音色
        self._agent_context = []  # 对话上下文列表，用于存储历史对话（支持多轮对话记忆）

    async def process(self, user_text: str,  # 数字人管线核心处理方法：输入用户语音识别后的文本
                      enable_tts: bool = True,  # 是否启用TTS语音合成（默认开启）
                      enable_summary: bool = False) -> dict:  # 是否生成会议纪要（默认关闭）
        """
        数字人管线核心方法

        参数:
          user_text:      用户语音识别后的文本
          enable_tts:     是否启用 TTS 合成语音
          enable_summary: 是否生成会议纪要

        返回:
          {
            "text": "Agent 文字回复",
            "audio_b64": "base64编码的MP3音频（如果enable_tts=True）",
            "summary": {...}  # 如果 enable_summary=True
          }
        """
        from services.llm_client import get_deepseek_client  # 延迟导入DeepSeek客户端（避免循环依赖）
        ds = get_deepseek_client()  # 获取DeepSeek客户端单例

        # Step 1: Agent 回复（DeepSeek 健康助理）
        system = """你是智能健康助理"小医"，专业、亲切。用中文回复。  # 系统提示词：定义Agent的角色为"小医"健康助理
对于医学问题，给出预防和就诊建议，并加免责声明。"""  # 系统提示词续：要求医学问题附带预防建议和免责声明
        messages = [{"role": "user", "content": user_text}]  # 构建用户消息：放入用户的语音识别文本
        result = ds.chat(messages, system=system, max_tokens=800)  # 调用DeepSeek对话接口，限制回复800token

        reply_text = result.get("content", "抱歉，我暂时无法回答。")  # 提取Agent回复文本，失败则使用默认道歉语
        response = {"text": reply_text}  # 初始化返回字典，先放入文本回复

        # Step 2: TTS 语音合成
        if enable_tts and reply_text:  # 如果启用了TTS并且有有效的回复文本
            audio_bytes = await self.tts.synthesize(reply_text)  # 异步合成语音，将回复文本转为MP3音频字节
            if audio_bytes:  # 如果合成成功返回了音频数据
                response["audio_b64"] = base64.b64encode(audio_bytes).decode()  # 将音频字节编码为base64字符串，方便JSON传输
                response["audio_format"] = "mp3"  # 标记音频格式为mp3

        # Step 3: 会议纪要（可选）
        if enable_summary and user_text:  # 如果启用了会议纪要并且有用户输入文本
            from services.tingwu_client import get_tingwu_client  # 延迟导入通义听悟客户端（依赖可能不存在）
            tw = get_tingwu_client()  # 获取通义听悟客户端单例
            response["summary"] = tw.process_transcript(user_text)  # 调用通义听悟处理转录文本生成会议纪要

        return response  # 返回包含文本、音频和纪要的完整响应字典


# ================================================================
# 全局单例
# ================================================================
_tts: Optional[TTSClient] = None  # 全局TTS客户端单例变量，类型标注为Optional[TTSClient]，初始为None
_pipeline: Optional[VoicePipeline] = None  # 全局语音管线单例变量，类型标注为Optional[VoicePipeline]，初始为None


def get_tts_client() -> TTSClient:  # 获取TTS客户端单例的工厂函数，返回类型为TTSClient
    global _tts  # 声明使用全局变量_tts
    if _tts is None:  # 检查单例是否已创建
        _tts = TTSClient()  # 未创建则新建实例（懒加载模式）
    return _tts  # 返回TTS客户端单例


def get_voice_pipeline() -> VoicePipeline:  # 获取语音管线单例的工厂函数，返回类型为VoicePipeline
    global _pipeline  # 声明使用全局变量_pipeline
    if _pipeline is None:  # 检查单例是否已创建
        _pipeline = VoicePipeline()  # 未创建则新建实例（懒加载模式）
    return _pipeline  # 返回语音管线单例
