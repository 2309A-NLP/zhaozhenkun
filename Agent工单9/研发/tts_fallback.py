# -*- coding: utf-8 -*-
"""
tts_fallback.py — EdgeTTS 回退方案 + 音频格式解码工具
--------------------------------------------------------------
功能: 当 GPT-SoVITS 服务不可用时，提供 EdgeTTS 兜底语音合成。
      以及 WAV/MP3/PCM 多格式音频解码工具（含 FFmpeg 最终兜底）。

被 tts_engine.py 的 GPTSovitsEngine 调用。

工单编号: 人工智能NLP-Agent数字人项目-数字人与智能体的集成任务
所属目录: 研发
"""
import os, tempfile, subprocess, logging, asyncio  # 标准库
import numpy as np                                  # 音频数组处理

logger = logging.getLogger("tts")


# ================================================================
# EdgeTTS 回退合成（异步版本）
# ================================================================
async def edge_tts_synthesize(text: str) -> np.ndarray:
    """EdgeTTS 异步合成 → MP3 → float32 数组。

    参数:
        text: 待合成文本
    返回:
        float32 音频数组，16kHz 单声道；失败返回空数组
    """
    try:
        import edge_tts
        comm = edge_tts.Communicate(text=text, voice="zh-CN-XiaoxiaoNeural")
        chunks = []
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])            # 收集音频数据块
        if chunks:
            mp3_data = b"".join(chunks)                 # 合并为完整 MP3
            return mp3_to_float32(mp3_data)             # 解码为 float32
    except ImportError:
        logger.warning("EdgeTTS未安装，无法回退。安装: pip install edge-tts")
    except Exception as e:
        logger.error("EdgeTTS回退失败: %s", e)
    return np.array([], dtype=np.float32)


# ================================================================
# EdgeTTS 回退合成（同步版本 — Flask 使用）
# ================================================================
def edge_tts_synthesize_sync(text: str) -> np.ndarray:
    """EdgeTTS 同步合成 → MP3 → float32 数组。

    参数:
        text: 待合成文本
    返回:
        float32 音频数组，16kHz 单声道
    """
    try:
        import edge_tts
        async def _run():
            comm = edge_tts.Communicate(text=text, voice="zh-CN-XiaoxiaoNeural")
            chunks = []
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    chunks.append(chunk["data"])
            return b"".join(chunks)
        mp3_data = asyncio.run(_run())                  # 在同步代码中运行异步
        if mp3_data:
            return mp3_to_float32(mp3_data)
    except ImportError:
        pass
    except Exception as e:
        logger.error("EdgeTTS同步回退失败: %s", e)
    return np.array([], dtype=np.float32)


# ================================================================
# 音频格式解码工具
# ================================================================
def wav_to_float32(wav_data: bytes, target_sr: int = 16000) -> np.ndarray:
    """WAV 字节流 → float32 numpy 数组（按需重采样）。

    参数:
        wav_data: WAV 格式原始字节
        target_sr: 目标采样率，默认 16000
    返回:
        float32 音频数组
    """
    try:
        import io, wave
        with wave.open(io.BytesIO(wav_data), 'rb') as wf:
            n_frames = wf.getnframes()                  # 总帧数
            sr = wf.getframerate()                      # 原始采样率
            pcm = wf.readframes(n_frames)               # PCM数据
            samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
            # 重采样到目标采样率
            if sr != target_sr and len(samples) > 0:
                try:
                    import librosa
                    samples = librosa.resample(samples, orig_sr=sr, target_sr=target_sr)
                except ImportError:
                    logger.warning("librosa未安装，跳过重采样(sr=%d→%d)", sr, target_sr)
            return samples.astype(np.float32)
    except Exception as e:
        logger.error("WAV解码失败: %s", e)
        return ffmpeg_decode(wav_data, input_fmt="wav")  # FFmpeg兜底


def mp3_to_float32(mp3_data: bytes, target_sr: int = 16000) -> np.ndarray:
    """MP3 → float32（EdgeTTS 回退用）。

    参数:
        mp3_data: MP3 格式原始字节
        target_sr: 目标采样率
    返回:
        float32 音频数组
    """
    return ffmpeg_decode(mp3_data, input_fmt="mp3", target_sr=target_sr)


def ffmpeg_decode(data: bytes, input_fmt: str = "wav",
                  target_sr: int = 16000) -> np.ndarray:
    """FFmpeg 音频解码 → 16kHz PCM float32（最终兜底方案）。

    参数:
        data: 原始音频字节
        input_fmt: 输入格式（wav/mp3等）
        target_sr: 目标采样率
    返回:
        float32 音频数组
    """
    # 写入临时文件
    with tempfile.NamedTemporaryFile(suffix=f".{input_fmt}", delete=False) as f:
        f.write(data)
        in_path = f.name
    out_path = in_path + ".pcm"                             # 临时输出路径
    try:
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", in_path,                                  # 输入文件
            "-f", "s16le", "-acodec", "pcm_s16le",          # 输出格式: 16-bit PCM
            "-ar", str(target_sr), "-ac", "1",              # 16kHz 单声道
            out_path,
        ], check=True, timeout=10)
        with open(out_path, "rb") as f:
            pcm = f.read()
        samples = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        return samples
    except Exception as e:
        logger.error("FFmpeg解码失败: %s", e)
        return np.array([], dtype=np.float32)
    finally:
        # 清理临时文件
        for p in [in_path, out_path]:
            if os.path.exists(p):
                os.remove(p)
