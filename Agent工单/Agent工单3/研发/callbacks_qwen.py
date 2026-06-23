# -*- coding: utf-8 -*-
"""
==============================================================================
功能说明：千问相关回调函数模块
==============================================================================
本文件包含与千问 Qwen-Image-Edit-Max 相关的 Gradio 回调函数：
  - qwen_edit_images: 千问AI自由编辑 Tab 的回调
  - outpaint_single: 单独扩图 Tab 的回调（使用千问）
  - get_status: 系统状态检测（含千问模型检测）
  - _init_qwen: 千问编辑器懒加载

依赖：qwen_image_editor, utils, config

工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
==============================================================================
"""

import cv2  # 图像处理
import os  # 路径操作
import logging  # 日志

from config import OUTPUT_DIR, qwen_config, controlnet_config  # 配置
from utils import save_image  # 图像保存

logger = logging.getLogger(__name__)  # 模块日志器

_qwen_editor = None  # 千问编辑器全局单例


def _format_error(title: str, error: Exception) -> str:
    """统一格式化错误消息"""
    text = str(error).strip() or repr(error)
    logger.error(f"{title}: {text}")
    return f"❌ {title}: {text}"


def _init_qwen():
    """懒加载千问图像编辑器"""
    global _qwen_editor
    if _qwen_editor is None:
        from qwen_image_editor import QwenImageEditor
        _qwen_editor = QwenImageEditor()
        logger.info("千问图像编辑器已加载")


def qwen_edit_images(img1, img2, img3, prompt, n_images, size, negative, prompt_extend):
    """千问AI编辑回调：支持1-3张输入图 + 文本指令"""
    if not prompt or not prompt.strip():
        return [None] * 6 + ["⚠️ 请输入编辑指令"]

    # 收集非空输入图像
    input_images = [img for img in [img1, img2, img3] if img is not None]
    if not input_images:
        return [None] * 6 + ["⚠️ 请至少上传一张图像"]

    try:
        _init_qwen()
        bgr_images = [cv2.cvtColor(img, cv2.COLOR_RGB2BGR) for img in input_images]  # RGB→BGR

        result = _qwen_editor.edit(
            images=bgr_images, prompt=prompt.strip(), n=int(n_images),
            size=size, negative_prompt=negative.strip() if negative else None,
            prompt_extend=prompt_extend,
        )

        if not result["success"]:
            return [None] * 6 + [f"❌ {result['error']}"]

        # BGR→RGB 显示 + 保存
        outputs = [cv2.cvtColor(img, cv2.COLOR_BGR2RGB) for img in result["images"]]
        while len(outputs) < 6:
            outputs.append(None)

        save_dir = os.path.join(OUTPUT_DIR, "face_rotation")
        os.makedirs(save_dir, exist_ok=True)
        for i, img_bgr in enumerate(result["images"]):
            save_image(img_bgr, os.path.join(save_dir, f"qwen_edit_{i}.png"))

        status = (f"✅ 千问编辑完成！\n📁 {save_dir}\n"
                  f"🖼️ {len(result['images'])} 张 | 🤖 {qwen_config.model}")
        return outputs[0], outputs[1], outputs[2], outputs[3], outputs[4], outputs[5], status

    except Exception as e:
        return [None] * 6 + [_format_error("千问编辑失败", e)]


def outpaint_single(image, ratio):
    """单独扩图回调（使用千问模型）"""
    if image is None:
        return None, "⚠️ 请先上传图像"
    try:
        _init_qwen()
        bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

        result = _qwen_editor.edit(
            images=[bgr], n=1, size="1280*1280",
            prompt="扩展图像画布，填充人物上半身和背景，保持人物身份完全不变，自然无缝扩展",
        )

        if not result["success"] or not result["images"]:
            return None, _format_error("扩图失败", Exception(result.get("error", "未知")))

        output_img = result["images"][0]
        result_rgb = cv2.cvtColor(output_img, cv2.COLOR_BGR2RGB)

        save_dir = os.path.join(OUTPUT_DIR, "face_rotation")
        os.makedirs(save_dir, exist_ok=True)
        path = os.path.join(save_dir, "outpaint_single.png")
        save_image(output_img, path)

        return result_rgb, f"✅ 扩图完成！{result_rgb.shape[1]}x{result_rgb.shape[0]} 保存在: {path}"
    except Exception as e:
        return None, _format_error("扩图失败", e)


def get_status():
    """获取系统运行状态"""
    import requests
    lines = ["### 🖥️ 系统状态\n"]

    # SD WebUI
    try:
        resp = requests.get("http://127.0.0.1:7861/sdapi/v1/progress", timeout=5)
        if resp.status_code == 200:
            lines.append("- **SD WebUI**: ✅ 运行中 (端口 7861)")
        else:
            lines.append(f"- **SD WebUI**: ⚠️ 异常 (HTTP {resp.status_code})")
    except Exception:
        lines.append("- **SD WebUI**: ❌ 未运行")

    # PyTorch
    try:
        import torch
        lines.append(f"- **PyTorch**: ✅ {torch.__version__}, CUDA: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            gb = torch.cuda.get_device_properties(0).total_mem / 1024 ** 3
            lines.append(f"- **GPU 显存**: {gb:.1f} GB")
    except Exception:
        lines.append("- **PyTorch**: ❌ 未安装")

    # MediaPipe
    try:
        import mediapipe
        lines.append(f"- **MediaPipe**: ✅ {mediapipe.__version__}")
    except Exception:
        lines.append("- **MediaPipe**: ❌ 未安装")

    # 千问
    try:
        import dashscope  # noqa: F401
        from qwen_image_editor import QwenImageEditor  # noqa: F401
        lines.append(f"- **千问AI编辑**: ✅ 可用 ({qwen_config.model})")
    except Exception as e:
        lines.append(f"- **千问AI编辑**: ⚠️ 未就绪 ({e})")

    # ControlNet
    try:
        from controlnet_generator import ControlNetGenerator  # noqa: F401
        lines.append("- **ControlNet 本地**: ✅ 可用 (SD 1.5 + OpenPose)")
        lines.append(f"  - ControlNet 模型: {'✅' if os.path.exists(controlnet_config.controlnet_model_path) else '❌'}")
        lines.append(f"  - SD 模型: {'✅' if os.path.exists(controlnet_config.sd_model_path) else '❌'}")
    except ImportError as e:
        lines.append(f"- **ControlNet 本地**: ⚠️ 部分依赖缺失 ({e})")

    return "\n".join(lines)
