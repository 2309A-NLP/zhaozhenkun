
# -*- coding: utf-8 -*-
"""
==============================================================================
功能说明：命令行主入口模块（集成 Milvus / Redis / BGE-M3）
==============================================================================
本文件是文生图智能体的命令行入口：
  - 解析命令行参数
  - 调用人脸处理器检测面部
  - 调用图像生成器生成三种旋转图像（查 Milvus/Redis 缓存）
  - 调用扩图器对图像进行扩展（查 Redis 缓存）
  - 保存结果并生成对比网格
  - 全部使用 logging 输出

使用方法：
  python main.py --input <输入图像路径> [--output <输出目录>]

工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
==============================================================================
"""

import argparse                              # 命令行参数解析
import os, sys, time                         # 系统模块
import logging                               # 日志模块
import numpy as np                           # 数值计算

# 导入项目模块
from config import setup_logging, log_config, gen_config, controlnet_config, strong_control_config, OUTPUT_DIR
from face_processor import FaceProcessor
from image_generator import ImageGenerator
from outpainter import ImageOutpainter
from strong_control_router import StrongControlRouter
from utils import load_image, save_image, create_comparison_grid, get_timestamp

logger = logging.getLogger(__name__)         # 模块日志器


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="文生图智能体 - 面部旋转与扩图工具")
    parser.add_argument("--input", "-i", type=str, default=None,
                        help="输入面部图像路径（不指定则自动使用 input/ 目录中第一张图片）")
    parser.add_argument("--output", "-o", type=str, default=None, help="输出目录")
    parser.add_argument("--no-outpaint", action="store_true", help="跳过扩图步骤")
    parser.add_argument("--controlnet", "-c", action="store_true",
                        help="使用 ControlNet OpenPose 本地推理模式（无需启动 SD WebUI）")
    parser.add_argument("--seed", "-s", type=int, default=-1, help="随机种子(-1=随机)")
    parser.add_argument("--show-config", action="store_true", help="显示配置后退出")
    parser.add_argument("--all", action="store_true", help="处理 input/ 目录中所有图片")
    return parser.parse_args()


def auto_find_inputs(input_dir: str) -> list:
    """自动扫描 input 目录中的图片文件"""
    exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}
    files = []
    if not os.path.isdir(input_dir):
        return files
    for f in sorted(os.listdir(input_dir)):
        if os.path.splitext(f)[1].lower() in exts:
            files.append(os.path.join(input_dir, f))
    return files


def resolve_input_path(args) -> str:
    """解析输入路径：命令行指定 > 自动扫描 input/ 目录"""
    if args.input:
        if os.path.exists(args.input):
            return args.input
        logger.error(f"指定的输入文件不存在: {args.input}")
        sys.exit(1)

    # 自动扫描
    from config import INPUT_DIR
    candidates = auto_find_inputs(INPUT_DIR)
    if not candidates:
        logger.error(
            f"未指定 --input，且 {INPUT_DIR}/ 目录中没有找到图片文件。\n"
            f"请将照片放入 {INPUT_DIR}/ 或使用 --input 指定路径。"
        )
        sys.exit(1)

    logger.info(f"在 input/ 目录找到 {len(candidates)} 张图片，使用第一张: {os.path.basename(candidates[0])}")
    return candidates[0]


def run_pipeline(args):
    """
    执行完整处理流程：
    1. 加载图像 -> 2. 人脸检测 -> 3. 生成旋转图 -> 4. 扩图 -> 5. 保存
    """
    start_time = time.time()
    logger.info("=" * 60)
    logger.info("文生图智能体 - 开始处理")
    logger.info("=" * 60)

    # ===== 第1步：加载输入图像 =====
    input_path = resolve_input_path(args)
    logger.info(f"第1步：加载输入图像 - {input_path}")
    input_image = load_image(input_path)
    if input_image is None:
        logger.error("输入图像加载失败，程序终止")
        sys.exit(1)
    logger.info(f"图像加载成功，尺寸: {input_image.shape}")

    # 创建输出目录
    output_dir = args.output or os.path.join(OUTPUT_DIR, f"task_{get_timestamp()}")
    os.makedirs(output_dir, exist_ok=True)
    logger.info(f"输出目录: {output_dir}")

    # ===== 第2步：人脸检测与分析 =====
    logger.info("第2步：人脸检测与分析")
    processor = FaceProcessor()

    bbox = processor.detect_face(input_image)
    if bbox is None:
        logger.error("未检测到人脸，程序终止")
        sys.exit(1)
    logger.info(f"检测到人脸边界框: {bbox}")

    landmarks = processor.extract_landmarks(input_image)
    if landmarks is not None:
        logger.info(f"提取到 {len(landmarks)} 个关键点")

    pose = processor.estimate_pose(input_image)
    if pose is not None:
        logger.info(f"当前姿态: yaw={pose[0]:.1f}° pitch={pose[1]:.1f}° roll={pose[2]:.1f}°")

    # ===== 第3步：生成旋转面部图像 =====
    logger.info("第3步：生成旋转面部图像（左转/右转/端正）")
    route_note = "旧版生成器"
    generator = None
    if strong_control_config.enabled:
        router = StrongControlRouter()
        route_result = router.generate_all_rotations(input_image, processor)
        route_note = route_result["status"]

        if route_result["mode"] == "strong" and route_result["images"]:
            rotation_results = route_result["images"]
            logger.info("使用强控制路线 (ComfyUI + IP-Adapter Face) 生成结果")
        elif route_result["mode"] in {"fallback", "strong_offline"} and route_result["images"]:
            rotation_results = route_result["images"]
            logger.warning(route_note)
            generator = ImageGenerator(use_controlnet=controlnet_config.enabled)
        elif not route_result["images"]:
            logger.error(route_result["status"])
            if strong_control_config.allow_fallback:
                logger.info("回退到旧版生成器...")
                generator = ImageGenerator(use_controlnet=controlnet_config.enabled)
                rotation_results = generator.generate_all_rotations(input_image, processor)
            else:
                return
        else:
            rotation_results = route_result["images"]
    else:
        generator = ImageGenerator(use_controlnet=controlnet_config.enabled)
        rotation_results = generator.generate_all_rotations(input_image, processor)

    labels = ["左转(-30°)", "右转(+30°)", "端正(0°)"]
    rotation_paths = []
    for i, (img, label) in enumerate(zip(rotation_results, labels)):
        fname = f"rotation_{i}.png"
        fpath = os.path.join(output_dir, fname)
        save_image(img, fpath)
        rotation_paths.append(fpath)

        # 验证生成质量
        validation = processor.validate_face(img, label)
        if validation["warnings"]:
            for w in validation["warnings"]:
                logger.warning(f"[{label}] {w}")
        else:
            logger.info(
                f"[{label}] ✅ 人脸质量合格 "
                f"(置信度={validation['confidence']:.2f}, "
                f"关键点={validation['landmarks_count']})"
            )
        logger.info(f"旋转图像已保存: {fpath}")

    # ===== 第4步：扩图（可选） =====
    outpaint_results = []
    if not args.no_outpaint and rotation_results:
        logger.info("第4步：执行图像扩图")

        # 尝试 ControlNet 本地扩图（如果 generator 可用且 ControlNet 已启用）
        cn_generator = None
        if generator is not None and controlnet_config.enabled:
            try:
                cn_generator = generator._cn_generator
            except Exception:
                cn_generator = None

        for i, (img, label) in enumerate(zip(rotation_results, labels)):
            try:
                if cn_generator is not None:
                    # ControlNet 本地管线扩图
                    logger.info(f"ControlNet 扩图: {label}")
                    expanded = cn_generator.outpaint(img)
                else:
                    # WebUI API 模式（默认）
                    outpainter = ImageOutpainter()
                    logger.info(f"WebUI 扩图: {label}")
                    expanded = outpainter.outpaint(img)

                fname = f"outpaint_{i}.png"
                fpath = os.path.join(output_dir, fname)
                save_image(expanded, fpath)
                outpaint_results.append(expanded)

                # 验证扩图质量
                h, w = expanded.shape[:2]
                ih, iw = img.shape[:2]
                if w < iw * 0.9 or h < ih * 0.9:
                    logger.warning(f"[{label}] 扩图后尺寸异常: {w}x{h} (原: {iw}x{ih})")

                logger.info(f"扩图结果已保存: {fpath} ({w}x{h})")
            except Exception as e:
                logger.error(f"[{label}] 扩图失败: {e}")
                # 扩图失败不影响整体流程，用原图替代
                outpaint_results.append(img)
    else:
        logger.info("第4步：已跳过扩图（--no-outpaint 或无旋转结果）")

    # ===== 第5步：生成对比网格 =====
    logger.info("第5步：生成对比网格")
    grid = create_comparison_grid(
        images=[input_image] + rotation_results,
        labels=["原图"] + labels,
        cols=4
    )
    grid_path = os.path.join(output_dir, "comparison_grid.png")
    save_image(grid, grid_path)
    logger.info(f"对比网格已保存: {grid_path}")

    # ===== 完成 =====
    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info("处理完成！")
    logger.info(f"总耗时: {elapsed:.1f} 秒")
    logger.info(f"输出目录: {output_dir}")
    logger.info(f"旋转图像: {len(rotation_results)} 张")
    logger.info(f"扩图结果: {len(outpaint_results)} 张")
    logger.info("=" * 60)


def main() -> int:
    """主函数入口"""
    setup_logging()                                        # 初始化日志
    args = parse_arguments()                               # 解析参数

    if args.show_config:                                   # 显示配置
        log_config()
        return 0
    if args.seed != -1:                                    # 更新种子
        gen_config.seed = args.seed

    if args.controlnet:                                    # 启用 ControlNet 模式
        controlnet_config.enabled = True
        logger.info("ControlNet 本地推理模式已启用")

    run_pipeline(args)                                     # 执行处理流程
    return 0


if __name__ == "__main__":
    sys.exit(main())
