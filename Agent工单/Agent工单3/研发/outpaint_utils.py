# -*- coding: utf-8 -*-
"""
==============================================================================
功能说明：图像扩图辅助方法（monkeypatch 注入）
==============================================================================
本文件定义 ImageOutpainter 所需的辅助方法：

  outpaint_progressive — 渐进式扩图（多步小幅扩展，适合大比例扩展）
  validate_outpaint — 扩图质量验证（尺寸/中心一致/异常像素检测）

通过 monkeypatch 注入到 outpainter.ImageOutpainter 类。

工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
==============================================================================
"""

import numpy as np
import cv2
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

from outpainter import ImageOutpainter  # 目标 monkeypatch 类


# ================================================================
# 渐进式扩图（针对大比例扩展）
# ================================================================
def outpaint_progressive(
    self, image: np.ndarray, target_ratio: float = None,
    steps: int = None, prompt: str = None, negative_prompt: str = None,
) -> np.ndarray:
    """渐进式扩图：多次小幅扩展，每次扩展后重新评估画布

    对于 expand_ratio >= 1.8 的大面积扩展，分步骤渐进扩展
    能获得更好的边缘连续性和内容一致性。

    Args:
        image: 输入 BGR 图像
        target_ratio: 目标扩展比例（默认从配置读取）
        steps: 分几步（None=自动根据比例决定，每步不超过 1.25x）
        prompt: 正向提示词
        negative_prompt: 负向提示词

    Returns:
        渐进扩展后的 BGR 图像
    """
    from config import outpaint_config
    target = target_ratio or outpaint_config.expand_ratio

    # 小幅扩展直接一步完成，无需渐进
    if target <= 1.3:
        return self.outpaint(image, prompt, negative_prompt, expand_ratio=target)

    # 自动确定步数：每步不超过 1.25x
    if steps is None:
        import numpy as np
        ratio_per_step = 1.25
        steps = max(2, int(np.ceil(np.log(target) / np.log(ratio_per_step))))

    # 计算每步扩展比例（等比递增）
    step_ratios = np.exp(np.linspace(np.log(1.0), np.log(target), steps + 1))[1:]
    step_ratios = [
        r / step_ratios[i - 1] if i > 0 else r
        for i, r in enumerate(step_ratios)
    ]

    # 逐步扩展
    current = image.copy()
    for i, ratio in enumerate(step_ratios):
        logger.info(f"渐进扩图 第 {i+1}/{steps} 步, ratio_step={ratio:.2f}")
        # 渐进步骤用稍低的去噪强度，避免过度改变
        denoise = 0.65 if ratio < 1.2 else 0.75
        current = self.outpaint(
            current, prompt, negative_prompt,
            expand_ratio=ratio, denoising_strength=denoise,
        )

    final_h, final_w = current.shape[:2]
    logger.info(
        f"渐进扩图完成: {image.shape[1]}x{image.shape[0]} -> {final_w}x{final_h}"
    )
    return current


# ================================================================
# 扩图质量验证
# ================================================================
def validate_outpaint(
    original: np.ndarray, outpainted: np.ndarray,
) -> Dict[str, object]:
    """验证扩图质量

    检查项：
    - 尺寸是否合理扩大
    - 中心区域是否保留原图内容
    - 是否有异常像素（死黑/死白）

    Returns:
        {"valid": bool, "warnings": [str], "metrics": {...}}
    """
    warnings = []
    oh, ow = original.shape[:2]
    nh, nw = outpainted.shape[:2]

    # 1. 尺寸检查：扩图后不应小于原图
    if nw < ow * 0.95 or nh < oh * 0.95:
        warnings.append(f"扩图后尺寸({nw}x{nh})小于等于原图({ow}x{oh})")

    # 2. 中心区域相似度检查
    cy, cx = nh // 2, nw // 2
    half_h, half_w = oh // 2, ow // 2
    center_orig = original
    center_new = outpainted[
        cy - half_h:cy + half_h, cx - half_w:cx + half_w
    ]
    if center_new.shape == center_orig.shape:
        diff = np.abs(
            center_orig.astype(float) - center_new.astype(float)
        ).mean()
        if diff > 50:  # 差异过大
            warnings.append(f"中心区域与原图差异过大 (mean_diff={diff:.1f})")
        elif diff > 30:  # 有较明显变化
            warnings.append(f"中心区域有较明显变化 (mean_diff={diff:.1f})")

    # 3. 异常像素检查：死黑或死白区域
    if (outpainted.max(axis=2).min() < 5):
        warnings.append("图像中存在接近全黑的区域")
    if (outpainted.min(axis=2).max() > 250):
        warnings.append("图像中存在接近全白的区域")

    valid = len(warnings) == 0
    return {
        "valid": valid,
        "warnings": warnings,
        "metrics": {
            "original_size": f"{ow}x{oh}",
            "outpainted_size": f"{nw}x{nh}",
            "expand_ratio": nw / ow,
        },
    }


# ================================================================
# Monkeypatch 注入
# ================================================================
ImageOutpainter.outpaint_progressive = outpaint_progressive
ImageOutpainter.validate_outpaint = staticmethod(validate_outpaint)
logger.info("outpaint_utils 方法已注入到 ImageOutpainter")


# ================================================================
# 自测入口
# ================================================================
if __name__ == "__main__":
    from config import setup_logging
    setup_logging()
    try:
        op = ImageOutpainter()
        logger.info("图像扩图器初始化成功")
    except Exception as e:
        logger.error(f"初始化失败: {e}")
