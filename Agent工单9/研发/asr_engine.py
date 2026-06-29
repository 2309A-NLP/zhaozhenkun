# -*- coding: utf-8 -*-
"""
asr_engine.py — FunASR 语音识别引擎
--------------------------------------------------------------
功能: 基于 FunASR SenseVoiceSmall 实现实时语音转文字。
      CPU/GPU 自适应，支持 VAD 语音活动检测和流式识别。
      FunASR 不可用时自动回退 Whisper。

对应工单需求: "语音识别：funASR"、"用户通过语音进行输入"

工单编号: 人工智能NLP-Agent数字人项目-数字人与智能体的集成任务
所属目录: 研发
"""
import logging                              # 日志记录
import numpy as np                          # 音频数组处理
import asyncio                              # 异步 IO
from concurrent.futures import ThreadPoolExecutor  # 线程池（避免阻塞事件循环）
from typing import Optional                        # 类型注解

logger = logging.getLogger("asr")  # ASR 模块日志器
_executor = ThreadPoolExecutor(max_workers=2)  # 全局推理线程池（2线程）


class FunASREngine:
    """FunASR 语音识别引擎。

    支持模型:
      - SenseVoiceSmall: 多语言、高精度、低延迟（推荐）
      - Paraformer: 中文专优、非自回归、实时
      - 自动回退: FunASR 不可用时使用 Whisper tiny

    对应工单需求: "语音识别：funASR"
    """

    def __init__(self, model_name: str = "iic/SenseVoiceSmall",
                 language: str = "zh", device: str = "cpu",
                 sample_rate: int = 16000, vad_enabled: bool = True):
        """初始化 FunASR 引擎。

        参数:
            model_name: FunASR 模型名 (SenseVoiceSmall 多语言 / Paraformer 中文)
            language: 识别语言 (zh/en/auto)
            device: 推理设备 (cpu/cuda:0)
            sample_rate: 输入音频采样率（默认 16000）
            vad_enabled: 是否启用 VAD 语音活动检测（自动分割说话段）
        """
        self.model_name = model_name          # 模型标识
        self.language = language              # 识别语言
        self.device = device                  # 推理设备
        self.sample_rate = sample_rate        # 音频采样率
        self.vad_enabled = vad_enabled        # VAD 开关
        self._model = None                    # ASR 模型实例（延迟加载）
        self._vad_model = None                # VAD 模型实例
        self._loaded = False                  # 是否已加载
        self._fallback = None                 # 回退引擎标识 ('whisper' or None)
        logger.info("FunASR引擎初始化: model=%s, lang=%s, device=%s",
                     model_name, language, device)

    def _load_model(self):
        """延迟加载 ASR 模型（首次使用时加载，避免启动慢）。"""
        if self._loaded:
            return
        try:
            from funasr import AutoModel           # FunASR 自动模型
            logger.info("加载FunASR模型: %s", self.model_name)
            self._model = AutoModel(
                model=self.model_name,              # SenseVoiceSmall / Paraformer
                device=self.device,                 # cpu / cuda:0
                disable_update=True,                # 不自动更新模型
            )
            # 可选: 加载 VAD 模型（语音活动检测）
            if self.vad_enabled:
                try:
                    self._vad_model = AutoModel(
                        model="iic/speech_fsmn_vad_zh-cn-16k-common-pytorch",
                        device=self.device,
                        disable_update=True,
                    )
                    logger.info("FunASR VAD模型加载完成")
                except Exception as e:
                    logger.warning("VAD模型加载失败(将使用能量VAD): %s", e)
                    self._vad_model = None
            self._loaded = True
            logger.info("FunASR模型加载完成: %s", self.model_name)
        except ImportError:
            logger.warning("FunASR未安装，将使用Whisper回退。安装: pip install funasr modelscope")
            self._load_whisper_fallback()
        except Exception as e:
            logger.error("FunASR加载失败: %s", e)
            self._load_whisper_fallback()

    def _load_whisper_fallback(self):
        """Whisper 回退方案（FunASR 不可用时自动切换）。"""
        try:
            import whisper                          # OpenAI Whisper
            logger.info("使用Whisper tiny作为回退ASR")
            self._model = whisper.load_model("tiny", device=self.device)
            self._fallback = "whisper"              # 标记为 Whisper 模式
            self._loaded = True
        except ImportError:
            logger.error("Whisper也未安装。安装: pip install openai-whisper")
            self._model = None; self._loaded = True  # 标记已尝试，避免重复加载

    # ================================================================
    # 识别核心方法
    # ================================================================

    def _transcribe_funasr(self, audio: np.ndarray) -> str:
        """使用 FunASR 进行语音识别。

        参数:
            audio: float32 音频数组，16kHz 采样率
        返回: 识别出的文本
        """
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)         # 确保 float32 类型
        max_len = 30 * self.sample_rate              # 最长 30 秒
        if len(audio) > max_len:
            audio = audio[-max_len:]                 # 截断超长音频

        # VAD 模式: 先分割语音段，逐段识别
        if self._vad_model:
            try:
                vad_result = self._vad_model.generate(
                    input=audio, chunk_size=200       # 200ms 分块
                )
                if vad_result and len(vad_result) > 0:
                    segments = vad_result[0].get("value", [])
                    if segments:
                        texts = []
                        for seg in segments:
                            start = int(seg[0] * self.sample_rate / 1000)  # 起始采样点
                            end = int(seg[1] * self.sample_rate / 1000)    # 结束采样点
                            seg_audio = audio[start:end]
                            if len(seg_audio) > self.sample_rate * 0.1:     # >100ms 有效段
                                result = self._model.generate(
                                    input=seg_audio,
                                    language=self.language if self.language != "auto" else None,
                                )
                                if result and len(result) > 0:
                                    text = result[0].get("text", "")
                                    if text.strip():
                                        texts.append(text)   # 收集各段识别结果
                        if texts:
                            return " ".join(texts)           # 空格拼接多段
            except Exception as e:
                logger.debug("VAD处理失败，使用整段识别: %s", e)

        # 整段识别（无 VAD 或 VAD 失败）
        result = self._model.generate(
            input=audio,
            language=self.language if self.language != "auto" else None,
        )
        if result and len(result) > 0:
            return result[0].get("text", "").strip()
        return ""

    def _transcribe_whisper(self, audio: np.ndarray) -> str:
        """Whisper 回退识别。

        参数:
            audio: float32 音频数组
        返回: 识别文本
        """
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        max_len = 30 * self.sample_rate
        if len(audio) > max_len:
            audio = audio[-max_len:]
        result = self._model.transcribe(
            audio, language=self.language,
            fp16=False,                            # CPU 推理使用 FP32
            no_speech_threshold=0.6,               # 静音检测阈值
        )
        return result["text"].strip()

    async def transcribe(self, audio: np.ndarray) -> str:
        """异步语音识别接口（主要对外接口）。

        在线程池中运行推理，不阻塞事件循环。

        参数:
            audio: float32 音频数组，16kHz 单声道
        返回: 识别文本
        """
        if not self._loaded:
            self._load_model()                      # 延迟加载
        if self._model is None:
            logger.error("ASR模型未加载，无法识别")
            return ""
        loop = asyncio.get_event_loop()
        if self._fallback == 'whisper':
            return await loop.run_in_executor(_executor, self._transcribe_whisper, audio)
        return await loop.run_in_executor(_executor, self._transcribe_funasr, audio)

    def transcribe_sync(self, audio: np.ndarray) -> str:
        """同步语音识别（用于 Flask 等非异步环境）。

        参数:
            audio: float32 音频数组
        返回: 识别文本
        """
        if not self._loaded:
            self._load_model()
        if self._model is None:
            return ""
        if self._fallback == 'whisper':
            return self._transcribe_whisper(audio)
        return self._transcribe_funasr(audio)

    def transcribe_file(self, audio_path: str) -> str:
        """转录音频文件（用于测试和批量处理）。

        参数:
            audio_path: 音频文件路径（支持 WAV/MP3 等）
        返回: 识别文本
        """
        try:
            import soundfile as sf                 # 音频文件读取
            audio, sr = sf.read(audio_path)        # 读取音频数据和采样率
            if sr != self.sample_rate:              # 需要重采样
                import librosa
                audio = librosa.resample(audio, orig_sr=sr, target_sr=self.sample_rate)
            return self.transcribe_sync(audio.astype(np.float32))
        except ImportError:
            logger.error("需要soundfile/librosa: pip install soundfile librosa")
            return ""
        except Exception as e:
            logger.error("文件转录失败: %s", e)
            return ""

    # ================================================================
    # 属性
    # ================================================================
    @property
    def is_loaded(self) -> bool:
        """模型是否已加载（含回退方案）。"""
        return self._loaded and self._model is not None

    @property
    def engine_type(self) -> str:
        """当前使用的引擎类型: 'funasr' 或 'whisper'。"""
        return self._fallback or "funasr"


# ============================================================
# 全局单例 — 延迟初始化
# ============================================================
_asr_instance: Optional[FunASREngine] = None


def get_asr_engine(config=None) -> FunASREngine:
    """获取全局 ASR 引擎单例。

    参数:
        config: 配置模块（可选，用于读取 ASR_MODEL/ASR_LANGUAGE/ASR_DEVICE）
    返回:
        FunASREngine 实例
    """
    global _asr_instance
    if _asr_instance is None:
        model = getattr(config, 'ASR_MODEL', "iic/SenseVoiceSmall") if config else "iic/SenseVoiceSmall"
        lang = getattr(config, 'ASR_LANGUAGE', "zh") if config else "zh"
        device = getattr(config, 'ASR_DEVICE', "cpu") if config else "cpu"
        _asr_instance = FunASREngine(model_name=model, language=lang, device=device)
    return _asr_instance


# ============================================================
# 自测
# ============================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                        datefmt="%H:%M:%S")
    engine = FunASREngine()
    print(f"ASR引擎: {engine.engine_type}, 已加载={engine.is_loaded}")
    if engine.is_loaded:
        test_audio = np.zeros(16000, dtype=np.float32)  # 1秒静音
        result = engine.transcribe_sync(test_audio)
        print(f"静音测试: '{result}'")
