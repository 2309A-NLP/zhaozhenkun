# -*- coding: utf-8 -*-
"""
==============================================================================
功能说明：Prompt 模板常量模块
==============================================================================
本文件定义了文生图智能体项目中使用的所有 Prompt 模板，包括：
  - FACE_PROMPT_TEMPLATE: 面部旋转正面 prompt（SD WebUI / ControlNet 用）
  - FACE_NEGATIVE_PROMPT: 面部旋转负向 prompt
  - FACE_CONTROLNET_TEMPLATE: ControlNet OpenPose 专用 prompt 模板

这些常量原本在 config.py 中，单独抽出便于维护和复用。

工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
==============================================================================
"""

# ============================================================
# 面部旋转 Prompt 模板
# ============================================================

# 正向 prompt：用于 img2img 面部旋转（{direction} 处填入朝向描述）
FACE_PROMPT_TEMPLATE = (
    "same person, same face, same identity, "
    "exactly the same facial features, same eyes, same nose, same mouth, "
    "same skin tone, same hair, same hairstyle, "
    "{direction}, "
    "high quality, sharp focus, natural lighting, "
    "photo-realistic, 8k, professional portrait photography, "
    "Canon EOS 5D, 85mm lens, f/1.8"
)

# 负向 prompt：避免身份变化和图像质量下降
FACE_NEGATIVE_PROMPT = (
    "different person, different face, different identity, "
    "different eyes, different nose, different mouth, "
    "changed face, altered features, gender change, age change, "
    "deformed face, asymmetric face, bad anatomy, distorted features, "
    "blurry, motion blur, out of focus, pixelated, low quality, "
    "ugly, disfigured, unnatural skin, plastic skin, "
    "watermark, text, signature, logo, extra fingers, "
    "harsh lighting, overexposed, underexposed"
)

# ControlNet OpenPose 专用模板（配合骨架图使用，prompt 更简洁）
FACE_CONTROLNET_TEMPLATE = (
    "same person, same face, same identity, "
    "same facial structure, same features, "
    "{direction}, "
    "professional portrait, studio lighting, sharp, 8k"
)
