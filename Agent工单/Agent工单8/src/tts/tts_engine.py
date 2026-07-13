"""
src/tts/tts_engine.py - TTS语音合成引擎 (流式版)
功能: 统一的TTS接口，支持EdgeTTS(默认)和CosyVoice(声音克隆可选)。
      新增 synthesize_chunk() 方法用于句子级流式合成，
      添加句子间平滑过渡(微小静音填充)。
      对应工单需求: "将文本转换为语音输出"、"声音克隆"、"多语言对话"
      性能要求: TTS延迟≤1.7秒
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import numpy as np
import logging
import subprocess
import tempfile
import os
from typing import AsyncIterator, Optional

logger = logging.getLogger(__name__)


class BaseTTSEngine:
    """TTS引擎抽象基类，所有TTS后端继承此类。"""

    async def synthesize(self, text: str) -> np.ndarray:
        """合成完整文本，返回 float32 numpy数组。"""
        raise NotImplementedError

    async def synthesize_chunk(self, text: str) -> np.ndarray:
        """
        合成单个句子片段(流式友好)。
        默认调用 synthesize()，子类可覆盖实现真正的流式。
        返回: float32 numpy数组，16kHz单声道
        """
        return await self.synthesize(text)


class EdgeTTSEngine(BaseTTSEngine):
    """
    Microsoft Edge TTS引擎(免费、流式、多语言)。
    零VRAM占用，延迟200-800ms，满足工单TTS≤1.7s要求。
    """

    def __init__(self, voice: str = "zh-CN-XiaoxiaoNeural",
                 rate: str = "+0%", pitch: str = "+0Hz"):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        self.sample_rate = 16000
        # 句子间过渡静音(样本数) — 约50ms，避免拼接爆音
        self._inter_sentence_silence = int(0.05 * self.sample_rate)

    async def synthesize(self, text: str) -> np.ndarray:
        """
        将文本转为16kHz PCM float32音频。
        参数: text - 待合成文本
        返回: float32 numpy数组，16kHz单声道
        """
        if not text or not text.strip():
            return np.array([], dtype=np.float32)
        try:
            import edge_tts
            comm = edge_tts.Communicate(text=text, voice=self.voice,
                                        rate=self.rate, pitch=self.pitch)
            chunks = []
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    chunks.append(chunk["data"])
            if not chunks:
                return np.array([], dtype=np.float32)
            full_mp3 = b"".join(chunks)
            return self._mp3_to_pcm(full_mp3)
        except ImportError:
            logger.error("请安装: pip install edge-tts")
            return np.array([], dtype=np.float32)
        except Exception as e:
            logger.error(f"TTS失败: {e}")
            return np.array([], dtype=np.float32)

    async def synthesize_chunk(self, text: str,
                                add_silence_pad: bool = False,
                                voice: str = None) -> np.ndarray:
        """
        合成单个句子片段。EdgeTTS本身已支持流式，
        这里直接按句子调用完整合成(延迟200-800ms，满足<1.7s要求)。
        参数:
            text: 句子文本
            add_silence_pad: 是否在末尾添加过渡静音
            voice: 可选，覆盖默认TTS语音角色
        返回: float32 numpy数组
        """
        # 如果指定了不同的voice，临时切换
        if voice and voice != self.voice:
            saved_voice = self.voice
            self.voice = voice
            audio = await self.synthesize(text)
            self.voice = saved_voice
        else:
            audio = await self.synthesize(text)

        if add_silence_pad and len(audio) > 0 and self._inter_sentence_silence > 0:
            silence = np.zeros(self._inter_sentence_silence, dtype=np.float32)
            audio = np.concatenate([audio, silence])
        return audio

    def _mp3_to_pcm(self, mp3_data: bytes) -> np.ndarray:
        """FFmpeg解码MP3→PCM 16kHz mono float32。"""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(mp3_data)
            mp3_path = f.name
        pcm_path = mp3_path + ".pcm"
        try:
            subprocess.run([
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", mp3_path, "-f", "s16le",
                "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
                pcm_path,
            ], check=True)
            with open(pcm_path, "rb") as f:
                pcm_bytes = f.read()
            samples = np.frombuffer(pcm_bytes, dtype=np.int16)
            return samples.astype(np.float32) / 32768.0
        finally:
            if os.path.exists(mp3_path):
                os.remove(mp3_path)
            if os.path.exists(pcm_path):
                os.remove(pcm_path)


class CosyVoiceTTSEngine(BaseTTSEngine):
    """
    CosyVoice声音克隆TTS(可选，通过HTTP API调用独立服务)。
    用于工单中的"声音克隆"需求。
    """

    def __init__(self, api_url: str = "http://localhost:5001/v1/tts"):
        self.api_url = api_url

    async def synthesize(self, text: str, voice_id: str = None) -> np.ndarray:
        """调用CosyVoice API合成，支持指定克隆声音ID。"""
        try:
            import aiohttp
            payload = {"text": text}
            if voice_id:
                payload["voice_id"] = voice_id
            async with aiohttp.ClientSession() as s:
                async with s.post(self.api_url, json=payload,
                                  timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        arr = np.frombuffer(data, dtype=np.int16)
                        return arr.astype(np.float32) / 32768.0
        except Exception as e:
            logger.error(f"CosyVoice失败: {e}")
        return np.array([], dtype=np.float32)


class CosyVoiceLocalEngine(BaseTTSEngine):
    """
    CosyVoice 本地声音克隆TTS引擎。
    延迟加载模型，避免启动时占用显存。
    对应工单需求: "支持声音克隆技术，能够模仿特定人物的声音"
    """

    def __init__(self, model_dir: str = "models/cosyvoice",
                 reference_audio: str = None,
                 reference_text: str = None):
        """
        初始化CosyVoice本地引擎。
        参数:
            model_dir: CosyVoice模型目录
            reference_audio: 参考音频路径(用于声音克隆)
            reference_text: 参考音频对应文本
        """
        self.model_dir = model_dir
        self.reference_audio = reference_audio
        self.reference_text = reference_text
        self._model = None
        self._loaded = False

    def _load_model(self):
        """延迟加载CosyVoice模型。"""
        if self._loaded:
            return
        try:
            import sys
            cosy_dir = self.model_dir
            if os.path.exists(cosy_dir):
                sys.path.insert(0, cosy_dir)
            from cosyvoice.cli.cosyvoice import CosyVoice
            self._model = CosyVoice(self.model_dir)
            self._loaded = True
            logger.info("CosyVoice本地模型加载完成")
        except ImportError:
            logger.warning(
                "CosyVoice未安装。请参考: https://github.com/FunAudioLLM/CosyVoice\n"
                "安装: pip install cosyvoice && python -m cosyvoice.download"
            )
            self._loaded = True  # 标记已尝试，避免重复warning
        except Exception as e:
            logger.error(f"CosyVoice加载失败: {e}")
            self._loaded = True

    async def synthesize(self, text: str, voice_id: str = "default") -> np.ndarray:
        """合成语音，支持声纹ID。"""
        if not self._loaded:
            self._load_model()
        if self._model is None:
            logger.warning("CosyVoice模型不可用，回退到静音")
            return np.array([], dtype=np.float32)
        try:
            output = self._model.inference_sft(
                text, spk_id=voice_id, stream=False
            )
            # CosyVoice返回的是torch tensor或numpy array
            if hasattr(output, 'cpu'):
                output = output.cpu().numpy()
            if isinstance(output, np.ndarray):
                return output.astype(np.float32)
            return np.array([], dtype=np.float32)
        except Exception as e:
            logger.error(f"CosyVoice合成失败: {e}")
            return np.array([], dtype=np.float32)


def create_tts_engine(config) -> BaseTTSEngine:
    """TTS工厂函数，根据配置创建后端实例。"""
    backend = config.tts.default_backend
    if backend == "edge":
        return EdgeTTSEngine(
            voice=config.tts.edge_voice,
            rate=config.tts.edge_rate,
            pitch=config.tts.edge_pitch,
        )
    elif backend == "cosyvoice":
        return CosyVoiceTTSEngine(
            api_url=getattr(config.tts, 'cosyvoice_url',
                            "http://localhost:5001/v1/tts")
        )
    elif backend == "cosyvoice_local":
        return CosyVoiceLocalEngine(
            model_dir=getattr(config.tts, 'cosyvoice_model_dir',
                              "models/cosyvoice"),
            reference_audio=getattr(config.tts, 'reference_audio', None),
            reference_text=getattr(config.tts, 'reference_text', None),
        )
    else:
        logger.warning(f"未知TTS后端'{backend}'，回退EdgeTTS")
        return EdgeTTSEngine()
