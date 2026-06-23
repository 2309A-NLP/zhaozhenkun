# -*- coding: utf-8 -*-
"""
==============================================================================
功能说明：千问图像编辑便捷函数 + 命令行入口模块
==============================================================================
本文件提供：
  - qwen_edit(): 一行代码调用千问图像编辑
  - qwen_edit_and_save(): 一行代码编辑并保存到本地
  - 命令行入口: python qwen_cli.py -i img1.png -p "编辑指令"

依赖：qwen_image_editor.QwenImageEditor

工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
==============================================================================
"""

import os  # 路径处理
import sys  # 退出码
import logging  # 日志
from typing import Dict, List, Union  # 类型提示

import numpy as np  # 数组类型
from PIL import Image  # PIL 图像类型

from qwen_image_editor import QwenImageEditor  # 千问编辑器核心类

logger = logging.getLogger(__name__)  # 模块日志器


def qwen_edit(
    images: List[Union[str, np.ndarray]],
    prompt: str,
    **kwargs,
) -> Dict:
    """便捷函数：使用默认配置进行图像编辑

    一行代码即可调用千问模型。配置从 config.qwen_config 自动读取。

    示例:
        result = qwen_edit(
            images=["face.jpg"],
            prompt="将照片背景替换为海滩日落场景",
            n=1,
        )
        if result["success"]:
            cv2.imwrite("output.jpg", result["images"][0])

    Returns:
        {"success": bool, "images": [np.ndarray], "urls": [str], "usage": {...}, "error": str}
    """
    editor = QwenImageEditor()  # 使用默认配置
    return editor.edit(images=images, prompt=prompt, **kwargs)


def qwen_edit_and_save(
    images: List[Union[str, np.ndarray]],
    prompt: str,
    output_dir: str = None,
    **kwargs,
) -> Dict:
    """便捷函数：编辑图像并自动保存到本地

    示例:
        result = qwen_edit_and_save(
            images=["face.jpg"],
            prompt="转换为油画风格",
            output_dir="output/qwen",
        )

    Returns:
        {"success": bool, "local_paths": [str], "urls": [str], "usage": {...}, "error": str}
    """
    editor = QwenImageEditor()  # 使用默认配置
    return editor.edit_and_save(
        images=images, prompt=prompt, output_dir=output_dir, **kwargs
    )


# ================================================================
# 命令行入口
# ================================================================
if __name__ == "__main__":
    import argparse  # 命令行解析

    # 配置日志格式
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # 解析命令行参数
    parser = argparse.ArgumentParser(
        description="千问图像编辑模型 (Qwen-Image-Edit-Max) 命令行工具"
    )
    parser.add_argument(
        "--images", "-i", nargs="+", required=True,
        help="输入图像路径 (1-3 张)"
    )
    parser.add_argument(
        "--prompt", "-p", required=True,
        help="编辑指令文本"
    )
    parser.add_argument(
        "--output", "-o", default=None,
        help="输出目录 (默认 output/qwen_edits/)"
    )
    parser.add_argument(
        "--n", type=int, default=1,
        help="输出图片数量 (1-6, 默认1)"
    )
    parser.add_argument(
        "--size", default="1024*1024",
        help="输出分辨率 (默认 1024*1024)"
    )
    parser.add_argument(
        "--negative", default="",
        help="反向提示词"
    )
    parser.add_argument(
        "--no-prompt-extend", action="store_true",
        help="禁用提示词扩展"
    )
    parser.add_argument(
        "--seed", type=int, default=-1,
        help="随机种子 (-1=随机)"
    )
    args = parser.parse_args()

    # 校验输入文件
    for f in args.images:
        if not os.path.exists(f):
            logger.error(f"输入文件不存在: {f}")
            sys.exit(1)

    logger.info(f"输入图像: {args.images}")
    logger.info(f"编辑指令: {args.prompt}")

    # 执行编辑并保存
    result = qwen_edit_and_save(
        images=args.images,
        prompt=args.prompt,
        output_dir=args.output,
        n=args.n,
        size=args.size,
        negative_prompt=args.negative,
        prompt_extend=not args.no_prompt_extend,
        seed=args.seed if args.seed >= 0 else None,
    )

    # 输出结果
    if result["success"]:
        logger.info(f"编辑成功！已保存 {len(result['local_paths'])} 张图像:")
        for p in result["local_paths"]:
            logger.info(f"  {p}")
        sys.exit(0)
    else:
        logger.error(f"编辑失败: {result['error']}")
        sys.exit(1)
