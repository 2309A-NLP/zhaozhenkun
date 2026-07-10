"""工单18：OCR服务 — 优先 PaddleOCR，降级 Tesseract，对图片文字做真实提取。"""
import cv2
import numpy as np
from PIL import Image

# 工单18：PaddleOCR 懒加载，避免启动时因缺少依赖而崩溃。
_PADDLE_OCR = None

def _get_paddle_ocr():
    global _PADDLE_OCR
    if _PADDLE_OCR is not None:
        return _PADDLE_OCR
    try:
        from paddleocr import PaddleOCR
        _PADDLE_OCR = PaddleOCR(lang="ch", use_angle_cls=True, show_log=False)
        return _PADDLE_OCR
    except Exception:
        return None

# 工单18：把原始图片字节解码成 OpenCV 图像数组。
def decode_image(image_bytes: bytes):
    data = np.frombuffer(image_bytes, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR)

# 工单18：图像预处理 — 灰度化、自适应阈值、放大，提高识别率。
def preprocess_image(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11)
    return cv2.resize(binary, None, fx=1.8, fy=1.8, interpolation=cv2.INTER_CUBIC)

# 工单18：PaddleOCR 识别 — PDF 指定的 OCR 引擎。
def _paddle_ocr_extract(image_bytes: bytes) -> str:
    ocr = _get_paddle_ocr()
    if ocr is None:
        return ""
    image = decode_image(image_bytes)
    if image is None:
        return ""
    try:
        results = ocr.ocr(image, cls=True)
        if not results or not results[0]:
            return ""
        lines = []
        for line in results[0]:
            text = line[1][0] if len(line) > 1 else ""
            if text and text.strip():
                lines.append(text.strip())
        return " ".join(lines)
    except Exception:
        return ""

# 工单18：Tesseract 降级识别 — 当 PaddleOCR 不可用时的备用方案。
def _tesseract_extract(image_bytes: bytes) -> str:
    import pytesseract
    image = decode_image(image_bytes)
    if image is None:
        return ""
    processed = preprocess_image(image)
    pil_image = Image.fromarray(processed)
    text = pytesseract.image_to_string(pil_image, lang="chi_sim+eng", config="--psm 6")
    return " ".join(part.strip() for part in text.splitlines() if part.strip())

# 工单18：统一 OCR 入口 — 优先 PaddleOCR（PDF要求），降级 Tesseract。
def extract_text_from_image(image_bytes: bytes) -> str:
    if not image_bytes:
        return ""
    # 工单18：优先使用 PaddleOCR
    result = _paddle_ocr_extract(image_bytes)
    if result:
        return result
    # 工单18：降级到 Tesseract
    return _tesseract_extract(image_bytes)
