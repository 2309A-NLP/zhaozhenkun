# -*- coding: utf-8 -*-
"""
==============================================================================
功能说明：千问图像编辑工具函数模块
==============================================================================
本文件提供千问 Qwen-Image-Edit 模型所需的图像处理工具函数：
  - image_to_base64(): 将图像（路径/numpy/PIL）转为 Base64 格式
  - url_to_image(): 从 URL 下载图像并转为 numpy BGR 数组
  - save_edited_images(): 批量下载并保存 API 返回的图像

依赖：cv2, numpy, PIL, requests

工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
==============================================================================
"""

import io  # 内存字节流
import os  # 路径处理
import base64  # Base64 编解码
import logging  # 日志
from typing import List, Optional, Union  # 类型提示
from datetime import datetime  # 时间戳

import cv2  # OpenCV 图像处理
import numpy as np  # 数值数组
import requests  # HTTP 下载
from PIL import Image  # PIL 图像处理

logger = logging.getLogger(__name__)  # 模块日志器


def image_to_base64(image: Union[str, np.ndarray, Image.Image]) -> str:
    """将图像转换为 DashScope API 所需的 Base64 格式

    支持三种输入：
      - 文件路径 (str): 直接读取文件
      - numpy BGR 数组 (np.ndarray): 先转 RGB 再编码为 PNG
      - PIL Image: 直接编码为 PNG

    Returns:
        "data:{mime_type};base64,{base64_data}" 格式字符串
    """
    # 情况1：文件路径
    if isinstance(image, str):
        with open(image, "rb") as f:
            raw = f.read()  # 读取原始字节
        ext = os.path.splitext(image)[1].lower()  # 取扩展名
        mime_map = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".png": "image/png", ".webp": "image/webp",
            ".bmp": "image/bmp", ".tiff": "image/tiff",
            ".gif": "image/gif",
        }
        mime_type = mime_map.get(ext, "image/png")  # 默认 PNG
        raw_bytes = raw

    # 情况2：numpy BGR 数组
    elif isinstance(image, np.ndarray):
        if image.shape[2] == 3:
            img_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)  # BGR→RGB
        else:
            img_rgb = image  # 已是 RGB 或灰度
        pil_img = Image.fromarray(img_rgb)  # numpy→PIL
        buf = io.BytesIO()
        pil_img.save(buf, format="PNG")  # 编码为 PNG
        raw_bytes = buf.getvalue()
        mime_type = "image/png"

    # 情况3：PIL Image
    elif isinstance(image, Image.Image):
        buf = io.BytesIO()
        image.save(buf, format="PNG")  # 编码为 PNG
        raw_bytes = buf.getvalue()
        mime_type = "image/png"

    else:
        raise TypeError(f"不支持的图像类型: {type(image)}")

    # Base64 编码
    b64_data = base64.b64encode(raw_bytes).decode("utf-8")
    return f"data:{mime_type};base64,{b64_data}"


def url_to_image(url: str, timeout: int = 30) -> Optional[np.ndarray]:
    """从 URL 下载图像并转为 numpy BGR 数组

    API 返回的图像 URL 有效期仅 24 小时，需及时下载。
    """
    try:
        resp = requests.get(url, timeout=timeout)  # HTTP 下载
        resp.raise_for_status()  # 检查 HTTP 错误
        raw = np.frombuffer(resp.content, dtype=np.uint8)  # 字节→numpy
        img = cv2.imdecode(raw, cv2.IMREAD_COLOR)  # 解码为 BGR
        if img is None:
            logger.error(f"URL 图像解码失败: {url[:80]}...")
        return img
    except Exception as e:
        logger.error(f"下载图像失败: {url[:80]}... | {e}")
        return None


def save_edited_images(
    urls: List[str],
    output_dir: str,
    prefix: str = "qwen_edit",
) -> List[str]:
    """下载并保存 Qwen 编辑后的图像到本地

    遍历 URL 列表，逐个下载并保存为 PNG 文件。
    文件名格式: {prefix}_{序号}_{时间戳}.png
    """
    os.makedirs(output_dir, exist_ok=True)  # 确保目录存在
    saved = []  # 已保存路径列表
    for i, url in enumerate(urls):
        img = url_to_image(url)  # 下载图像
        if img is None:
            continue  # 跳过下载失败的
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")  # 时间戳
        fname = f"{prefix}_{i}_{ts}.png"  # 文件名
        fpath = os.path.join(output_dir, fname)  # 完整路径
        cv2.imwrite(fpath, img)  # 写入文件
        logger.info(f"图像已保存: {fpath}")
        saved.append(fpath)
    return saved
