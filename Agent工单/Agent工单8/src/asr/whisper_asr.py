"""
src/asr/whisper_asr.py - 语音识别模块
功能: 基于 OpenAI Whisper 模型实现实时语音转文字。
      运行在CPU上以节省GPU显存给Wav2Lip使用。
      对应工单需求: "实时接收用户的语音输入，将其转换为文本"
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import numpy as np
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# 全局线程池，避免每次推理都创建线程
_executor = ThreadPoolExecutor(max_workers=2)


class WhisperASR:
    """
    Whisper 语音识别引擎。
    使用 openai-whisper tiny 模型在 CPU 上运行。
    tiny模型仅75MB，在CPU上的推理速度约为实时速度的2-3倍，
    足以满足实时交互需求且不占用GPU显存。
    """

    def __init__(self, model_name: str = "tiny", language: str = "zh",
                 device: str = "cpu", sample_rate: int = 16000):
        """
        初始化Whisper ASR引擎。

        参数:
            model_name: 模型大小 (tiny/base/small)
            language: 目标识别语言
            device: 推理设备 (cpu 节省显存)
            sample_rate: 输入音频采样率
        """
        self.model_name = model_name
        self.language = language
        self.device = device
        self.sample_rate = sample_rate
        self._model = None  # 延迟加载

    def _load_model(self):
        """延迟加载Whisper模型(首次使用时加载)。"""
        if self._model is None:
            import whisper
            logger.info(f"加载Whisper模型: {self.model_name} (device={self.device})")
            self._model = whisper.load_model(self.model_name, device=self.device)
            logger.info("Whisper模型加载完成")
        return self._model

    def _transcribe_sync(self, audio: np.ndarray) -> str:
        """
        同步执行语音识别(在后台线程中运行)。

        参数:
            audio: float32音频数组，16kHz采样率
        返回:
            识别出的文本内容
        """
        model = self._load_model()
        # 确保音频是float32格式，值范围[-1, 1]
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        # 如果音频太长，只取最近30秒
        max_len = 30 * self.sample_rate
        if len(audio) > max_len:
            audio = audio[-max_len:]
        # 调用Whisper转录
        result = model.transcribe(
            audio,
            language=self.language,
            fp16=False,                      # CPU上不使用FP16
            no_speech_threshold=0.6,          # 无声阈值
            condition_on_previous_text=True,  # 利用上文改善识别
        )
        text = result["text"].strip()
        return text

    async def transcribe(self, audio: np.ndarray) -> str:
        """
        异步语音识别接口。

        参数:
            audio: float32音频数组
        返回:
            识别文本，失败时返回空字符串
        """
        if audio is None or len(audio) == 0:
            return ""
        # 确保音频长度至少为 0.1 秒（1600 采样），避免 Whisper 推理失败
        if len(audio) < 1600:
            return ""
        try:
            # 在后台线程中运行Whisper推理，避免阻塞事件循环
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(
                _executor, self._transcribe_sync, audio
            )
            return text
        except Exception as error:
            logger.error(f"Whisper推理异常: {error}")
            return ""

    def transcribe_file(self, audio_path: str) -> str:
        """
        离线转录音频文件(用于测试和批量处理)。

        参数:
            audio_path: 音频文件路径
        返回:
            识别文本
        """
        import soundfile as sf
        audio, sr = sf.read(audio_path)
        # 重采样到16kHz
        if sr != self.sample_rate:
            import librosa
            audio = librosa.resample(audio, orig_sr=sr, target_sr=self.sample_rate)
        return self._transcribe_sync(audio.astype(np.float32))
