# -*- coding: utf-8 -*-
"""
==============================================================================
功能说明：千问图像编辑模型接入验证脚本
==============================================================================
测试 Qwen-Image-Edit-Max 模型是否可正常调用：
  1. 基础连通性测试
  2. 单图编辑测试
  3. 输出保存测试

使用方法:
  python test_qwen_integration.py

工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
==============================================================================
"""

import os
import sys
import logging

# 添加项目根目录到 path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import setup_logging, qwen_config, OUTPUT_DIR
from qwen_image_editor import QwenImageEditor
from qwen_utils import image_to_base64
from qwen_cli import qwen_edit, qwen_edit_and_save

# 初始化日志
setup_logging()
logger = logging.getLogger("test_qwen")


def test_01_module_import():
    """测试 1: 模块导入和基础初始化"""
    logger.info("=" * 60)
    logger.info("测试 1: 模块导入和初始化")
    logger.info("=" * 60)

    try:
        from qwen_image_editor import QwenImageEditor
        from qwen_cli import qwen_edit, qwen_edit_and_save
        logger.info("✅ qwen_image_editor 模块导入成功")
    except Exception as e:
        logger.error(f"❌ 模块导入失败: {e}")
        return False

    try:
        editor = QwenImageEditor()
        logger.info(f"✅ QwenImageEditor 初始化成功")
        logger.info(f"   model: {editor.model}")
        logger.info(f"   base_url: {editor.base_url}")
    except Exception as e:
        logger.error(f"❌ 初始化失败: {e}")
        return False

    return True


def test_02_image_conversion():
    """测试 2: 图像格式转换"""
    logger.info("=" * 60)
    logger.info("测试 2: 图像格式转换")
    logger.info("=" * 60)

    import numpy as np

    # 创建测试图像 (纯色)
    test_img = np.ones((256, 256, 3), dtype=np.uint8) * 128
    test_img[50:200, 50:200] = [255, 0, 0]  # 红色方块

    try:
        b64 = image_to_base64(test_img)
        assert b64.startswith("data:image/png;base64,"), f"格式不正确: {b64[:50]}"
        logger.info(f"✅ numpy 数组 → Base64 转换成功 (长度={len(b64)})")
    except Exception as e:
        logger.error(f"❌ 图像转换失败: {e}")
        return False

    return True


def test_03_api_call():
    """测试 3: 实际 API 调用 (单图编辑)"""
    logger.info("=" * 60)
    logger.info("测试 3: API 调用测试 (qwen-image-edit-max)")
    logger.info("=" * 60)

    # 查找测试图像
    from config import INPUT_DIR
    test_images = []
    for ext in [".png", ".jpg", ".jpeg"]:
        for f in os.listdir(INPUT_DIR) if os.path.isdir(INPUT_DIR) else []:
            if f.lower().endswith(ext):
                test_images.append(os.path.join(INPUT_DIR, f))

    if not test_images:
        logger.error("❌ 未找到测试图像，请将图像放入 input/ 目录")
        return False

    test_image = test_images[0]
    logger.info(f"使用测试图像: {test_image}")

    try:
        editor = QwenImageEditor()

        result = editor.edit(
            images=[test_image],
            prompt="增强图像质量，使画面更清晰、色彩更自然",
            n=1,
            size="1024*1024",
        )

        if result["success"]:
            logger.info(f"✅ API 调用成功!")
            logger.info(f"   生成图像数: {len(result['images'])}")
            logger.info(f"   URL 数: {len(result['urls'])}")
            if result["usage"]:
                logger.info(f"   Token 用量: {result['usage']}")

            # 保存测试结果
            if result["images"]:
                import cv2
                test_out_dir = os.path.join(OUTPUT_DIR, "qwen_test")
                os.makedirs(test_out_dir, exist_ok=True)
                for i, img in enumerate(result["images"]):
                    path = os.path.join(test_out_dir, f"test_result_{i}.png")
                    cv2.imwrite(path, img)
                    logger.info(f"   已保存: {path}")
        else:
            logger.error(f"❌ API 调用失败: {result['error']}")
            return False

    except Exception as e:
        logger.error(f"❌ API 调用异常: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


def test_04_edit_and_save():
    """测试 4: edit_and_save 便捷方法"""
    logger.info("=" * 60)
    logger.info("测试 4: edit_and_save 便捷方法")
    logger.info("=" * 60)

    from config import INPUT_DIR

    test_images = []
    if os.path.isdir(INPUT_DIR):
        for f in os.listdir(INPUT_DIR):
            if f.lower().endswith((".png", ".jpg", ".jpeg")):
                test_images.append(os.path.join(INPUT_DIR, f))

    if not test_images:
        logger.error("❌ 未找到测试图像")
        return False

    try:
        from qwen_cli import qwen_edit_and_save

        result = qwen_edit_and_save(
            images=[test_images[0]],
            prompt="保持人物不变，将背景虚化处理",
            output_dir=os.path.join(OUTPUT_DIR, "qwen_test2"),
            n=1,
            size="1024*1024",
        )

        if result["success"]:
            logger.info(f"✅ edit_and_save 成功!")
            for p in result["local_paths"]:
                logger.info(f"   已保存: {p}")
        else:
            logger.error(f"❌ edit_and_save 失败: {result['error']}")
            return False

    except Exception as e:
        logger.error(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True


def main():
    logger.info("=" * 60)
    logger.info("千问图像编辑模型 (Qwen-Image-Edit-Max) 接入验证")
    logger.info(f"API URL: {qwen_config.base_url}")
    logger.info(f"Model: {qwen_config.model}")
    logger.info("=" * 60)

    results = {}

    # 测试 1: 模块导入
    results["模块导入"] = test_01_module_import()

    # 测试 2: 图像转换
    results["图像转换"] = test_02_image_conversion()

    # 测试 3: API 调用
    if results["模块导入"]:
        results["API调用"] = test_03_api_call()
    else:
        results["API调用"] = False

    # 测试 4: edit_and_save
    if results["API调用"]:
        results["edit_and_save"] = test_04_edit_and_save()
    else:
        results["edit_and_save"] = False

    # 汇总
    logger.info("=" * 60)
    logger.info("验证结果汇总:")
    for name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        logger.info(f"  {name}: {status}")

    all_passed = all(results.values())
    if all_passed:
        logger.info("🎉 所有测试通过！千问模型已成功接入项目。")
    else:
        logger.warning("⚠️ 部分测试失败，请检查日志。")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
