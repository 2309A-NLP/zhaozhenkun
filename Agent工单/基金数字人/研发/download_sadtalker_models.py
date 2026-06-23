# -*- coding: utf-8 -*-
"""
download_sadtalker_models.py — 下载 SadTalker 预训练模型权重
来源：HuggingFace / ModelScope
总大小约 2.5GB

运行方式：
    python download_sadtalker_models.py
    python download_sadtalker_models.py --checkpoint_dir ./checkpoints
"""

import os
import sys
import argparse
from huggingface_hub import hf_hub_download, snapshot_download
from logger import logger  # 统一日志

# SadTalker 需要的所有模型文件
SADTALKER_MODELS = {
    # MappingNet
    "mapping_00109-model.pth.tar": "vinthony/SadTalker",
    "mapping_00229-model.pth.tar": "vinthony/SadTalker",
    # Face Renderer (256 and 512)
    "SadTalker_V0.0.2_256.safetensors": "vinthony/SadTalker",
    "SadTalker_V0.0.2_512.safetensors": "vinthony/SadTalker",
}

# 3DMM 人脸模型（BFM - Basel Face Model）
# 这些也需要，用于3D人脸重建
BFM_FILES = {
    "BFM_model_front.mat": "vinthony/SadTalker",
    "BFM_model_front.mat": None,  # 可从 ModelScope 获取
}

# 面部增强模型（可选，提升画质）
GFPGAN_MODEL = {
    "GFPGANv1.4.pth": "vinthony/SadTalker",
}


def download_from_hf(checkpoint_dir: str):
    """从 HuggingFace 下载 SadTalker 模型"""
    os.makedirs(checkpoint_dir, exist_ok=True)

    logger.info("=" * 55)
    logger.info("  下载 SadTalker 模型权重 (HuggingFace)")
    logger.info("=" * 55)
    logger.info(f"  目标目录: {checkpoint_dir}")
    logger.info(f"  预计大小: ~2.5 GB")
    logger.info("")

    downloaded = 0
    failed = []

    for filename, repo_id in SADTALKER_MODELS.items():
        target = os.path.join(checkpoint_dir, filename)
        if os.path.exists(target):
            size_mb = os.path.getsize(target) / (1024 * 1024)
            logger.info(f"  ✓ {filename} ({size_mb:.1f} MB) [已存在]")
            downloaded += 1
            continue

        logger.info(f"  ⬇ 下载 {filename} ...")
        try:
            path = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                local_dir=checkpoint_dir,
                local_dir_use_symlinks=False,
            )
            size_mb = os.path.getsize(path) / (1024 * 1024)
            logger.info(f"✓ ({size_mb:.1f} MB)")
            downloaded += 1
        except Exception as e:
            logger.error(f"✗ 失败: {e}")
            failed.append(filename)

    # 下载 BFM 模型到子目录
    bfm_dir = os.path.join(checkpoint_dir, "BFM")
    os.makedirs(bfm_dir, exist_ok=True)

    bfm_target = os.path.join(bfm_dir, "BFM_model_front.mat")
    if not os.path.exists(bfm_target):
        logger.info(f"  ⬇ 下载 BFM 模型 ...")
        try:
            hf_hub_download(
                repo_id="vinthony/SadTalker",
                filename="BFM/BFM_model_front.mat",
                local_dir=checkpoint_dir,
                local_dir_use_symlinks=False,
            )
            logger.info("✓")
            downloaded += 1
        except Exception as e:
            logger.error(f"✗ 失败: {e}")
            logger.info(f"    BFM 模型也可以从以下地址手动下载:")
            logger.info(f"    https://github.com/Juyong/3DMMasSTN/releases")
            failed.append("BFM_model_front.mat")

    # 下载 GFPGAN 增强器（可选）
    gfpgan_target = os.path.join(checkpoint_dir, "GFPGANv1.4.pth")
    if not os.path.exists(gfpgan_target):
        logger.info(f"  ⬇ 下载 GFPGAN 增强模型 (可选) ...")
        try:
            # GFPGAN 在独立仓库
            hf_hub_download(
                repo_id="vinthony/SadTalker",
                filename="GFPGANv1.4.pth",
                local_dir=checkpoint_dir,
                local_dir_use_symlinks=False,
            )
            logger.info("✓")
        except Exception:
            logger.info("跳过 (可选)")

    # 下载 gfpgan 子目录
    gfpgan_dir = os.path.join(checkpoint_dir, "gfpgan")
    os.makedirs(gfpgan_dir, exist_ok=True)

    logger.info("")
    logger.info(f"  完成: {downloaded} 个文件已就绪")
    if failed:
        logger.error(f"  失败: {len(failed)} 个文件需要手动下载")
        for f in failed:
            logger.info(f"    - {f}")
        logger.info("")
        logger.info("  手动下载方式:")
        logger.info("  1. HuggingFace: https://huggingface.co/vinthony/SadTalker")
        logger.info("  2. 百度网盘: https://pan.baidu.com/s/1nXuVNzFjD4HjKYZbT6hNQQ?pwd=sadt")

    return downloaded


def download_from_modelscope(checkpoint_dir: str):
    """从 ModelScope 下载（国内用户更快）"""
    try:
        from modelscope.hub.snapshot_download import snapshot_download as ms_snapshot

        logger.info("=" * 55)
        logger.info("  从 ModelScope 下载 SadTalker 模型")
        logger.info("=" * 55)

        # ModelScope 上的 SadTalker 模型
        model_id = "wwd123/SadTalker"

        ms_snapshot(
            model_id=model_id,
            local_dir=checkpoint_dir,
            revision="master",
        )
        logger.info(f"  ✓ 模型已下载到: {checkpoint_dir}")
        return True
    except Exception as e:
        logger.error(f"  ✗ ModelScope 下载失败: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="下载 SadTalker 预训练模型")
    parser.add_argument(
        "--checkpoint_dir",
        type=str,
        default=None,
        help="模型存放目录 (默认: SadTalker/checkpoints)",
    )
    parser.add_argument(
        "--source",
        type=str,
        choices=["huggingface", "modelscope", "auto"],
        default="auto",
        help="下载源 (默认: auto = 先尝试 ModelScope 再 HuggingFace)",
    )
    args = parser.parse_args()

    # 默认路径：与 SadTalker 代码同级
    if args.checkpoint_dir is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        args.checkpoint_dir = os.path.join(
            os.path.dirname(script_dir), "SadTalker", "checkpoints"
        )

    logger.info(f"\nSadTalker 模型下载工具")
    logger.info(f"目标目录: {args.checkpoint_dir}\n")

    if args.source == "modelscope":
        download_from_modelscope(args.checkpoint_dir)
    elif args.source == "huggingface":
        download_from_hf(args.checkpoint_dir)
    else:  # auto
        if not download_from_modelscope(args.checkpoint_dir):
            download_from_hf(args.checkpoint_dir)
