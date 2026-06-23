# -*- coding: utf-8 -*-
"""
==============================================================================
功能说明：千问图像编辑模型 (Qwen-Image-Edit-Max) 客户端类模块
==============================================================================
本文件定义 QwenImageEditor 类，封装阿里云 DashScope 千问图像编辑 API：
  - edit(): 核心编辑方法，支持 1-3 张输入图 + 文本指令
  - edit_and_save(): 编辑后自动下载保存到本地

向后兼容导出：
  - image_to_base64, url_to_image, save_edited_images (从 qwen_utils)
  - qwen_edit, qwen_edit_and_save (从 qwen_cli)

模型: qwen-image-edit-max
API: DashScope MultiModalConversation

工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
==============================================================================
"""

import io  # 内存字节流
import os  # 路径处理
import base64  # Base64 编解码
import time  # 性能计时
import logging  # 日志
from typing import Dict, List, Optional, Union  # 类型提示

import cv2  # OpenCV 图像处理
import numpy as np  # 数值数组
from PIL import Image  # PIL 图像处理

from dashscope import MultiModalConversation  # 千问多模态 API
import dashscope  # 全局配置

from config import qwen_config  # 千问配置
from qwen_utils import (  # 工具函数
    image_to_base64, url_to_image, save_edited_images,
)

logger = logging.getLogger(__name__)  # 模块日志器


class QwenImageEditor:
    """千问图像编辑模型 (Qwen-Image-Edit-Max) 客户端

    封装 DashScope MultiModalConversation API。
    示例: editor = QwenImageEditor(); result = editor.edit(images=["face.jpg"], prompt="...")
    """

    def __init__(self, api_key: str = None, model: str = None, base_url: str = None):
        """初始化编辑器，参数默认从 config.qwen_config 读取"""
        self.api_key = api_key or qwen_config.api_key  # API 密钥
        self.model = model or qwen_config.model  # 模型名
        self.base_url = base_url or qwen_config.base_url  # API 端点
        dashscope.base_http_api_url = self.base_url  # 全局 API 地址
        logger.info(f"千问编辑器初始化: model={self.model}, base_url={self.base_url}")

    def edit(
        self,
        images: List[Union[str, np.ndarray, Image.Image]],
        prompt: str,
        negative_prompt: str = None,
        n: int = None,
        size: str = None,
        watermark: bool = None,
        seed: int = None,
        prompt_extend: bool = None,
        timeout: int = 120,
    ) -> Dict:
        """调用 Qwen-Image-Edit 模型进行图像编辑

        Args:
            images: 输入图像列表 (1-3 张)，支持路径/numpy/PIL
            prompt: 编辑指令文本，多图可用"图1""图2"指代
            negative_prompt: 反向提示词（不想出现的内容）
            n: 输出图片数量 (1-6)
            size: 输出分辨率如 "1024*1024"
            watermark: 是否添加水印
            seed: 随机种子，-1 为随机
            prompt_extend: 是否启用提示词扩展
            timeout: 请求超时秒数

        Returns:
            {
                "success": bool,
                "images": [numpy BGR 数组, ...],  # 生成的图像
                "urls": [str, ...],               # 生成的图像 URL（24h有效）
                "usage": {...},                   # Token/图像用量
                "error": str or None,             # 错误信息
            }
        """
        # === 参数默认值（从 config 读取） ===
        n = n if n is not None else qwen_config.n
        size = size or qwen_config.size
        watermark = watermark if watermark is not None else qwen_config.watermark
        seed = seed if seed is not None else qwen_config.seed
        prompt_extend = prompt_extend if prompt_extend is not None else qwen_config.prompt_extend
        negative_prompt = negative_prompt or qwen_config.negative_prompt

        # === 校验输入 ===
        if not images:
            return {"success": False, "images": [], "urls": [],
                    "usage": {}, "error": "输入图像列表为空"}
        if len(images) > 3:
            logger.warning(f"输入图像数量 ({len(images)}) 超过上限 3，仅使用前 3 张")
            images = images[:3]

        # === 转换图像为 Base64 ===
        base64_images = []
        for i, img in enumerate(images):
            try:
                b64 = image_to_base64(img)  # 调用工具函数
                base64_images.append({"image": b64})
            except Exception as e:
                return {
                    "success": False, "images": [], "urls": [],
                    "usage": {}, "error": f"第 {i+1} 张图像转换失败: {e}",
                }

        # === 构建 API 请求 ===
        content = base64_images + [{"text": prompt}]  # 图像+文本
        messages = [{"role": "user", "content": content}]

        call_kwargs = {
            "api_key": self.api_key,
            "model": self.model,
            "messages": messages,
            "n": n,
            "size": size,
            "watermark": watermark,
            "prompt_extend": prompt_extend,
        }
        if seed is not None and seed >= 0:
            call_kwargs["seed"] = seed
        if negative_prompt:
            call_kwargs["negative_prompt"] = negative_prompt

        logger.info(
            f"调用 {self.model}: prompt='{prompt[:80]}...' "
            f"n={n} size={size} images={len(images)}"
        )

        # === 调用 API ===
        start_time = time.time()
        try:
            response = MultiModalConversation.call(**call_kwargs)
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"API 调用异常 ({elapsed:.1f}s): {e}")
            return {
                "success": False, "images": [], "urls": [],
                "usage": {}, "error": f"API 调用异常: {e}",
            }
        elapsed = time.time() - start_time

        # === 检查 HTTP 状态 ===
        if response.status_code != 200:
            error_msg = (
                f"API 返回错误 (HTTP {response.status_code}): "
                f"code={response.code}, message={response.message}"
            )
            logger.error(error_msg)
            return {
                "success": False, "images": [], "urls": [],
                "usage": {}, "error": error_msg,
            }

        # === 解析响应 ===
        try:
            output = response.output
            choices = output.choices if output else []
            if not choices:
                return {
                    "success": False, "images": [], "urls": [],
                    "usage": {}, "error": "API 返回中无 choices",
                }

            message = choices[0].message
            contents = message.content if message else []

            # 提取图像 URL 和/或 Base64 数据
            urls = []
            images_list = []
            for item in contents:
                if isinstance(item, dict) and "image" in item:
                    img_data = item["image"]
                    urls.append(img_data)
                    # 判断是 URL 还是 Base64
                    if img_data.startswith(("http://", "https://")):
                        img_array = url_to_image(img_data)  # URL→下载
                        if img_array is not None:
                            images_list.append(img_array)
                    elif img_data.startswith("data:"):
                        b64_part = img_data.split(",", 1)[-1]  # 取 Base64 部分
                        raw = base64.b64decode(b64_part)
                        npy = np.frombuffer(raw, dtype=np.uint8)
                        img_array = cv2.imdecode(npy, cv2.IMREAD_COLOR)
                        if img_array is not None:
                            images_list.append(img_array)

            # 提取用量信息
            usage = {}
            try:
                resp_usage = response.usage
                if resp_usage is not None:
                    if isinstance(resp_usage, dict):
                        usage = {
                            "input_tokens": resp_usage.get("input_tokens", 0),
                            "output_tokens": resp_usage.get("output_tokens", 0),
                            "image_count": resp_usage.get("image_count", 0),
                        }
                    else:
                        usage = {
                            "input_tokens": getattr(resp_usage, "input_tokens", 0),
                            "output_tokens": getattr(resp_usage, "output_tokens", 0),
                            "image_count": getattr(resp_usage, "image_count", 0),
                        }
            except Exception:
                pass  # 用量信息非关键，忽略异常

            logger.info(
                f"✅ {self.model} 调用成功 "
                f"({elapsed:.1f}s, {len(images_list)} 张图像)"
            )

            return {
                "success": True,
                "images": images_list,
                "urls": urls,
                "usage": usage,
                "error": None,
            }

        except Exception as e:
            logger.error(f"解析 API 响应失败: {e}")
            return {
                "success": False, "images": [], "urls": [],
                "usage": {}, "error": f"解析响应失败: {e}",
            }

    def edit_and_save(
        self, images: List[Union[str, np.ndarray, Image.Image]], prompt: str,
        output_dir: str = None, prefix: str = "qwen_edit", **kwargs,
    ) -> Dict:
        """编辑图像并保存到本地。参数同 edit()，额外支持 output_dir/prefix。
        Returns {"success": bool, "local_paths": [str], "urls": [str], "usage": {...}, "error": str}
        """
        # 默认输出目录
        if output_dir is None:
            from config import OUTPUT_DIR
            output_dir = os.path.join(OUTPUT_DIR, "qwen_edits")

        # 调用编辑
        result = self.edit(images=images, prompt=prompt, **kwargs)

        # 下载并保存图像
        local_paths = []
        if result["urls"]:
            local_paths = save_edited_images(
                result["urls"], output_dir, prefix=prefix
            )

        return {
            "success": result["success"] and len(local_paths) > 0,
            "local_paths": local_paths,
            "urls": result["urls"],
            "usage": result["usage"],
            "error": result["error"] if not local_paths else None,
        }
