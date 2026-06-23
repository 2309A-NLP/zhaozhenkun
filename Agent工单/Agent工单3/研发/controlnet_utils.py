# -*- coding: utf-8 -*-
"""
==============================================================================
功能说明：ControlNet 工具函数与扩展方法（ControlNetGenerator 扩展模块）
==============================================================================
本文件提供以下扩展功能，通过 monkeypatch 注入到 ControlNetGenerator 类：
  - generate_all_rotations(): 批量生成左转/右转/端正三张旋转图像
  - outpaint(): 使用 ControlNet 进行图像扩图
  - _get_pose_detector(): OpenPose 姿态检测器懒加载
  - _cv2_to_pil() / _pil_to_cv2(): 图像格式转换工具

本模块不独立使用，需配合 controlnet_generator.py 中的 ControlNetGenerator 类。
包含测试入口（__main__）供命令行直接运行。

依赖：diffusers, controlnet_aux, torch, PIL
工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
==============================================================================
"""

import os                               # 系统操作
import sys                              # 系统参数
import logging                          # 日志模块
from typing import List, Optional       # 类型提示

import cv2                              # OpenCV图像处理
import numpy as np                      # 数值计算
import torch                            # PyTorch
from PIL import Image, ImageFilter      # PIL图像处理

from config import (                    # 导入配置
    controlnet_config, gen_config, face_config,
)

logger = logging.getLogger(__name__)    # 创建模块日志器


# ================================================================
# OpenPose 姿态检测器（懒加载）
# ================================================================
def _get_pose_detector(self):
    """获取 OpenPose 姿态检测器（懒加载）"""
    if self._pose_detector is None:                                 # 首次调用时初始化
        logger.info("初始化 OpenPose 检测器...")

        # 如果指定了本地 body_pose_model.pth 路径，设置环境变量
        if controlnet_config.body_pose_model_path:                  # 本地模型路径
            os.environ["BODY_POSE_MODEL_PATH"] = controlnet_config.body_pose_model_path

        from controlnet_aux import OpenposeDetector                 # 延迟导入检测器
        self._pose_detector = OpenposeDetector.from_pretrained(    # 加载预训练模型
            "lllyasviel/ControlNet",
            local_files_only=controlnet_config.offline_mode,
        )
        logger.info("OpenPose 检测器就绪")
    return self._pose_detector                                      # 返回检测器实例


# ================================================================
# 图像格式转换工具
# ================================================================
def _cv2_to_pil(img: np.ndarray) -> Image.Image:
    """BGR numpy → RGB PIL"""
    return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))   # 颜色空间转换


def _pil_to_cv2(img: Image.Image) -> np.ndarray:
    """RGB PIL → BGR numpy"""
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)          # 颜色空间转换


# ================================================================
# 批量旋转生成
# ================================================================
def generate_all_rotations(
    self, init_image: np.ndarray, processor=None
) -> List[np.ndarray]:
    """生成三张旋转图像：左转 / 右转 / 端正

    直接用原图 + ControlNet 低强度骨架 + 高去噪 + 方向 prompt。
    不使用 3D warp — warp 会扭曲身份信息。

    Returns:
        [left_rotated, right_rotated, frontal] 三张 BGR 图像
    """
    self._load_pipeline()                                           # 确保管线已加载

    tasks = [                                                       # 三个旋转任务
        ("left", face_config.left_rotation_angle),                  # 左转
        ("right", face_config.right_rotation_angle),                # 右转
        ("front", face_config.frontal_angle),                       # 正面
    ]

    results = []                                                    # 收集生成结果
    for direction, angle in tasks:                                  # 遍历三个方向
        logger.info(f"生成旋转图像: {direction}, 角度={angle}°")
        generated = self.generate_rotated_face(                     # 调用核心方法
            init_image=init_image,                                  # 直接用原图
            direction=direction,                                    # 目标方向
            angle=angle,                                            # 目标角度
        )
        results.append(generated)                                   # 收集结果

    logger.info(f"全部旋转图像生成完成，共 {len(results)} 张")
    return results                                                  # 返回三张图像


# ================================================================
# 扩图（ControlNet 版本）
# ================================================================
def outpaint(
    self,
    image: np.ndarray,
    expand_ratio: float = 1.5,
    prompt: str = None,
    negative_prompt: str = None,
) -> np.ndarray:
    """使用 ControlNet 进行图像扩图

    Args:
        image: 输入 BGR 图像
        expand_ratio: 扩展比例
        prompt: 正向提示词
        negative_prompt: 负向提示词
    """
    self._load_pipeline()                                           # 确保管线已加载

    pil_image = self._cv2_to_pil(image) if isinstance(image, np.ndarray) else image
    w, h = pil_image.size                                           # 原始尺寸
    new_w = (int(w * expand_ratio) // 8) * 8                        # 新宽度（8的倍数）
    new_h = (int(h * expand_ratio) // 8) * 8                        # 新高度
    offset_x = (new_w - w) // 2                                     # x偏移
    offset_y = (new_h - h) // 2                                     # y偏移

    # 画布 + 遮罩
    canvas = Image.new("RGB", (new_w, new_h), (128, 128, 128))      # 灰色画布
    canvas.paste(pil_image, (offset_x, offset_y))                   # 粘贴原图

    mask = Image.new("L", (new_w, new_h), 255)                      # 白色遮罩（全部保护）
    margin = int(min(w, h) * 0.03)                                  # 3%内边距
    mask_inner = Image.new("L", (w - 2 * margin, h - 2 * margin), 0)  # 内部黑色（不保护）
    mask.paste(mask_inner, (offset_x + margin, offset_y + margin))  # 粘贴内部区域
    mask = mask.filter(ImageFilter.GaussianBlur(radius=15))         # 高斯模糊过渡

    # 提取 OpenPose 骨架
    detector = self._get_pose_detector()                            # 获取姿态检测器
    pose = detector(canvas).resize((new_w, new_h), Image.LANCZOS)   # 提取骨架并缩放

    if prompt is None:                                              # 默认正向提示词
        prompt = (
            "same person, high quality portrait, professional photography, "
            "natural background, upper body shot, elegant clothing, "
            "sharp focus, 8k, seamless extension, natural continuation"
        )
    if negative_prompt is None:                                     # 默认负向提示词
        negative_prompt = "different person, deformed, blurry, seams, distortion"

    logger.info(f"ControlNet 扩图: {new_w}x{new_h} ratio={expand_ratio}")
    torch.cuda.empty_cache()                                        # 清空GPU缓存

    seed = gen_config.seed if gen_config.seed != -1 else 100        # 随机种子
    generator = torch.Generator(device=self.device).manual_seed(seed)

    with torch.autocast(self.device):                               # 自动混合精度
        result = self._pipe(                                        # 执行扩散推理
            prompt=prompt,
            negative_prompt=negative_prompt,
            image=canvas,
            control_image=pose,
            controlnet_conditioning_scale=0.7,                      # ControlNet控制强度
            strength=0.75,                                          # 去噪强度
            num_inference_steps=35,                                 # 推理步数
            guidance_scale=8.0,                                     # 引导系数
            generator=generator,
        )

    return self._pil_to_cv2(result.images[0])                       # 转换回BGR格式


# ================================================================
# Monkeypatch: 将本模块函数注册到 ControlNetGenerator 类
# ================================================================
from controlnet_generator import ControlNetGenerator  # noqa: E402  # 导入核心类

# 实例方法（含 self 参数）
ControlNetGenerator._get_pose_detector = _get_pose_detector         # 姿态检测器获取
ControlNetGenerator.generate_all_rotations = generate_all_rotations # 批量旋转生成
ControlNetGenerator.outpaint = outpaint                             # 图像扩图

# 静态方法（无 self 参数）
ControlNetGenerator._cv2_to_pil = staticmethod(_cv2_to_pil)        # BGR→PIL转换
ControlNetGenerator._pil_to_cv2 = staticmethod(_pil_to_cv2)        # PIL→BGR转换

logger.debug("controlnet_utils 扩展方法已注册到 ControlNetGenerator")


# ================================================================
# 测试入口
# ================================================================
if __name__ == "__main__":
    from config import setup_logging
    setup_logging()

    import argparse
    parser = argparse.ArgumentParser(description="ControlNet 本地推理测试")
    parser.add_argument("--input", "-i", required=True, help="输入图像路径")
    parser.add_argument("--output", "-o", default=None, help="输出目录")
    args = parser.parse_args()

    controlnet_config.enabled = True                                # 启用ControlNet

    from utils import load_image                                    # 导入图像加载
    image = load_image(args.input)                                  # 加载输入图像
    if image is None:                                               # 加载失败
        logger.error(f"无法加载图像: {args.input}")
        sys.exit(1)

    gen = ControlNetGenerator()                                     # 创建生成器实例
    results = gen.generate_all_rotations(image)                     # 批量生成旋转图像

    out_dir = args.output or "output/cn_test"                       # 输出目录
    os.makedirs(out_dir, exist_ok=True)                             # 创建输出目录
    labels = ["left", "right", "front"]                             # 方向标签
    for label, img in zip(labels, results):                         # 保存每张结果
        path = os.path.join(out_dir, f"face_{label}.png")           # 输出路径
        from utils import save_image                                # 导入图像保存
        save_image(img, path)                                       # 保存图像
        logger.info(f"已保存: {path}")                              # 日志记录

    logger.info("全部完成！")                                         # 完成提示
