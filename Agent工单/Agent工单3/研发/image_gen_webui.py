# -*- coding: utf-8 -*-
"""
==============================================================================
功能说明：图像生成器 WebUI API 调用与缓存方法（monkeypatch 注入）
==============================================================================
本文件定义 ImageGenerator 所需的 WebUI API 底层调用和缓存方法：

  _call_img2img / _call_inpaint / _call_img2img_controlnet — WebUI API 调用
  _build_rotation_meta / _check_cache / _store_to_cache / _search_similar — 缓存

通过 monkeypatch 注入到 image_generator.ImageGenerator 类。

工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
==============================================================================
"""

import io, base64, random, logging
import numpy as np, cv2
from PIL import Image
from typing import Optional
import requests

from config import (
    webui_config, gen_config, face_config,
    retrieval_config, FACE_NEGATIVE_PROMPT
)

logger = logging.getLogger(__name__)

# 可选缓存模块
try:
    from embedding_service import get_embedding_service
    from vector_store import get_vector_store
    from cache_manager import get_cache_manager
    _CACHE_AVAILABLE = True
except Exception:
    _CACHE_AVAILABLE = False

from image_generator import ImageGenerator  # 目标 monkeypatch 类


# ================================================================
# WebUI API 调用
# ================================================================
def _call_img2img(
    self, init_image: np.ndarray, prompt: str,
    negative_prompt: str = FACE_NEGATIVE_PROMPT,
    denoising_strength: float = None, steps: int = None,
    cfg_scale: float = None, seed: int = None,
    width: int = None, height: int = None,
) -> np.ndarray:
    """调用 WebUI img2img API，返回 BGR numpy 图像"""
    # 合并参数默认值
    strength = denoising_strength or gen_config.denoising_strength
    n_steps = steps or gen_config.num_inference_steps
    guidance = cfg_scale or gen_config.guidance_scale
    w = width or gen_config.image_width
    h = height or gen_config.image_height
    s = gen_config.seed if seed is None else seed
    if s == -1:  # 随机种子
        s = random.randint(0, 2**32)

    pil_img = ImageGenerator._cv2_to_pil(init_image).resize((w, h), Image.LANCZOS)

    payload = {
        "init_images": [ImageGenerator._pil_to_base64(pil_img)],
        "prompt": prompt, "negative_prompt": negative_prompt,
        "denoising_strength": strength, "steps": n_steps,
        "cfg_scale": guidance, "seed": s,
        "width": w, "height": h, "sampler_name": "Euler a",
    }

    logger.info(
        f"WebUI img2img: '{prompt[:50]}...' "
        f"seed={s} steps={n_steps} strength={strength}"
    )
    resp = requests.post(
        f"{self.base_url}/sdapi/v1/img2img", json=payload, timeout=self.timeout
    )
    resp.raise_for_status()
    return ImageGenerator._pil_to_cv2(
        ImageGenerator._base64_to_pil(resp.json()["images"][0])
    )


def _call_inpaint(
    self, init_image: np.ndarray, mask_image: np.ndarray,
    prompt: str, negative_prompt: str = "",
    denoising_strength: float = 0.80, steps: int = None,
    cfg_scale: float = None, seed: int = None,
) -> np.ndarray:
    """调用 WebUI inpainting API，返回 BGR numpy 图像"""
    n_steps = steps or gen_config.num_inference_steps
    guidance = cfg_scale or gen_config.guidance_scale
    s = gen_config.seed if seed is None else seed
    if s == -1:
        s = random.randint(0, 2**32)

    pil_img = ImageGenerator._cv2_to_pil(init_image)
    pil_mask = ImageGenerator._cv2_to_pil(mask_image)

    payload = {
        "init_images": [ImageGenerator._pil_to_base64(pil_img)],
        "mask": ImageGenerator._pil_to_base64(pil_mask),
        "prompt": prompt, "negative_prompt": negative_prompt,
        "denoising_strength": denoising_strength,
        "steps": n_steps, "cfg_scale": guidance, "seed": s,
        "inpainting_fill": 1, "inpaint_full_res": True,
        "inpaint_full_res_padding": 32, "sampler_name": "Euler a",
        "width": init_image.shape[1], "height": init_image.shape[0],
    }

    logger.info(f"WebUI inpaint: '{prompt[:50]}...' seed={s}")
    resp = requests.post(
        f"{self.base_url}/sdapi/v1/img2img", json=payload, timeout=self.timeout
    )
    resp.raise_for_status()
    return ImageGenerator._pil_to_cv2(
        ImageGenerator._base64_to_pil(resp.json()["images"][0])
    )


def _call_img2img_controlnet(
    self, init_image: np.ndarray, control_image: np.ndarray,
    prompt: str, negative_prompt: str = FACE_NEGATIVE_PROMPT,
    denoising_strength: float = None, controlnet_weight: float = 0.50,
    steps: int = None, cfg_scale: float = None, seed: int = None,
    width: int = None, height: int = None,
) -> np.ndarray:
    """调用 WebUI img2img + ControlNet OpenPose，实现姿态引导旋转

    Args:
        init_image: 输入 BGR 图像
        control_image: OpenPose 骨架控制图像
        controlnet_weight: ControlNet 权重（旋转建议 0.3-0.5）
    """
    strength = denoising_strength or gen_config.denoising_strength
    n_steps = steps or gen_config.num_inference_steps
    guidance = cfg_scale or gen_config.guidance_scale
    w = width or gen_config.image_width
    h = height or gen_config.image_height
    s = gen_config.seed if seed is None else seed
    if s == -1:
        s = random.randint(0, 2**32)

    # 缩放输入图像和控制图像
    pil_img = ImageGenerator._cv2_to_pil(init_image).resize((w, h), Image.LANCZOS)
    pil_ctrl = ImageGenerator._cv2_to_pil(control_image).resize(
        (w, h), Image.LANCZOS)

    payload = {
        "init_images": [ImageGenerator._pil_to_base64(pil_img)],
        "prompt": prompt, "negative_prompt": negative_prompt,
        "denoising_strength": strength, "steps": n_steps,
        "cfg_scale": guidance, "seed": s,
        "width": w, "height": h, "sampler_name": "Euler a",
        "alwayson_scripts": {
            "controlnet": {"args": [{
                "enabled": True,
                "model": "control_v11p_sd15_openpose [cab727d4]",
                "module": "openpose_full",
                "input_image": ImageGenerator._pil_to_base64(pil_ctrl),
                "weight": controlnet_weight,
                "guidance_start": 0.0, "guidance_end": 1.0,
                "resize_mode": "Resize and Fill", "pixel_perfect": True,
                "control_mode": "Balanced",
            }]}
        },
    }

    logger.info(
        f"WebUI img2img+ControlNet: '{prompt[:50]}...' "
        f"seed={s} cn_weight={controlnet_weight}"
    )
    resp = requests.post(
        f"{self.base_url}/sdapi/v1/img2img", json=payload, timeout=self.timeout
    )
    resp.raise_for_status()
    return ImageGenerator._pil_to_cv2(
        ImageGenerator._base64_to_pil(resp.json()["images"][0])
    )


# ================================================================
# 缓存（Milvus/Redis 不可用时自动跳过）
# ================================================================
def _build_rotation_meta(self, direction: str, angle: float) -> dict:
    """构建旋转任务缓存元数据"""
    return {
        "direction": direction,
        "angle": float(angle),
        "width": gen_config.image_width,
        "height": gen_config.image_height,
        "steps": gen_config.num_inference_steps,
        "guidance": gen_config.guidance_scale,
        "strength": gen_config.denoising_strength,
    }


def _check_cache(
    self, prompt: str, init_image: np.ndarray, meta: dict
) -> Optional[np.ndarray]:
    """查询 Redis 精确缓存，未命中返回 None"""
    if not _CACHE_AVAILABLE:
        return None
    try:
        cache = get_cache_manager()
        token = cache.build_cache_token(prompt, init_image, meta)
        return cache.get_cached_image(prompt, token)
    except Exception as e:
        logger.debug(f"缓存查询跳过: {e}")
        return None


def _store_to_cache(
    self, prompt: str, source_image: np.ndarray,
    image: np.ndarray, task_type: str, meta: dict
):
    """将生成结果写入 Redis 缓存"""
    if not _CACHE_AVAILABLE:
        return
    try:
        cache = get_cache_manager()
        token = cache.build_cache_token(prompt, source_image, meta)
        cache.cache_result(
            prompt, image, task_type, extra_meta=meta, cache_token=token)
        logger.info("结果写入 Redis 缓存")
    except Exception as e:
        logger.debug(f"缓存写入跳过: {e}")


def _search_similar(self, prompt: str, task_type: str):
    """在 Milvus 向量库中搜索语义相似缓存"""
    if not retrieval_config.enable_semantic_retrieval or not _CACHE_AVAILABLE:
        return []
    try:
        emb_svc = get_embedding_service()
        vs = get_vector_store()
        embedding = emb_svc.encode_text(prompt)
        return vs.search_similar(
            embedding, top_k=1,
            task_type=task_type if retrieval_config.reuse_only_same_task else None)
    except Exception as e:
        logger.debug(f"Milvus 检索跳过: {e}")
        return []


# ================================================================
# Monkeypatch 注入
# ================================================================
ImageGenerator._call_img2img = _call_img2img
ImageGenerator._call_inpaint = _call_inpaint
ImageGenerator._call_img2img_controlnet = _call_img2img_controlnet
ImageGenerator._build_rotation_meta = _build_rotation_meta
ImageGenerator._check_cache = _check_cache
ImageGenerator._store_to_cache = _store_to_cache
ImageGenerator._search_similar = _search_similar
logger.info("image_gen_webui 方法已注入到 ImageGenerator")


# ================================================================
# 自测入口
# ================================================================
if __name__ == "__main__":
    from config import setup_logging
    setup_logging()
    try:
        gen = ImageGenerator()
        logger.info(f"图像生成器初始化成功 (ControlNet={gen._use_controlnet})")
    except Exception as e:
        logger.error(f"初始化失败: {e}")
