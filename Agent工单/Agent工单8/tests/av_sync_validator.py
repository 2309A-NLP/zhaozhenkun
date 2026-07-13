#!/usr/bin/env python3
"""
tests/av_sync_validator.py — 音视频同步精度测量工具
功能: 分析生成的数字人视频, 计算音频波形峰值与口型开合度之间的时间偏移。
      验证工单需求: "音频与嘴型同步误差不超过0.1秒"

用法:
  python tests/av_sync_validator.py output/reply_xxxx.mp4
  python tests/av_sync_validator.py output/ --batch  # 批量分析

输出: 同步偏移量(ms), 是否达标(≤100ms)

工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import sys, os, argparse, logging, json
import numpy as np
import subprocess

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("av_sync")


def extract_audio(video_path: str) -> np.ndarray:
    """用FFmpeg提取音频为16kHz float32 PCM数组。"""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pcm", delete=False) as tmp_file:
        tmp = tmp_file.name
    try:
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", video_path,
            "-f", "s16le", "-ar", "16000", "-ac", "1", tmp,
        ], check=True)
        with open(tmp, "rb") as f:
            audio = np.frombuffer(f.read(), dtype=np.int16).astype(np.float32) / 32768.0
        return audio
    finally:
        os.remove(tmp)


def extract_video_frames(video_path: str) -> list:
    """用OpenCV提取视频帧列表(BGR)。"""
    import cv2
    frames = []
    cap = cv2.VideoCapture(video_path)
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)
    cap.release()
    return frames


def compute_mouth_openness(frames: list) -> np.ndarray:
    """
    计算每帧的嘴部开合度。
    使用下半脸区域(口部)的灰度方差作为代理指标。
    方差越大→嘴张得越大→口型越明显。
    返回: 归一化数组 [0,1]
    """
    openness = []
    for frame in frames:
        h, w = frame.shape[:2]
        # 取下半脸区域(嘴部大致在图像下半部分的中间区域)
        mouth_roi = frame[int(h * 0.55):int(h * 0.85), int(w * 0.3):int(w * 0.7)]
        gray = np.mean(mouth_roi, axis=2)  # BGR→灰度
        # 局部方差作为口型开合度代理
        var = float(np.var(gray))
        openness.append(var)
    arr = np.array(openness, dtype=np.float32)
    if arr.max() > 0:
        arr = arr / arr.max()  # 归一化到[0,1]
    return arr


def compute_audio_energy(audio: np.ndarray, fps: int = 25) -> np.ndarray:
    """
    计算音频逐帧能量(与视频帧对齐)。
    每帧音频长度 = sample_rate / fps = 16000/25 = 640采样点
    返回: 归一化能量数组
    """
    samples_per_frame = 16000 // fps  # 640
    n_frames = len(audio) // samples_per_frame
    energy = []
    for i in range(n_frames):
        chunk = audio[i * samples_per_frame:(i + 1) * samples_per_frame]
        energy.append(float(np.sqrt(np.mean(chunk ** 2))))  # RMS能量
    arr = np.array(energy, dtype=np.float32)
    if arr.max() > 0:
        arr = arr / arr.max()
    return arr


def cross_correlation(x: np.ndarray, y: np.ndarray) -> tuple:
    """
    计算两个信号的互相关, 找到最佳偏移量。
    正偏移→音频领先视频, 负偏移→视频领先音频。
    返回: (best_offset_frames, correlation_peak, offset_ms)
    """
    # 对齐长度
    min_len = min(len(x), len(y))
    x, y = x[:min_len], y[:min_len]
    # 归一化互相关
    x_norm = (x - x.mean()) / (x.std() + 1e-8)
    y_norm = (y - y.mean()) / (y.std() + 1e-8)
    corr = np.correlate(x_norm, y_norm, mode='full')
    # 最佳偏移
    best_idx = np.argmax(np.abs(corr))
    lag_frames = best_idx - (len(y_norm) - 1)
    corr_peak = float(corr[best_idx]) / (len(x_norm) * x_norm.std() * y_norm.std() + 1e-8)
    offset_ms = (lag_frames / 25.0) * 1000  # 帧→毫秒(25fps)
    return lag_frames, corr_peak, offset_ms


def validate_video(video_path: str) -> dict:
    """
    验证单个视频的音视频同步精度。
    返回: {"path": str, "offset_ms": float, "pass": bool, "frames": int, "duration_s": float}
    """
    logger.info(f"分析: {video_path}")
    try:
        audio = extract_audio(video_path)
        frames = extract_video_frames(video_path)
    except Exception as e:
        logger.error(f"  提取失败: {e}")
        return {"path": video_path, "error": str(e)}

    if len(frames) < 10 or len(audio) < 16000:
        return {"path": video_path, "error": "视频/音频太短(<1s)"}

    mouth = compute_mouth_openness(frames)
    energy = compute_audio_energy(audio)
    lag, peak, offset_ms = cross_correlation(energy, mouth)

    passed = abs(offset_ms) <= 100  # ±100ms = 0.1s阈值

    result = {
        "path": video_path,
        "frames": len(frames),
        "duration_s": round(len(audio) / 16000.0, 2),
        "offset_ms": round(offset_ms, 1),
        "offset_frames": lag,
        "correlation": round(peak, 3),
        "pass": passed,
        "threshold_ms": 100,
        "result": "✅ 达标" if passed else f"❌ 超标(偏移{abs(offset_ms):.0f}ms > 100ms)"
    }
    logger.info(f"  {result['result']} | 偏移={result['offset_ms']}ms | "
               f"相关性={result['correlation']} | {result['frames']}帧 {result['duration_s']}s")
    return result


def batch_validate(directory: str) -> list:
    """批量验证目录下所有MP4视频。"""
    results = []
    for f in sorted(os.listdir(directory)):
        if f.endswith(".mp4"):
            results.append(validate_video(os.path.join(directory, f)))
    return results


def main():
    parser = argparse.ArgumentParser(description="音视频同步精度测量工具")
    parser.add_argument("input", help="视频文件路径或目录")
    parser.add_argument("--batch", action="store_true", help="批量模式(目录)")
    parser.add_argument("--output", help="结果JSON输出路径")
    args = parser.parse_args()

    if args.batch or os.path.isdir(args.input):
        results = batch_validate(args.input)
    else:
        results = [validate_video(args.input)]

    # 汇总
    valid = [r for r in results if "error" not in r]
    if valid:
        passed = sum(1 for r in valid if r["pass"])
        offsets = [abs(r["offset_ms"]) for r in valid]
        logger.info(f"\n{'='*50}")
        logger.info(f"📊 汇总: {passed}/{len(valid)} 达标")
        logger.info(f"   平均偏移: {np.mean(offsets):.1f}ms")
        logger.info(f"   最大偏移: {np.max(offsets):.1f}ms")
        logger.info(f"   阈值: ≤100ms (0.1s)")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"结果已保存: {args.output}")

    # 返回码: 全部达标→0, 有超标→1
    all_pass = all(r.get("pass", False) for r in valid) if valid else False
    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
