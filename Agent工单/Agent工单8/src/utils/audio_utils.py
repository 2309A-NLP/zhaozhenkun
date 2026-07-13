"""
src/utils/audio_utils.py - 音频处理工具函数
功能: 提供音频格式转换、静音检测、声道转换等基础音频处理功能。
      支持 PCM 16-bit 整数与 float32 之间的转换，以及重采样操作。
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import numpy as np               # 数值计算，音频数据处理
import struct                    # 二进制数据打包/解包（PCM 字节 ↔ 浮点数组）
import logging                   # 日志记录

logger = logging.getLogger(__name__)  # 获取当前模块的 logger


def pcm_bytes_to_float32(pcm_bytes: bytes) -> np.ndarray:
    """
    将 PCM S16LE 字节流转换为 float32 的 numpy 数组，值范围归一化到 [-1.0, 1.0]。

    参数:
        pcm_bytes: 原始 PCM 16-bit 小端字节流
    返回:
        shape 为 (n_samples,) 的 float32 数组
    """
    # 将字节转换为 16-bit 有符号整数数组
    n_samples = len(pcm_bytes) // 2  # 每个采样 2 字节
    # struct.unpack 批量解析为有符号 short
    int_samples = struct.unpack(f"<{n_samples}h", pcm_bytes)
    # 归一化到 [-1.0, 1.0]，除以 32768 (2^15)
    float_samples = np.array(int_samples, dtype=np.float32) / 32768.0
    return float_samples


def float32_to_pcm_bytes(float_samples: np.ndarray) -> bytes:
    """
    将 float32 numpy 数组转换为 PCM S16LE 字节流。

    参数:
        float_samples: float32 数组，值范围 [-1.0, 1.0]
    返回:
        PCM 16-bit 小端字节流
    """
    # 从 [-1, 1] 缩放到 [-32768, 32767] 并转为 16-bit 整数
    int_samples = np.clip(float_samples * 32767.0, -32768, 32767).astype(np.int16)
    # 打包为小端字节流
    return int_samples.tobytes()


def compute_rms_energy(audio: np.ndarray, window_size: int = 400) -> np.ndarray:
    """
    计算滑动窗口的 RMS (Root Mean Square) 能量值，用于语音活动检测(VAD)。

    参数:
        audio: 音频信号数组（float32, 采样率 16000）
        window_size: 滑动窗口大小（采样点数），默认 400 = 25ms @ 16kHz
    返回:
        与输入等长的 RMS 能量数组，边界处用零填充
    """
    # 平方信号（保留符号，平方后全为正）
    squared = audio ** 2
    # 使用移动平均计算窗口内均方值
    kernel = np.ones(window_size) / window_size  # 均值滤波器
    rms = np.sqrt(np.convolve(squared, kernel, mode='same'))  # 卷积实现滑动平均
    return rms.astype(np.float32)


def detect_silence(audio: np.ndarray, threshold: float = 0.02,
                   min_silence_ms: int = 300, sample_rate: int = 16000) -> bool:
    """
    检测音频片段是否包含足够长的静音区间。
    用于触发空闲视频切换。

    参数:
        audio: 音频信号 (float32 数组)
        threshold: RMS 能量阈值，低于此值视为静音
        min_silence_ms: 最小连续静音时长（毫秒）
        sample_rate: 采样率
    返回:
        True 表示检测到长时间静音
    """
    # 计算 RMS 能量
    rms = compute_rms_energy(audio)
    # 找到低于阈值的区域
    silent_mask = rms < threshold
    # 计算最长连续静音帧数
    min_silence_frames = int(min_silence_ms * sample_rate / 1000)
    # 遍历寻找连续静音段
    max_consecutive = 0
    current_run = 0
    for is_silent in silent_mask:
        if is_silent:
            current_run += 1
            max_consecutive = max(max_consecutive, current_run)
        else:
            current_run = 0
    return max_consecutive >= min_silence_frames


def resample_audio(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """
    将音频从原始采样率重采样到目标采样率（简单线性插值实现）。
    对于高质量需求，建议使用 librosa.resample，此函数用于不依赖 librosa 的轻量场景。

    参数:
        audio: 输入音频 (float32)
        orig_sr: 原始采样率
        target_sr: 目标采样率
    返回:
        重采样后的音频
    """
    if orig_sr == target_sr:
        return audio  # 无需重采样

    # 计算新采样点数
    ratio = target_sr / orig_sr
    n_out = int(len(audio) * ratio)
    # 使用 numpy 线性插值进行采样率转换
    x_orig = np.arange(len(audio)) / orig_sr      # 原始时间轴(秒)
    x_target = np.arange(n_out) / target_sr         # 目标时间轴(秒)
    resampled = np.interp(x_target, x_orig, audio)  # 线性插值重采样
    return resampled.astype(np.float32)


def float32_to_wav_bytes(audio: np.ndarray, sample_rate: int = 16000) -> bytes:
    """
    将float32音频数组转换为WAV格式字节流(含44字节头)。
    参数:
        audio: float32数组, [-1.0, 1.0], 单声道
        sample_rate: 采样率(默认16kHz)
    返回: 完整WAV文件字节流
    """
    import io, wave
    buf = io.BytesIO()
    # 写入WAV文件
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)          # 单声道
        wf.setsampwidth(2)          # 16-bit
        wf.setframerate(sample_rate)
        # float32→int16
        samples = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
        wf.writeframes(samples.tobytes())
    buf.seek(0)
    return buf.read()
