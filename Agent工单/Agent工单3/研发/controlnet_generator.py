# -*- coding: utf-8 -*-
"""
==============================================================================
功能说明：ControlNet OpenPose 本地推理模块（核心类，不依赖 WebUI API）
==============================================================================
本文件实现了基于本地 diffusers + ControlNet OpenPose 的面部旋转生成：
  - ControlNetGenerator: 加载 SD 1.5 + ControlNet OpenPose 管线
  - generate_rotated_face(): 用 OpenPose 骨架控制头部姿态生成旋转面部

扩展方法通过 monkeypatch 注入：
  - controlnet_utils.py: generate_all_rotations, outpaint 等

与 image_generator.py 的区别：
  - image_generator.py 通过 REST API 调用 SD WebUI（需要先启动 WebUI）
  - 本模块直接在本地加载 diffusers 管线（无需 WebUI，但需要 GPU 显存）

依赖：diffusers, controlnet_aux, torch, PIL
模型文件：
  - SD 1.5: v1-5-pruned-emaonly.safetensors
  - ControlNet: control_v11p_sd15_openpose.pth

工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
==============================================================================
"""

import os
import sys
import time
import logging
from typing import List, Optional, Tuple

import cv2
import numpy as np
import torch
from PIL import Image

from config import (
    controlnet_config, gen_config, face_config,
    FACE_PROMPT_TEMPLATE, FACE_NEGATIVE_PROMPT,
)

logger = logging.getLogger(__name__)

# ============================================================
# 延迟导入（避免未安装时阻塞 import）
# ============================================================
_diffusers_available = True
_controlnet_aux_available = True

try:
    from diffusers import StableDiffusionControlNetImg2ImgPipeline, ControlNetModel
    _DIFFUSERS_IMPORT_ERROR = ""
except Exception as e:
    _diffusers_available = False
    _DIFFUSERS_IMPORT_ERROR = str(e)

try:
    from controlnet_aux import OpenposeDetector
    _CONTROLNET_AUX_IMPORT_ERROR = ""
except Exception as e:
    _controlnet_aux_available = False
    _CONTROLNET_AUX_IMPORT_ERROR = str(e)


class ControlNetGenerator:
    """基于 ControlNet OpenPose 的本地图像生成器

    直接在 GPU 上加载 SD 1.5 + ControlNet 管线，
    不需要事先启动 SD WebUI。
    """

    def __init__(self):
        self._check_dependencies()

        # 配置
        self.device = controlnet_config.device
        self.dtype = getattr(torch, controlnet_config.torch_dtype)
        self.conditioning_scale = controlnet_config.conditioning_scale
        # IP-Adapter 默认启用 — 这是保持身份的关键
        self.use_ip_adapter = True

        # 管线（懒加载）
        self._pipe = None
        self._pose_detector = None

        # 离线模式
        if controlnet_config.offline_mode:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

        logger.info(
            f"ControlNet 生成器初始化: device={self.device}, "
            f"dtype={controlnet_config.torch_dtype}, "
            f"IP-Adapter={'启用' if self.use_ip_adapter else '关闭'}"
        )

    # ================================================================
    # 依赖检查
    # ================================================================
    @staticmethod
    def _check_dependencies():
        """检查 diffusers / controlnet_aux 是否可用"""
        if not _diffusers_available:
            msg = (
                "未安装 diffusers，无法使用 ControlNet 本地推理模式。\n"
                "请安装: pip install diffusers==0.35.1 accelerate==1.8.1\n"
                f"原始错误: {_DIFFUSERS_IMPORT_ERROR}"
            )
            raise RuntimeError(msg)
        if not _controlnet_aux_available:
            msg = (
                "未安装 controlnet_aux，无法使用 OpenPose 姿态检测。\n"
                "请安装: pip install controlnet_aux\n"
                f"原始错误: {_CONTROLNET_AUX_IMPORT_ERROR}"
            )
            raise RuntimeError(msg)

    # ================================================================
    # 管线加载（懒加载，首次调用时才真正加载模型）
    # ================================================================
    def _load_pipeline(self):
        """加载 SD 1.5 + ControlNet OpenPose 管线"""
        if self._pipe is not None:
            return

        logger.info("=" * 50)
        logger.info("正在加载 ControlNet 本地管线...")

        # 1. 加载 ControlNet OpenPose 模型
        logger.info(f"ControlNet 模型: {controlnet_config.controlnet_model_path}")
        if not os.path.exists(controlnet_config.controlnet_model_path):
            raise FileNotFoundError(
                f"ControlNet 模型不存在: {controlnet_config.controlnet_model_path}\n"
                f"请先下载到该路径"
            )

        controlnet = ControlNetModel.from_single_file(
            controlnet_config.controlnet_model_path,
            config=controlnet_config.controlnet_config_path,
            torch_dtype=self.dtype,
            local_files_only=controlnet_config.offline_mode,
        )
        logger.info("ControlNet OpenPose 加载完成")

        # 2. 加载 SD 1.5 + ControlNet img2img 管线
        logger.info(f"SD 模型: {controlnet_config.sd_model_path}")
        if not os.path.exists(controlnet_config.sd_model_path):
            raise FileNotFoundError(
                f"SD 模型不存在: {controlnet_config.sd_model_path}\n"
                f"请先下载 SD 1.5 模型到该路径"
            )

        pipe = StableDiffusionControlNetImg2ImgPipeline.from_single_file(
            controlnet_config.sd_model_path,
            controlnet=controlnet,
            torch_dtype=self.dtype,
            safety_checker=None,
            load_safety_checker=False,
            local_files_only=controlnet_config.offline_mode,
        )
        logger.info("SD 1.5 管线加载完成")

        # 3. 加载 IP-Adapter Face ID（保持人脸身份的关键）
        if self.use_ip_adapter:
            ip_path = controlnet_config.ip_adapter_model_path
            ip_dir = os.path.dirname(ip_path)
            ip_file = os.path.basename(ip_path)
            if os.path.exists(ip_path):
                logger.info(f"加载 IP-Adapter Face ID: {ip_path}")
                pipe.load_ip_adapter(
                    ip_dir,
                    weight_name=ip_file,
                    local_files_only=True,
                )
                pipe.set_ip_adapter_scale(0.8)
                logger.info("IP-Adapter Face ID 加载完成 (scale=0.8)")
            else:
                logger.warning(f"IP-Adapter 模型不存在: {ip_path}，身份保持能力受限")
                self.use_ip_adapter = False

        # 4. 移到 GPU 并优化显存
        pipe = pipe.to(self.device)
        pipe.enable_model_cpu_offload()
        pipe.enable_vae_slicing()

        self._pipe = pipe
        logger.info("ControlNet 管线就绪（SD 1.5 + ControlNet OpenPose）")
        logger.info("=" * 50)

    # ================================================================
    # 核心：旋转面部生成
    # ================================================================
    def generate_rotated_face(
        self,
        init_image: np.ndarray,
        rotated_image: np.ndarray = None,
        depth_map: np.ndarray = None,
        direction: str = "",
        angle: float = 0.0,
    ) -> np.ndarray:
        """
        生成指定角度/方向的面部旋转图像

        策略：
        - IP-Adapter Face ID 锁定人物身份（关键！）
        - ControlNet OpenPose 维持人体结构
        - 高去噪 (0.55-0.65) 让 SD 有足够自由度改变朝向
        - 方向 prompt 指定目标朝向
        """
        self._load_pipeline()

        pil_original = self._cv2_to_pil(init_image).resize((512, 512), Image.LANCZOS)

        # OpenPose 骨架
        detector = self._get_pose_detector()
        pose_image = detector(pil_original)
        pose_image = pose_image.resize((512, 512), Image.LANCZOS)

        abs_angle = abs(angle)
        if abs_angle < 5:
            prompt = (
                "same person, same face, "
                "looking directly at camera, front view, symmetrical face, "
                "high quality portrait, professional photo, 8k"
            )
            denoising = 0.25
            cn_scale = 0.80
        else:
            direction_full = "left" if angle < 0 else "right"
            prompt = (
                f"same person, "
                f"head turned to the {direction_full}, "
                f"facing {direction_full}, {direction_full} profile, "
                f"three-quarter view, looking to the {direction_full}, "
                f"high quality portrait, professional photo, 8k"
            )
            # IP-Adapter 锁定身份 → 可以用更高去噪来真正转头
            denoising = 0.60
            cn_scale = 0.55

        negative_prompt = (
            "different person, different face, gender change, "
            "deformed face, bad anatomy, ugly, blurry, "
            "watermark, text, distorted, low quality"
        )

        logger.info(
            f"ControlNet: direction={direction} angle={angle}° "
            f"denoising={denoising} cn_scale={cn_scale} "
            f"ip_adapter={self.use_ip_adapter}"
        )
        torch.cuda.empty_cache()

        seed = gen_config.seed if gen_config.seed != -1 else 42
        generator = torch.Generator(device=self.device).manual_seed(seed)

        # 构建 pipeline 参数
        pipe_kwargs = dict(
            prompt=prompt,
            negative_prompt=negative_prompt,
            image=pil_original,
            control_image=pose_image,
            controlnet_conditioning_scale=cn_scale,
            strength=denoising,
            num_inference_steps=30,
            guidance_scale=7.5,
            generator=generator,
        )

        # IP-Adapter: 用原图作为身份参考 → 锁定人脸
        if self.use_ip_adapter:
            pipe_kwargs["ip_adapter_image"] = pil_original

        with torch.autocast(self.device):
            result = self._pipe(**pipe_kwargs)

        output_bgr = self._pil_to_cv2(result.images[0])
        logger.info(f"ControlNet 完成: {direction} {angle}°")
        return output_bgr

    # ================================================================
    # 以下扩展方法通过 monkeypatch 从 controlnet_utils 注入：
    #   generate_all_rotations, outpaint, 工具方法等
    # ================================================================


# ================================================================
# 注册 monkeypatch 扩展方法（向后兼容 — 导入即生效）
# ================================================================
import controlnet_utils  # noqa: E402  # 注入批量生成、扩图、工具方法
