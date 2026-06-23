# -*- coding: utf-8 -*-
"""
asr_engine.py — 语音识别引擎（ASR: Automatic Speech Recognition）
功能：将用户语音转为文本，支持 FunASR 和 Whisper
工单编号：人工智能NLP-Agent数字人项目-基金问答智能体任务
"""

import os
import tempfile
import time
import numpy as np
from logger import logger  # 统一日志

# ============================================================
# FunASR 引擎（阿里达摩院，中文识别精度高）
# ============================================================

class FunASREngine:
    """FunASR 语音识别 — 阿里达摩院出品，中文 ASR 效果最好"""

    def __init__(self, model_name: str = "paraformer-zh"):
        """
        Args:
            model_name: FunASR 模型
                - paraformer-zh (通用中文，推荐)
                - paraformer-large (大模型，更准)
                - sensevoice (多语言)
        """
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        """延迟加载 FunASR 模型"""
        if self._model is None:
            try:
                from funasr import AutoModel
                logger.info(f"加载 FunASR 模型: {self.model_name} ...")
                self._model = AutoModel(
                    model=self.model_name,
                    vad_model="fsmn-vad",         # 语音端点检测
                    punc_model="ct-punc",          # 标点恢复
                    spk_model="cam++",             # 说话人识别（可选）
                )
                logger.info("FunASR 模型加载完成")
            except ImportError:
                raise ImportError("FunASR 未安装。运行: pip install funasr")
            except Exception as e:
                raise RuntimeError(f"FunASR 加载失败: {e}")
        return self._model

    def transcribe(self, audio_path: str) -> dict:
        """
        识别音频文件中的语音

        Args:
            audio_path: 音频文件路径（wav/mp3 等）

        Returns:
            dict: {
                "text": "识别的完整文本",
                "segments": [{"start": 0.0, "end": 1.5, "text": "..."}],
                "language": "zh"
            }
        """
        model = self._load_model()

        result = model.generate(input=audio_path)

        # 解析 FunASR 输出
        if result and len(result) > 0:
            full_text = result[0].get("text", "")
            segments = []
            if "timestamp" in result[0]:
                for t in result[0]["timestamp"]:
                    segments.append({
                        "start": t[0] / 1000.0 if t[0] >= 0 else 0,
                        "end": t[1] / 1000.0 if t[1] >= 0 else 0,
                        "text": t[2] if len(t) > 2 else ""
                    })

            return {
                "text": full_text,
                "segments": segments,
                "language": "zh"
            }

        return {"text": "", "segments": [], "language": "zh"}

    def transcribe_bytes(self, audio_bytes: bytes, sample_rate: int = 16000) -> dict:
        """从音频字节流识别（适合实时场景）"""
        # 写入临时文件
        tmp_path = tempfile.mktemp(suffix=".wav")
        try:
            import wave
            with wave.open(tmp_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(audio_bytes)
            return self.transcribe(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


# ============================================================
# Whisper 引擎（OpenAI，支持多语言）
# ============================================================

class WhisperEngine:
    """Whisper 语音识别 — OpenAI 通用 ASR 模型"""

    MODELS = ["tiny", "base", "small", "medium", "large-v3"]

    def __init__(self, model_name: str = "medium", device: str = "cuda"):
        """
        Args:
            model_name: tiny/base/small/medium/large-v3
            device: cpu / cuda
        """
        self.model_name = model_name
        self.device = device
        self._model = None

    def _load_model(self):
        """延迟加载 Whisper 模型"""
        if self._model is None:
            try:
                import whisper
                logger.info(f"加载 Whisper 模型: {self.model_name} ...")
                self._model = whisper.load_model(
                    self.model_name,
                    device=self.device
                )
                logger.info("Whisper 模型加载完成")
            except ImportError:
                raise ImportError("whisper 未安装。运行: pip install openai-whisper")
            except Exception as e:
                raise RuntimeError(f"Whisper 加载失败: {e}")
        return self._model

    def transcribe(self, audio_path: str, language: str = "zh") -> dict:
        """
        转录音频为文本

        Args:
            audio_path: 音频文件路径
            language: 语言代码（zh/en/auto）

        Returns:
            dict: {"text": "...", "segments": [...]}
        """
        model = self._load_model()

        options = {}
        if language != "auto":
            options["language"] = language

        result = model.transcribe(audio_path, **options)

        segments = []
        for seg in result.get("segments", []):
            segments.append({
                "start": seg.get("start", 0),
                "end": seg.get("end", 0),
                "text": seg.get("text", "").strip()
            })

        return {
            "text": result.get("text", "").strip(),
            "segments": segments,
            "language": result.get("language", language)
        }


# ============================================================
# ASR 工厂函数
# ============================================================

_asr_engine = None

def get_asr_engine(engine_type: str = "funasr", **kwargs):
    """
    获取 ASR 引擎实例

    Args:
        engine_type: "funasr" (推荐中文) 或 "whisper" (多语言)
        **kwargs: 模型参数

    Returns:
        FunASREngine 或 WhisperEngine
    """
    global _asr_engine

    if engine_type == "funasr":
        _asr_engine = FunASREngine(**kwargs)
    elif engine_type == "whisper":
        _asr_engine = WhisperEngine(**kwargs)
    else:
        raise ValueError(f"不支持的 ASR 引擎: {engine_type}")

    return _asr_engine


def speech_to_text(audio_path: str, engine: str = "funasr") -> str:
    """
    便捷函数：将音频转为文本

    Args:
        audio_path: 音频文件路径
        engine: ASR 引擎类型

    Returns:
        str: 识别出的文本
    """
    asr = get_asr_engine(engine)
    result = asr.transcribe(audio_path)
    return result.get("text", "")


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("ASR 引擎测试")
    logger.info("=" * 50)

    # 测试语音文件路径（需要用户提供）
    logger.info("注意：需要提供音频文件才能测试 ASR 功能")
    logger.info("支持的引擎: funasr, whisper")

    # 如果 TTS 生成的文件存在，可以用来测试
    test_audio = "test_tts_output.mp3"
    if os.path.exists(test_audio):
        logger.info(f"使用 TTS 测试输出进行 ASR 测试: {test_audio}")
        try:
            text = speech_to_text(test_audio, engine="funasr")
            logger.info(f"识别结果: {text}")
        except Exception as e:
            logger.warning(f"ASR 测试失败（模型可能未下载）: {e}")
