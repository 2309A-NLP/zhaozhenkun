# -*- coding: utf-8 -*-
"""
==============================================================================
功能说明：工具函数模块
==============================================================================
本文件包含项目通用的工具函数：
  - load_image(): 加载图像文件并进行格式转换
  - save_image(): 保存图像到指定路径
  - resize_image(): 按比例或指定尺寸缩放图像
  - create_comparison_grid(): 将多张图像拼接为对比网格
  - add_text_label(): 在图像上方添加文字标签
  - setup_logging(): 配置项目日志系统
  - get_timestamp(): 获取当前时间戳字符串

工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
==============================================================================
"""

import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from typing import List, Tuple, Optional
import logging

from config import LOG_LEVEL, LOG_FORMAT, OUTPUT_DIR, setup_logging


def get_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def load_image(file_path: str) -> Optional[np.ndarray]:
    if not os.path.exists(file_path):
        logging.error(f"图像文件不存在: {file_path}")
        return None
    try:
        # 用 numpy 读取原始字节再解码，避免 cv2.imread 的中文路径问题
        with open(file_path, "rb") as f:
            raw = np.frombuffer(f.read(), dtype=np.uint8)
        image = cv2.imdecode(raw, cv2.IMREAD_COLOR)
        if image is None:
            logging.error(f"图像解码失败: {file_path}")
            return None
        logging.info(f"图像加载成功: {file_path}, 尺寸: {image.shape}")
        return image
    except Exception as e:
        logging.error(f"加载图像时出错: {e}")
        return None


def save_image(image: np.ndarray, file_path: str, quality: int = 95) -> bool:
    """保存图像到指定路径，并输出更明确的失败原因"""
    try:
        directory = os.path.dirname(file_path)
        os.makedirs(directory, exist_ok=True)

        if image is None:
            raise ValueError("待保存图像为 None")
        if not isinstance(image, np.ndarray):
            raise TypeError(f"待保存对象不是 numpy 数组，而是 {type(image)}")
        if image.size == 0:
            raise ValueError("待保存图像为空数组")
        if image.ndim not in (2, 3):
            raise ValueError(f"待保存图像维度异常: ndim={image.ndim}, shape={image.shape}")

        ext = os.path.splitext(file_path)[1].lower()
        if ext in [".jpg", ".jpeg"]:
            params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        elif ext == ".png":
            params = [cv2.IMWRITE_PNG_COMPRESSION, 3]
        else:
            params = []

        image_to_save = image.copy()
        if image_to_save.dtype != np.uint8:
            if image_to_save.max() <= 1.0:
                image_to_save = (image_to_save * 255).clip(0, 255).astype(np.uint8)
            else:
                image_to_save = image_to_save.clip(0, 255).astype(np.uint8)

        success, encoded = cv2.imencode(ext or ".png", image_to_save, params)
        if not success or encoded is None:
            raise ValueError(
                f"OpenCV 编码失败: ext={ext}, shape={image_to_save.shape}, dtype={image_to_save.dtype}"
            )

        with open(file_path, "wb") as f:
            f.write(encoded.tobytes())

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件写入后未找到: {file_path}")

        logging.info(f"图像保存成功: {file_path}, shape={image_to_save.shape}, dtype={image_to_save.dtype}")
        return True
    except Exception as e:
        logging.error(f"保存图像时出错: {file_path} | {e}")
        return False


def resize_image(image: np.ndarray, width: Optional[int] = None, height: Optional[int] = None, scale: Optional[float] = None) -> np.ndarray:
    h, w = image.shape[:2]
    if scale is not None:
        new_w = int(w * scale)
        new_h = int(h * scale)
    elif width is not None and height is not None:
        new_w, new_h = width, height
    elif width is not None:
        new_w = width
        new_h = int(h * (width / w))
    elif height is not None:
        new_h = height
        new_w = int(w * (height / h))
    else:
        return image
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
    logging.info(f"图像缩放: {w}x{h} -> {new_w}x{new_h}")
    return resized


def add_text_label(image: np.ndarray, text: str, position: str = "top") -> np.ndarray:
    h, w = image.shape[:2]
    label_height = 40
    label = np.ones((label_height, w, 3), dtype=np.uint8) * 255
    label_pil = Image.fromarray(cv2.cvtColor(label, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(label_pil)
    font_size = 20
    font = None
    # Try multiple font paths (Windows + WSL/Linux)
    font_candidates = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/mnt/c/Windows/Fonts/msyh.ttc",
        "/mnt/c/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for fpath in font_candidates:
        if os.path.exists(fpath):
            try:
                font = ImageFont.truetype(fpath, font_size)
                break
            except Exception:
                continue
    if font is None:
        try:
            font = ImageFont.load_default()
        except Exception:
            font = None

    # Draw label - skip text if no usable font
    if font is not None:
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            text_x = (w - text_w) // 2
            text_y = (label_height - text_h) // 2
            draw.text((text_x, text_y), text, fill=(0, 0, 0), font=font)
        except (UnicodeEncodeError, Exception):
            pass  # skip text if font can't render it
    label_np = cv2.cvtColor(np.array(label_pil), cv2.COLOR_RGB2BGR)
    if position == "top":
        return np.vstack([label_np, image])
    return np.vstack([image, label_np])


def create_comparison_grid(images: List[np.ndarray], labels: List[str], cols: int = 3) -> np.ndarray:
    if len(images) != len(labels):
        raise ValueError("图像数量与标签数量不匹配")
    target_h = max(img.shape[0] for img in images)
    target_w = max(img.shape[1] for img in images)
    resized_images = []
    for index, img in enumerate(images):
        resized = cv2.resize(img, (target_w, target_h))
        labeled = add_text_label(resized, labels[index])
        resized_images.append(labeled)
    rows = []
    for i in range(0, len(resized_images), cols):
        row_images = resized_images[i:i + cols]
        while len(row_images) < cols:
            blank = np.ones_like(row_images[0]) * 255
            row_images.append(blank)
        rows.append(np.hstack(row_images))
    return np.vstack(rows)
