# -*- coding: utf-8 -*-
"""
tts_engine.py — GPT-SoVITS 语音合成引擎
--------------------------------------------------------------
功能: 基于 GPT-SoVITS 实现文本转语音，支持零样本声音克隆。
      用户可上传参考音频克隆自己的声音，数字人使用克隆声音回复。
      GPT-SoVITS 服务不可用时自动回退到 EdgeTTS。

对应工单需求: "语音合成：gptSovits"、"支持自定义语音合成"

工单编号: 人工智能NLP-Agent数字人项目-数字人与智能体的集成任务
所属目录: 研发
"""
import os, logging, base64, asyncio                         # 标准库
import numpy as np                                          # 音频数组处理
from typing import Optional                                 # 类型注解

from tts_fallback import (                                  # 回退+解码工具
    edge_tts_synthesize, edge_tts_synthesize_sync,
    wav_to_float32, mp3_to_float32, ffmpeg_decode
)

logger = logging.getLogger("tts")  # TTS 模块日志器


class BaseTTSEngine:
    """TTS 引擎抽象基类 — 定义统一接口。"""

    async def synthesize(self, text: str) -> np.ndarray:
        """异步合成语音，返回 float32 数组 (16kHz 单声道)。"""
        raise NotImplementedError

    def synthesize_sync(self, text: str, voice: str = None) -> np.ndarray:
        """同步合成（用于 Flask 等非异步环境）。"""
        raise NotImplementedError

    def audio_to_base64_wav(self, audio: np.ndarray) -> str:
        """将 float32 音频转为 WAV base64 字符串（供前端 <audio> 播放）。

        参数:
            audio: float32 音频数组，16kHz 单声道
        返回:
            base64 编码的 WAV 字符串
        """
        import io, wave
        buf = io.BytesIO()                                  # 内存缓冲区
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(1)                              # 单声道
            wf.setsampwidth(2)                              # 16-bit
            wf.setframerate(16000)                          # 16kHz
            # float32→int16，clip 防止溢出
            samples = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
            wf.writeframes(samples.tobytes())               # 写入WAV帧
        buf.seek(0)                                         # 回到缓冲区开头
        return base64.b64encode(buf.read()).decode('utf-8') # 返回base64


class GPTSovitsEngine(BaseTTSEngine):
    """GPT-SoVITS 语音合成引擎。

    特点:
      - 零样本/少样本声音克隆
      - 通过 HTTP API 调用独立部署的 GPT-SoVITS 服务
      - 自动回退: GPT-SoVITS不可用时使用 EdgeTTS

    对应工单需求: "语音合成：gptSovits"、"支持自定义语音合成"
    """

    def __init__(self, api_url: str = "http://localhost:9880",
                 default_voice: str = "default",
                 ref_audio_path: str = None,
                 ref_text: str = "",
                 sample_rate: int = 16000):
        """初始化 GPT-SoVITS 引擎。

        参数:
            api_url: GPT-SoVITS API 地址 (默认 localhost:9880)
            default_voice: 默认音色名称
            ref_audio_path: 声音克隆参考音频路径
            ref_text: 参考音频对应文本
            sample_rate: 输出音频采样率
        """
        self.api_url = api_url.rstrip('/')                  # 去尾部斜杠
        self.default_voice = default_voice
        self.ref_audio_path = ref_audio_path
        self.ref_text = ref_text
        self.sample_rate = sample_rate
        self._available = None                              # 延迟检测（首次调用时探测）
        logger.info("GPT-SoVITS引擎初始化: api=%s, voice=%s", api_url, default_voice)

    def check_available(self) -> bool:
        """检测 GPT-SoVITS 服务是否可用（带缓存）。

        返回: True=服务可用，False=不可用（将自动回退EdgeTTS）
        """
        if self._available is not None:
            return self._available                          # 使用缓存结果
        try:
            import requests
            r = requests.get(f"{self.api_url}/status", timeout=5)
            self._available = r.status_code == 200
            if self._available:
                logger.info("GPT-SoVITS服务可用: %s", self.api_url)
            else:
                logger.warning("GPT-SoVITS返回非200: %d", r.status_code)
        except Exception as e:
            logger.warning("GPT-SoVITS服务不可用(%s)，将使用EdgeTTS回退", e)
            self._available = False
        return self._available

    async def synthesize(self, text: str, voice: str = None,
                         ref_audio: str = None, ref_text: str = "") -> np.ndarray:
        """异步合成语音（GPT-SoVITS优先→EdgeTTS回退）。

        参数:
            text: 待合成文本
            voice: 音色名称（可选）
            ref_audio: 声音克隆参考音频路径
            ref_text: 参考音频对应文本
        返回: float32 数组，16kHz
        """
        if not text or not text.strip():
            return np.array([], dtype=np.float32)

        if not self.check_available():
            return await edge_tts_synthesize(text)          # 回退EdgeTTS

        try:
            import aiohttp
            payload = {"text": text.strip(), "text_lang": "zh"}
            # 声音克隆: 使用参考音频
            if ref_audio or self.ref_audio_path:
                payload["ref_audio_path"] = ref_audio or self.ref_audio_path
                payload["prompt_text"] = ref_text or self.ref_text or text[:50]
                payload["prompt_lang"] = "zh"
            elif voice:
                payload["voice"] = voice

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/tts", json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        audio = wav_to_float32(await resp.read(), self.sample_rate)
                        if len(audio) > 0:
                            return audio
            logger.warning("GPT-SoVITS返回空音频，回退EdgeTTS")
            return await edge_tts_synthesize(text)
        except Exception as e:
            logger.error("GPT-SoVITS合成失败(%s)，回退EdgeTTS", e)
            return await edge_tts_synthesize(text)

    def synthesize_sync(self, text: str, voice: str = None) -> np.ndarray:
        """同步合成语音（Flask 环境使用）。GPT-SoVITS优先→EdgeTTS回退。

        参数:
            text: 待合成文本
            voice: 音色名称（可选，用于声音克隆）
        返回: float32 数组，16kHz
        """
        if not text or not text.strip():
            return np.array([], dtype=np.float32)

        if not self.check_available():
            return edge_tts_synthesize_sync(text)           # 回退EdgeTTS

        try:
            import requests
            payload = {"text": text.strip(), "text_lang": "zh"}
            if self.ref_audio_path:
                payload["ref_audio_path"] = self.ref_audio_path
                payload["prompt_text"] = self.ref_text or text[:50]
                payload["prompt_lang"] = "zh"

            r = requests.post(f"{self.api_url}/tts", json=payload, timeout=30)
            if r.status_code == 200:
                audio = wav_to_float32(r.content, self.sample_rate)
                if len(audio) > 0:
                    return audio
        except Exception as e:
            logger.error("GPT-SoVITS同步合成失败(%s)", e)

        return edge_tts_synthesize_sync(text)

    async def clone_voice(self, voice_name: str, ref_audio_path: str,
                          ref_text: str = "") -> bool:
        """注册声音克隆到 GPT-SoVITS 服务。

        参数:
            voice_name: 克隆声音名称
            ref_audio_path: 参考音频文件路径
            ref_text: 参考文本（可选）
        返回: True=注册成功，False=失败
        """
        if not self.check_available():
            logger.warning("GPT-SoVITS不可用，无法克隆声音")
            return False

        try:
            import aiohttp
            payload = {"voice_name": voice_name,
                       "ref_audio_path": ref_audio_path,
                       "prompt_text": ref_text or ""}
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.api_url}/voice_clone", json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    if resp.status == 200:
                        logger.info("声音克隆成功: %s", voice_name)
                        return True
                    logger.warning("声音克隆失败: HTTP %d", resp.status)
                    return False
        except Exception as e:
            logger.error("声音克隆请求失败: %s", e)
            return False


# ================================================================
# 全局单例 — 延迟初始化，首次调用时创建
# ================================================================
_tts_instance: Optional[GPTSovitsEngine] = None


def get_tts_engine(config=None) -> GPTSovitsEngine:
    """获取全局 TTS 引擎单例。

    参数:
        config: 配置模块（可选，用于读取 GPT-SoVITS URL 等参数）
    返回:
        GPTSovitsEngine 实例
    """
    global _tts_instance
    if _tts_instance is None:
        api = getattr(config, 'GPTSOVITS_URL', "http://localhost:9880") if config else "http://localhost:9880"
        ref_aud = getattr(config, 'GPTSOVITS_REF_AUDIO', None) if config else None
        ref_txt = getattr(config, 'GPTSOVITS_REF_TEXT', "") if config else ""
        _tts_instance = GPTSovitsEngine(api_url=api, ref_audio_path=ref_aud, ref_text=ref_txt)
    return _tts_instance


# ================================================================
# 自测
# ================================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                        datefmt="%H:%M:%S")
    engine = GPTSovitsEngine()
    avail = engine.check_available()
    print(f"GPT-SoVITS可用: {avail}")
    if not avail:
        print("将使用EdgeTTS回退方案")
    audio = engine.synthesize_sync("你好，我是AI智能助手。")
    print(f"合成音频: {len(audio)}采样点 ({len(audio)/16000:.2f}秒)")
