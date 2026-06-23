# -*- coding: utf-8 -*-
"""
==============================================================================
功能说明：图像扩图核心模块（ImageOutpainter 类定义）
==============================================================================
本文件定义了 ImageOutpainter 类的核心结构：
  - 初始化与配置
  - PIL/OpenCV 图像格式互转工具
  - 缓存管理（Redis 精确缓存）
  - 扩图画布与遮罩创建（create_outpaint_canvas）
  - 核心扩图执行（outpaint）

渐进式扩图（outpaint_progressive）和质量验证（validate_outpaint）
通过 outpaint_utils.py 中的 monkeypatch 注入。

工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
==============================================================================
"""

import io
import base64
import numpy as np
import cv2
from PIL import Image, ImageFilter
from typing import Dict, Optional
import logging
import random
import requests

from config import (
    webui_config, gen_config, outpaint_config
)

logger = logging.getLogger(__name__)

# 可选缓存模块
try:
    from cache_manager import get_cache_manager
    _CACHE_AVAILABLE = True
except Exception:
    _CACHE_AVAILABLE = False


class ImageOutpainter:
    """图像扩图器 — 通过 SD WebUI Inpainting API 实现"""

    def __init__(self):
        """初始化扩图器：读取 WebUI 连接配置"""
        self.base_url = webui_config.base_url
        self.timeout = webui_config.timeout
        logger.info("图像扩图器初始化完成")

    # ================================================================
    # 图像格式转换工具
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
    # 缓存管理
    # ================================================================
    def _build_outpaint_meta(self) -> dict:
        """构建扩图任务缓存元数据"""
        return {
            "expand_ratio": outpaint_config.expand_ratio,
            "steps": gen_config.num_inference_steps,
            "guidance": gen_config.guidance_scale,
            "prompt": outpaint_config.prompt,
        }

    def _check_cache(
        self, prompt: str, image: np.ndarray, meta: dict
    ) -> Optional[np.ndarray]:
        """查询 Redis 精确缓存，未命中返回 None"""
        if not _CACHE_AVAILABLE:
            return None
        try:
            cache = get_cache_manager()
            token = cache.build_cache_token(prompt, image, meta)
            return cache.get_cached_image(prompt, token)
        except Exception as e:
            logger.debug(f"缓存查询跳过: {e}")
            return None

    def _store_result(
        self, prompt: str, source_image: np.ndarray,
        image: np.ndarray, meta: dict
    ):
        """将扩图结果写入 Redis 缓存"""
        if not _CACHE_AVAILABLE:
            return
        try:
            cache = get_cache_manager()
            token = cache.build_cache_token(prompt, source_image, meta)
            cache.cache_result(
                prompt, image, "outpaint", extra_meta=meta, cache_token=token)
            logger.info("扩图结果写入 Redis 缓存")
        except Exception as e:
            logger.debug(f"缓存写入跳过: {e}")

    # ================================================================
    # 扩图画布与遮罩
    # ================================================================
    def create_outpaint_canvas(self, image: np.ndarray, expand_ratio: float):
        """创建扩图画布和遮罩

        改进版遮罩策略：
        - 黑色区域（保留）= 原图内部（含小边距过渡带）
        - 白色区域（重绘）= 扩展区域
        - 边缘羽化：渐变过渡避免硬拼接缝
        - 四角额外保留：避免角落细节损失
        - 自适应模糊半径：根据图像分辨率调整

        Returns:
            (canvas, mask): 画布 (PIL) 和遮罩 (PIL)，遮罩白色=需填充
        """
        h, w = image.shape[:2]
        # 计算新画布尺寸（对齐到 8px）
        new_w = (int(w * expand_ratio) // 8) * 8
        new_h = (int(h * expand_ratio) // 8) * 8
        offset_x = (new_w - w) // 2  # 原图水平居中偏移
        offset_y = (new_h - h) // 2  # 原图垂直居中偏移

        # 多区域边缘颜色采样：四边 + 四角
        pil_img = self._cv2_to_pil(image)
        img_np = np.array(pil_img)
        edge_samples = [
            img_np[0, :, :],       # 上边
            img_np[-1, :, :],      # 下边
            img_np[:, 0, :],       # 左边
            img_np[:, -1, :],      # 右边
        ]
        # 四角采样
        corner_size = max(5, int(min(w, h) * 0.02))
        edge_samples.extend([
            img_np[0:corner_size, 0:corner_size, :].reshape(-1, 3),     # 左上角
            img_np[0:corner_size, -corner_size:, :].reshape(-1, 3),     # 右上角
            img_np[-corner_size:, 0:corner_size, :].reshape(-1, 3),     # 左下角
            img_np[-corner_size:, -corner_size:, :].reshape(-1, 3),     # 右下角
        ])
        # 用边缘平均颜色填充画布背景
        edge_pixels = np.concatenate(edge_samples)
        edge_color = tuple(int(c) for c in edge_pixels.mean(axis=0))
        canvas = Image.new("RGB", (new_w, new_h), edge_color)
        canvas.paste(pil_img, (offset_x, offset_y))  # 贴入原图

        # 创建遮罩：白色=可重绘区域，黑色=保留区域
        mask = Image.new("L", (new_w, new_h), 255)  # 初始全白

        # 自适应过渡带宽度
        image_diag = (w ** 2 + h ** 2) ** 0.5  # 图像对角线
        margin_ratio = 0.03 if image_diag > 1024 else 0.05
        margin = max(8, int(min(w, h) * margin_ratio))
        inner_w = max(w - 2 * margin, w // 2)
        inner_h = max(h - 2 * margin, h // 2)
        margin = min(margin, (w - inner_w) // 2, (h - inner_h) // 2)

        # 在遮罩中心创建黑色保留区域
        mask_inner = Image.new("L", (inner_w, inner_h), 0)
        mask.paste(
            mask_inner,
            (offset_x + (w - inner_w) // 2, offset_y + (h - inner_h) // 2)
        )

        # 自适应羽化半径：大图用更大模糊
        blur_radius = max(10, int(min(w, h) * 0.05))
        mask = mask.filter(ImageFilter.GaussianBlur(radius=blur_radius))

        logger.info(
            f"扩图画布: {w}x{h} -> {new_w}x{new_h} "
            f"margin={margin}px blur={blur_radius}px ratio={expand_ratio}"
        )
        return canvas, mask

    # ================================================================
    # 核心：执行扩图
    # ================================================================
    def outpaint(
        self, image: np.ndarray, prompt: str = None,
        negative_prompt: str = None, expand_ratio: float = None,
        denoising_strength: float = None,
    ) -> np.ndarray:
        """执行图像扩图

        改进版：根据扩展比例自适应调整去噪强度与步数，
        大面积扩展时用更高强度确保内容一致性。

        Args:
            image: 输入 BGR 图像
            prompt: 正向提示词（None=使用默认人像扩图 prompt）
            negative_prompt: 负向提示词
            expand_ratio: 扩展比例（默认从配置读取）
            denoising_strength: 去噪强度

        Returns:
            扩图后的 BGR 图像
        """
        ratio = expand_ratio or outpaint_config.expand_ratio
        denoise = denoising_strength or outpaint_config.denoising_strength

        # 根据扩展比例自适应调整参数
        if ratio >= 1.8:
            denoise = max(denoise, 0.85)   # 大面积：高强度
            steps = max(gen_config.num_inference_steps, 35)
        elif ratio >= 1.4:
            denoise = max(denoise, 0.80)   # 中等面积
            steps = gen_config.num_inference_steps
        else:
            denoise = min(denoise, 0.70)   # 小面积：低强度保持原图
            steps = gen_config.num_inference_steps

        # 默认人像扩图正向提示词
        if prompt is None:
            prompt = (
                "professional portrait photography, same person, "
                "upper body shot, elegant casual clothing, "
                "natural studio lighting, neutral background, "
                "sharp focus, 8k, highly detailed, "
                "seamless image extension, perfect composition"
            )
        # 默认负向提示词
        if negative_prompt is None:
            negative_prompt = (
                "different person, deformed face, bad anatomy, disfigured, "
                "blurry, distorted, visible seams, hard edges, cut off, "
                "poorly drawn, watermark, text, signature, "
                "different clothing, multiple people, double face"
            )

        # 构建缓存元数据
        meta = self._build_outpaint_meta()
        meta["expand_ratio"] = ratio
        meta["denoising"] = denoise
        meta["steps"] = steps

        # 1. 查 Redis 缓存
        cached = self._check_cache(prompt, image, meta)
        if cached is not None:
            logger.info("Redis 缓存命中（扩图），跳过生成")
            return cached

        # 2. 创建画布 + 遮罩
        canvas_pil, mask_pil = self.create_outpaint_canvas(image, ratio)

        # 3. 调用 WebUI API
        seed = gen_config.seed if gen_config.seed != -1 else random.randint(0, 2**32)

        payload = {
            "init_images": [self._pil_to_base64(canvas_pil)],
            "mask": self._pil_to_base64(mask_pil),
            "prompt": prompt, "negative_prompt": negative_prompt,
            "denoising_strength": denoise,
            "steps": steps, "cfg_scale": gen_config.guidance_scale,
            "seed": seed,
            "inpainting_fill": 1, "inpaint_full_res": True,
            "inpaint_full_res_padding": 32, "sampler_name": "Euler a",
            "width": canvas_pil.width, "height": canvas_pil.height,
        }

        logger.info(
            f"WebUI 扩图: {canvas_pil.width}x{canvas_pil.height} "
            f"seed={seed} denoise={denoise}"
        )
        resp = requests.post(
            f"{self.base_url}/sdapi/v1/img2img", json=payload, timeout=self.timeout
        )
        resp.raise_for_status()
        result_rgb = np.array(self._base64_to_pil(resp.json()["images"][0]))
        result_bgr = cv2.cvtColor(result_rgb, cv2.COLOR_RGB2BGR)

        # 4. 写入缓存
        self._store_result(prompt, image, result_bgr, meta)
        logger.info(f"扩图完成, 结果: {result_bgr.shape[1]}x{result_bgr.shape[0]}")
        return result_bgr


# 导入 outpaint_utils 触发 monkeypatch（注入 outpaint_progressive 和 validate_outpaint）
import outpaint_utils  # noqa: F401,E402
