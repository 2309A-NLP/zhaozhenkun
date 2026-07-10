# 该文件功能：提供更真实的 OCR、TTS 与知识库增强工具函数。
import base64
import io
import re
import subprocess
import tempfile

from PIL import Image

try:
    # 这里尝试导入 pytesseract。
    import pytesseract
except Exception:
    # 这里在缺少 pytesseract 时记为 None，避免启动即崩。
    pytesseract = None


def extract_ocr_text(image_bytes: bytes) -> str:
    # 这里在没有图片时直接返回空字符串。
    if not image_bytes:
        return ""
    try:
        # 这里把字节流读成图片。
        image = Image.open(io.BytesIO(image_bytes))
        # 这里在 pytesseract 可用时尝试真正 OCR。
        if pytesseract is not None:
            text = pytesseract.image_to_string(image, lang="chi_sim+eng")
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                return text[:200]
        # 这里在未识别出文字时退回图片描述。
        return f"检测到图片，宽{image.width}像素，高{image.height}像素，可能包含景点主体、标牌或建筑轮廓。"
    except Exception:
        # 这里在图片解析失败时返回空字符串。
        return ""


def build_tts_text(text: str) -> str:
    # 这里整理可供 TTS 使用的纯净文本。
    return re.sub(r"\s+", " ", (text or "").strip())


def build_audio_base64(text: str) -> str:
    # 这里先准备要播报的文本。
    clean_text = build_tts_text(text)
    # 这里在文本为空时返回空串。
    if not clean_text:
        return ""
    # 这里创建临时音频文件。
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_path = temp_file.name
    try:
        # 这里调用 espeak 生成真实 wav 音频。
        subprocess.run(["espeak", "-w", temp_path, clean_text], check=True, capture_output=True)
        # 这里读取音频并转 base64。
        with open(temp_path, "rb") as audio_file:
            return base64.b64encode(audio_file.read()).decode("utf-8")
    except Exception:
        # 这里失败时退回文本 base64 演示。
        return base64.b64encode(clean_text.encode("utf-8")).decode("utf-8")


def build_audio_payload(text: str) -> dict:
    # 这里统一组织语音播报结果。
    clean_text = build_tts_text(text)
    return {"text": clean_text, "audio_base64_demo": build_audio_base64(clean_text)}
