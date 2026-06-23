# -*- coding: utf-8 -*-
"""
==============================================================================
功能说明：图像生成器核心模块（ImageGenerator 类定义）
==============================================================================
本文件定义了 ImageGenerator 类的核心结构：
  - 初始化与模式选择（WebUI API / ControlNet 本地推理）
  - WebUI 启动就绪检测与 ControlNet 扩展探测
  - PIL/OpenCV 图像格式互转工具
  - 旋转面部生成（generate_rotated_face、generate_all_rotations）

WebUI API 底层调用与缓存方法通过 image_gen_webui.py monkeypatch 注入。

工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
==============================================================================
"""

import os
import io
import time
import base64
import numpy as np
import cv2
from PIL import Image
from typing import List, Optional, Tuple
import logging
import requests

from config import (
    webui_config, model_config, gen_config, face_config,
    retrieval_config, controlnet_config,
    FACE_PROMPT_TEMPLATE, FACE_NEGATIVE_PROMPT
)

logger = logging.getLogger(__name__)

# 可选依赖：ControlNet 本地生成器
try:
    from controlnet_generator import ControlNetGenerator
    _CONTROLNET_AVAILABLE = True
    _CONTROLNET_IMPORT_ERROR = ""
except Exception as e:
    _CONTROLNET_AVAILABLE = False
    _CONTROLNET_IMPORT_ERROR = str(e)

# 可选依赖：缓存模块（Milvus/Redis）
try:
    from embedding_service import get_embedding_service
    from vector_store import get_vector_store
    from cache_manager import get_cache_manager
    _CACHE_AVAILABLE = True
except Exception:
    _CACHE_AVAILABLE = False
    logger.info("缓存模块未加载（Milvus/Redis 不可用），将跳过高阶缓存功能")


class ImageGenerator:
    """图像生成器 — 支持 WebUI API 和 ControlNet 本地推理两种模式"""

    def __init__(self, use_controlnet: bool = None):
        """初始化：根据参数或配置选择推理模式"""
        self._use_controlnet = (
            use_controlnet
            if use_controlnet is not None
            else controlnet_config.enabled
        )
        if self._use_controlnet:
            self._init_controlnet()  # 加载本地 ControlNet 管线
        else:
            self._init_webui()       # 连接远程 WebUI API

    def _init_controlnet(self):
        """初始化 ControlNet 本地推理管线"""
        if not _CONTROLNET_AVAILABLE:
            raise RuntimeError(
                "ControlNet 本地推理模式不可用。\n"
                "请安装依赖: pip install diffusers controlnet_aux accelerate\n"
                f"原始错误: {_CONTROLNET_IMPORT_ERROR}"
            )
        self._cn_generator = ControlNetGenerator()
        logger.info("图像生成器初始化完成（ControlNet 本地推理模式）")

    def _init_webui(self):
        """初始化 WebUI API 连接"""
        self.base_url = webui_config.base_url
        self.timeout = webui_config.timeout
        self._ensure_webui_ready()           # 阻塞等待 WebUI 就绪
        self._webui_has_controlnet = self._check_webui_controlnet()  # 探测扩展
        logger.info(
            f"图像生成器初始化完成，WebUI: {self.base_url}"
            f"{' (含 ControlNet 扩展)' if self._webui_has_controlnet else ''}"
        )

    # ================================================================
    # WebUI 启动与检测
    # ================================================================
    def _ensure_webui_ready(self):
        """轮询等待 WebUI API 就绪，超时抛异常"""
        if not webui_config.wait_startup:
            return
        logger.info("等待 SD WebUI API 就绪...")
        timeout = webui_config.startup_timeout
        for _ in range(timeout // 2):
            try:
                resp = requests.get(
                    f"{self.base_url}/sdapi/v1/progress", timeout=5
                )
                if resp.status_code == 200:
                    logger.info("SD WebUI API 已就绪")
                    return
            except Exception:
                pass  # 连接失败，继续轮询
            time.sleep(2)
        raise TimeoutError(
            "SD WebUI 未能在规定时间内启动。请先运行 launch_fixed.sh"
        )

    def _check_webui_controlnet(self) -> bool:
        """探测 WebUI 是否安装 ControlNet 扩展"""
        # 方法 1：查询版本接口
        try:
            resp = requests.get(f"{self.base_url}/controlnet/version", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"检测到 ControlNet 扩展 v{data.get('version', '?')}")
                return True
        except Exception:
            pass
        # 方法 2：备选 — 检查模型列表
        try:
            resp = requests.get(f"{self.base_url}/controlnet/model_list", timeout=5)
            if resp.status_code == 200:
                logger.info("检测到 ControlNet 扩展（通过 model_list）")
                return True
        except Exception:
            pass
        logger.info("未检测到 ControlNet 扩展，使用基础 img2img")
        return False

    # ================================================================
    # 图像格式转换工具（PIL / OpenCV / Base64）
    # ================================================================
    @staticmethod
    def _pil_to_base64(img: Image.Image) -> str:
        """PIL -> Base64 字符串"""
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

    @staticmethod
    def _base64_to_pil(b64_str: str) -> Image.Image:
        """Base64 -> PIL 图像"""
        return Image.open(io.BytesIO(base64.b64decode(b64_str)))

    @staticmethod
    def _pil_to_cv2(img: Image.Image) -> np.ndarray:
        """PIL（RGB） -> OpenCV（BGR）"""
        return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

    @staticmethod
    def _cv2_to_pil(img: np.ndarray) -> Image.Image:
        """OpenCV（BGR） -> PIL（RGB）"""
        return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

    # ================================================================
    # 旋转面部生成
    # ================================================================
    def generate_rotated_face(
        self, init_image: np.ndarray, rotated_image: np.ndarray,
        depth_map: np.ndarray, direction: str, angle: float
    ) -> np.ndarray:
        """生成指定角度的旋转面部图像

        策略：原图直接作为 img2img 输入 + 方向 prompt + 中等去噪 (0.25-0.35)，
        改变朝向但保留身份。ControlNet 模式委托本地生成器。
        """
        # ControlNet 本地模式
        if self._use_controlnet:
            return self._cn_generator.generate_rotated_face(
                init_image=init_image, direction=direction, angle=angle,
            )

        # WebUI API 模式：根据角度选去噪强度与方向描述
        abs_angle = abs(angle)
        if abs_angle < 5:
            denoising = 0.25  # 近似正面：低去噪保持原图细节
            direction_str = "front view, looking directly at camera, symmetrical face"
        else:
            denoising = 0.35  # 侧面旋转：中去噪改变朝向
            direction_str = (
                f"head turned to the {direction}, "
                f"face profile from the {direction}, "
                f"{direction}-facing view"
            )

        # 正向提示词：强调身份保持
        prompt = (
            "same person, same face, same identity, "
            f"exactly the same facial features, "
            f"same eyes, same nose, same mouth, same skin tone, same hair, "
            f"{direction_str}, "
            "high quality portrait, professional photography, sharp focus, 8k"
        )
        # 负向提示词：避免身份漂移
        negative_prompt = (
            "different person, different face, different identity, "
            "different eyes, different nose, different mouth, "
            "changed face, altered features, gender change, "
            "deformed, blurry, distorted, ugly, low quality, "
            "watermark, text, extra fingers, bad anatomy"
        )

        meta = self._build_rotation_meta(direction, angle)  # 缓存元数据

        # 1. 查 Redis 精确缓存
        cached = self._check_cache(prompt, init_image, meta)
        if cached is not None:
            logger.info(f"缓存命中: {direction}")
            return cached

        # 2. 调用 img2img 生成
        logger.info(
            f"WebUI img2img: direction={direction} angle={angle}° "
            f"denoising={denoising}"
        )
        generated = self._call_img2img(
            init_image=init_image, prompt=prompt,
            negative_prompt=negative_prompt, denoising_strength=denoising,
        )

        # 3. 写入缓存
        self._store_to_cache(prompt, init_image, generated, "rotation", meta)
        logger.info(f"完成: {direction} {angle}°")
        return generated

    def generate_all_rotations(
        self, init_image: np.ndarray, processor
    ) -> List[np.ndarray]:
        """生成三张旋转图像：左转 / 右转 / 端正

        直接用原图 + 方向 prompt 让 SD 生成不同朝向，不使用 3D warp。
        """
        if self._use_controlnet:
            return self._cn_generator.generate_all_rotations(init_image, processor)

        results = []
        # 三个方向的生成任务
        tasks = [
            ("left", face_config.left_rotation_angle),
            ("right", face_config.right_rotation_angle),
            ("front", face_config.frontal_angle),
        ]
        for direction, angle in tasks:
            logger.info(f"生成旋转图像: {direction}, 角度={angle}°")
            generated = self.generate_rotated_face(
                init_image=init_image, rotated_image=None, depth_map=None,
                direction=direction, angle=angle,
            )
            results.append(generated)
        logger.info(f"全部旋转图像生成完成，共 {len(results)} 张")
        return results


# 导入 image_gen_webui 触发 monkeypatch（将 WebUI API 方法注入 ImageGenerator）
import image_gen_webui  # noqa: F401,E402
