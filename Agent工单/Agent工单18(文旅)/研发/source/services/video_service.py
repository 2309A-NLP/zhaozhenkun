"""工单18：视频服务，负责多帧抽取、关键帧OCR与视频讲解摘要生成。"""
import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from services.ocr_service import extract_text_from_image
from services.vision_service import describe_image_in_detail

# 工单18：用ffmpeg从视频中抽取多张代表帧，提升视频讲解稳定性。
def extract_key_frames(video_path: str, output_dir: str) -> list:
    output_pattern = str(Path(output_dir) / "frame_%02d.jpg")
    subprocess.run(["ffmpeg", "-y", "-i", video_path, "-vf", "fps=1/2", "-frames:v", "3", output_pattern], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return sorted(Path(output_dir).glob("frame_*.jpg"))

# 工单18：汇总多帧视觉结果和OCR结果，用于后续视频讲解。
def analyze_video(settings: dict, video_bytes: bytes, suffix: str = ".mp4") -> dict:
    with TemporaryDirectory() as temp_dir:
        video_path = Path(temp_dir) / f"input{suffix}"
        video_path.write_bytes(video_bytes)
        frame_paths = extract_key_frames(str(video_path), temp_dir)
        summaries, ocr_results = [], []
        for frame_path in frame_paths:
            frame_bytes = frame_path.read_bytes()
            summaries.append(describe_image_in_detail(settings, frame_bytes, "image/jpeg"))
            ocr_results.append(extract_text_from_image(frame_bytes))
        frame_summary = "；".join(part for part in summaries if part)
        ocr_text = "；".join(part for part in ocr_results if part)
        return {"frame_summary": frame_summary, "ocr_text": ocr_text, "frame_count": len(frame_paths), "summary_text": json.dumps({"frame_summary": frame_summary, "ocr_text": ocr_text, "frame_count": len(frame_paths)}, ensure_ascii=False)}
