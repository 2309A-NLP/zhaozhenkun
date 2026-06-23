# -*- coding: utf-8 -*-
"""
tts_engine.py — 语音合成引擎（TTS: Text-to-Speech）
功能：将文本答案转为自然语音，支持 Edge-TTS（免费中文）和 Paddle TTS
工单编号：人工智能NLP-Agent数字人项目-基金问答智能体任务
"""

import os
import asyncio
import tempfile
import time
from pathlib import Path
from logger import logger  # 统一日志

# ============================================================
# Edge-TTS 引擎（推荐：免费、中文质量好、无需GPU）
# ============================================================

class EdgeTTSEngine:
    """Edge-TTS 语音合成引擎 — 微软免费TTS，中文自然度高"""

    def __init__(self, voice: str = "zh-CN-XiaoxiaoNeural", rate: str = "+0%"):
        """
        Args:
            voice: 发音人
                - zh-CN-XiaoxiaoNeural (女声，活泼，推荐)
                - zh-CN-YunxiNeural (男声，新闻播报风格)
                - zh-CN-YunjianNeural (男声，沉稳)
                - zh-CN-XiaoyiNeural (女声，温柔)
            rate: 语速，如 "+10%" 加快，"-10%" 减慢
        """
        self.voice = voice
        self.rate = rate

    def _get_voices(self) -> list:
        """获取所有可用中文发音人列表"""
        return [
            {"id": "zh-CN-XiaoxiaoNeural", "gender": "Female", "style": "活泼自然"},
            {"id": "zh-CN-YunxiNeural", "gender": "Male", "style": "新闻播报"},
            {"id": "zh-CN-YunjianNeural", "gender": "Male", "style": "沉稳专业"},
            {"id": "zh-CN-XiaoyiNeural", "gender": "Female", "style": "温柔亲切"},
            {"id": "zh-CN-YunyangNeural", "gender": "Male", "style": "新闻播音"},
            {"id": "zh-CN-XiaochenNeural", "gender": "Female", "style": "自然对话"},
        ]

    def synthesize(self, text: str, output_path: str = None) -> str:
        """
        将文本合成语音，返回音频文件路径

        Args:
            text: 要合成的文本
            output_path: 输出音频路径（可选，默认生成临时文件）

        Returns:
            str: 音频文件路径 (.mp3)
        """
        if output_path is None:
            output_path = tempfile.mktemp(suffix=".mp3")

        # Edge-TTS 是 async API，用 asyncio 运行
        loop = asyncio.new_event_loop()
        try:
            result_path = loop.run_until_complete(
                self._async_synthesize(text, output_path)
            )
            return result_path
        finally:
            loop.close()

    async def _async_synthesize(self, text: str, output_path: str) -> str:
        """异步执行 Edge-TTS 合成"""
        import edge_tts

        # 创建 TTS 通信对象
        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
        )

        # 保存为 mp3 文件
        await communicate.save(output_path)
        return output_path

    def synthesize_sync(self, text: str, output_path: str = None) -> str:
        """同步版本（别名）"""
        return self.synthesize(text, output_path)


# ============================================================
# Paddle TTS 引擎（可选：离线、可定制、需额外安装）
# ============================================================

class PaddleTTSEngine:
    """Paddle TTS 引擎 — 百度开源，支持中文，可离线使用"""

    def __init__(self, model_name: str = "fastspeech2_mix"):
        """
        Args:
            model_name: 模型名称
                - fastspeech2_mix (中英混合)
                - fastspeech2_canton (粤语)
        """
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        """延迟加载模型（首次使用时）"""
        if self._model is None:
            try:
                from paddlespeech.cli.tts import TTSExecutor
                self._model = TTSExecutor()
                logger.info(f"Paddle TTS 模型加载完成: {self.model_name}")
            except ImportError:
                raise ImportError(
                    "Paddle TTS 未安装。请运行: pip install paddlespeech"
                )
            except Exception as e:
                raise RuntimeError(f"Paddle TTS 加载失败: {e}")
        return self._model

    def synthesize(self, text: str, output_path: str = None) -> str:
        """合成语音，返回 wav 文件路径"""
        if output_path is None:
            output_path = tempfile.mktemp(suffix=".wav")

        tts = self._load_model()
        tts(text=text, output=output_path)
        return output_path


# ============================================================
# TTS 工厂函数 — 统一入口
# ============================================================

# 全局 TTS 引擎实例（懒加载）
_tts_engine = None

def get_tts_engine(engine_type: str = "edge", **kwargs):
    """
    获取 TTS 引擎实例

    Args:
        engine_type: "edge" (推荐) 或 "paddle"
        **kwargs: 传递给引擎的额外参数

    Returns:
        EdgeTTSEngine 或 PaddleTTSEngine 实例
    """
    global _tts_engine

    if engine_type == "edge":
        voice = kwargs.get("voice", "zh-CN-XiaoxiaoNeural")
        rate = kwargs.get("rate", "+5%")
        _tts_engine = EdgeTTSEngine(voice=voice, rate=rate)
    elif engine_type == "paddle":
        _tts_engine = PaddleTTSEngine(**kwargs)
    else:
        raise ValueError(f"不支持的 TTS 引擎: {engine_type}")

    return _tts_engine


def text_to_speech(text: str, output_dir: str = None, engine: str = "edge") -> str:
    """
    便捷函数：将文本转为语音文件

    Args:
        text: 输入文本
        output_dir: 输出目录（可选）
        engine: TTS 引擎类型

    Returns:
        str: 音频文件路径
    """
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        fname = f"tts_{int(time.time()*1000)}.mp3"
        output_path = os.path.join(output_dir, fname)
    else:
        output_path = None

    tts = get_tts_engine(engine)
    return tts.synthesize(text, output_path)


# ============================================================
# 测试
# ============================================================

if __name__ == "__main__":
    # 测试 Edge-TTS
    logger.info("=" * 50)
    logger.info("TTS 引擎测试")
    logger.info("=" * 50)

    test_text = "景顺长城中短债债券C基金在2021年3月31日的前三大持仓债券分别是：20国开12、21国债01和20农发05。"

    logger.info(f"测试文本: {test_text}")
    logger.info("合成中...")

    tts = get_tts_engine("edge", voice="zh-CN-YunxiNeural")
    audio_path = tts.synthesize(test_text, "test_tts_output.mp3")

    logger.info(f"音频已保存: {audio_path}")
    logger.info(f"文件大小: {os.path.getsize(audio_path) / 1024:.1f} KB")
