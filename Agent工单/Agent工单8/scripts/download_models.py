#!/usr/bin/env python3
"""
scripts/download_models.py - 模型权重下载脚本
功能: 下载Wav2Lip等模型权重文件。
      对应工单需求: 唇形同步模型可运行
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import os
import sys
import argparse
import logging
import subprocess
from pathlib import Path

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"

# 模型下载配置
MODELS = {
    "wav2lip_gan": {
        "name": "Wav2Lip GAN 主模型",
        "url": "https://github.com/Rudrabha/Wav2Lip/raw/master/checkpoints/wav2lip_gan.pth",
        "path": MODELS_DIR / "wav2lip" / "wav2lip_288.pth",
        "size_mb": 320,
        "required": True,
    },
    "s3fd": {
        "name": "SFD 人脸检测模型",
        "url": "https://github.com/Rudrabha/Wav2Lip/raw/master/face_detection/detection/sfd/s3fd.pth",
        "path": MODELS_DIR / "wav2lip" / "s3fd.pth",
        "size_mb": 35,
        "required": False,
    },
    "wav2lip_quality": {
        "name": "Wav2Lip 质量增强模型",
        "url": "https://github.com/Rudrabha/Wav2Lip/raw/master/checkpoints/wav2lip_gan.pth",
        "path": MODELS_DIR / "wav2lip" / "visual_quality_disc.pth",
        "size_mb": 320,
        "required": False,
    },
}

# 备选下载方式
ALT_SOURCES = {
    "wav2lip_gan": [
        "https://huggingface.co/spaces/akhaliq/Wav2Lip/resolve/main/wav2lip_gan.pth",
        "https://iiitaphyd-my.sharepoint.com/personal/radrabha_m_research_iiit_ac_in/_layouts/15/download.aspx?share=EdjI7bZlgApMqsVoEUUXpLsBxqXbn5z8VTmoxp55YNDcIA",
    ],
}


def check_disk_space(min_mb: int = 500) -> bool:
    """检查磁盘空间是否足够。"""
    try:
        import shutil
        usage = shutil.disk_usage(MODELS_DIR)
        free_mb = usage.free / (1024 * 1024)
        if free_mb < min_mb:
            logger.warning(f"磁盘剩余空间不足: {free_mb:.0f}MB < {min_mb}MB")
            return False
        logger.info(f"磁盘剩余空间: {free_mb:.0f}MB OK")
        return True
    except Exception:
        return True  # 无法检测时默认放行


def download_file(url: str, dest: Path, desc: str = "") -> bool:
    """下载文件，支持 wget/curl/requests 三种方式。"""
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        size_mb = dest.stat().st_size / (1024 * 1024)
        logger.info(f"  {desc} 已存在 ({size_mb:.1f}MB)，跳过")
        return True

    logger.info(f"  下载 {desc}...")
    logger.info(f"    URL: {url}")
    logger.info(f"    目标: {dest}")

    # 方式1: Python requests (支持进度条)
    try:
        import requests
        resp = requests.get(url, stream=True, timeout=30,
                           headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = downloaded * 100 // total
                        print(f"\r  进度: {pct}% ({downloaded//(1024*1024)}MB)", end="")
            print()
            logger.info(f"  ✓ {desc} 下载完成")
            return True
        else:
            logger.warning(f"  HTTP {resp.status_code}")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"  requests失败: {e}")

    # 方式2: wget
    try:
        subprocess.run(["wget", "-q", "--show-progress", "-O", str(dest), url],
                       check=True, timeout=600)
        logger.info(f"  ✓ {desc} 下载完成")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # 方式3: curl
    try:
        subprocess.run(["curl", "-L", "-o", str(dest), "--progress-bar", url],
                       check=True, timeout=600)
        logger.info(f"  ✓ {desc} 下载完成")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    logger.error(f"  ✗ {desc} 下载失败，请手动下载放到: {dest}")
    return False


def verify_model(path: Path) -> bool:
    """验证模型文件是否有效（至少>1MB）。"""
    if not path.exists():
        return False
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb < 1:
        logger.warning(f"  {path.name} 文件太小({size_mb:.1f}MB)，可能损坏")
        return False
    return True


def print_manual_instructions(model_key: str):
    """打印手动下载指南。"""
    model = MODELS[model_key]
    logger.info(f"\n{'='*60}")
    logger.info(f"  手动下载: {model['name']}")
    logger.info(f"{'='*60}")
    logger.info(f"1. 浏览器打开以下任一链接:")
    logger.info(f"   {model['url']}")
    for alt in ALT_SOURCES.get(model_key, []):
        logger.info(f"   {alt}")
    logger.info(f"2. 下载到: {model['path']}")
    logger.info(f"3. 重命名为: {model['path'].name}")
    logger.info(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="下载数字人模型权重")
    parser.add_argument("--all", action="store_true", default=True,
                        help="下载所有模型(默认)")
    parser.add_argument("--required-only", action="store_true",
                        help="仅下载必需模型")
    parser.add_argument("--model", choices=list(MODELS.keys()),
                        help="下载指定模型")
    parser.add_argument("--check", action="store_true",
                        help="仅检查模型状态，不下载")
    parser.add_argument("--help-manual", action="store_true",
                        help="显示所有模型的手动下载指南")
    args = parser.parse_args()

    logger.info("=" * 50)
    logger.info("  数字人模型下载工具")
    logger.info(f"  项目路径: {PROJECT_ROOT}")
    logger.info("=" * 50)

    if args.help_manual:
        for key in MODELS:
            print_manual_instructions(key)
        return

    # 检查磁盘空间
    if not check_disk_space(500):
        logger.error("磁盘空间不足，请清理后重试")
        sys.exit(1)

    # 选择要下载的模型
    if args.model:
        targets = {args.model: MODELS[args.model]}
    elif args.required_only:
        targets = {k: v for k, v in MODELS.items() if v["required"]}
    else:
        targets = MODELS

    if args.check:
        logger.info("仅检查模型状态:\n")
        all_ok = True
        for key, model in targets.items():
            exists = model["path"].exists()
            size = model["path"].stat().st_size / (1024 * 1024) if exists else 0
            status = f"✓ {size:.0f}MB" if exists else "✗ 缺失"
            required = "[必需]" if model["required"] else "[可选]"
            logger.info(f"  {required} {model['name']:30s} {status}")
            if model["required"] and not exists:
                all_ok = False
        if not all_ok:
            logger.info("\n运行 python scripts/download_models.py 下载缺失模型")
        return

    # 下载
    success = 0
    failed = 0

    for key, model in targets.items():
        logger.info(f"\n[{model['name']}] (~{model['size_mb']}MB)")
        if download_file(model["url"], model["path"], model["name"]):
            if verify_model(model["path"]):
                success += 1
            else:
                failed += 1
                # 尝试备选源
                for alt_url in ALT_SOURCES.get(key, []):
                    logger.info(f"  尝试备选源...")
                    if download_file(alt_url, model["path"], model["name"]):
                        if verify_model(model["path"]):
                            success += 1
                            failed -= 1
                            break
                else:
                    print_manual_instructions(key)
        else:
            failed += 1
            # 尝试备选源
            for alt_url in ALT_SOURCES.get(key, []):
                logger.info(f"  尝试备选源...")
                if download_file(alt_url, model["path"], model["name"]):
                    if verify_model(model["path"]):
                        success += 1
                        failed -= 1
                        break
            else:
                print_manual_instructions(key)

    logger.info(f"\n{'='*50}")
    logger.info(f"  下载完成: {success} 成功, {failed} 失败")
    logger.info(f"{'='*50}")

    if failed > 0:
        logger.warning("部分模型下载失败，请手动下载或使用 --help-manual 查看指南")
        sys.exit(1)


if __name__ == "__main__":
    main()
