# -*- coding: utf-8 -*-
"""
linly_talker.py — Linly-Talker 数字人引擎适配器
--------------------------------------------------------------
功能: 将 Linly-Talker 数字人能力集成到 Agent工单9 项目中。
      复用已有的 SadTalker + GPT-SoVITS + FunASR 模型，
      通过统一接口对外提供 Linly-Talker 风格的数字人服务。

Linly-Talker 官方仓库: https://github.com/Kedreamix/Linly-Talker
本地已链接模型:
  - SadTalker checkpoints ← /home/zzy/SadTalker_modelscope/
  - Qwen LLM ← /home/zzy/models/Qwen3-0.6B-Base
  - GFPGAN ← /home/zzy/SadTalker_modelscope/gfpgan

工单编号: 人工智能NLP-Agent数字人项目-数字人与智能体的集成任务
所属目录: 研发
"""
import os, sys, logging  # 标准库
import numpy as np       # 数值计算

logger = logging.getLogger("digital_human")

# ================================================================
# Linly-Talker 模型路径（优先复用已有模型）
# ================================================================
LINLY_TALKER_ROOT = "/home/zzy/Linly-Talker"                     # Linly-Talker 仓库根目录

# SadTalker 路径（从已有模型链接）
SADTALKER_ROOT = "/home/zzy/SadTalker_modelscope"
SADTALKER_CHECKPOINTS = os.path.join(SADTALKER_ROOT, "checkpoints")
SADTALKER_SRC = os.path.join(SADTALKER_ROOT, "src")
SADTALKER_CONFIG = os.path.join(SADTALKER_SRC, "config")

# Qwen LLM 路径（从已有模型链接）
QWEN_MODEL_PATH = "/home/zzy/models/Qwen3-0.6B-Base"

# GPT-SoVITS 路径（Linly-Talker 自带目录结构）
GPT_SOVITS_ROOT = os.path.join(LINLY_TALKER_ROOT, "GPT_SoVITS")
GPT_SOVITS_PRETRAINED = os.path.join(GPT_SOVITS_ROOT, "pretrained_models")

# MuseTalk 路径（待下载）
MUSETALK_ROOT = os.path.join(LINLY_TALKER_ROOT, "Musetalk")
MUSETALK_MODELS = os.path.join(MUSETALK_ROOT, "models")


def check_models_status() -> dict:
    """检查 Linly-Talker 各模型组件的就绪状态。

    返回:
        dict: {组件名: {"status": "ready"/"missing"/"partial", "path": str, "size": str}}
    """
    def _dir_size(path):
        if not os.path.exists(path): return "N/A"
        total = sum(os.path.getsize(os.path.join(dirpath, f))
                    for dirpath, _, filenames in os.walk(path)
                    for f in filenames)
        if total > 1024**3: return f"{total/1024**3:.1f}GB"
        if total > 1024**2: return f"{total/1024**2:.0f}MB"
        return f"{total/1024:.0f}KB"

    return {
        "SadTalker": {
            "status": "ready" if os.path.exists(os.path.join(
                SADTALKER_CHECKPOINTS, "SadTalker_V0.0.2_512.safetensors"
            )) else "missing",
            "path": SADTALKER_CHECKPOINTS,
            "size": _dir_size(SADTALKER_CHECKPOINTS),
        },
        "Qwen_LLM": {
            "status": "ready" if os.path.exists(os.path.join(
                QWEN_MODEL_PATH, "model.safetensors"
            )) else "missing",
            "path": QWEN_MODEL_PATH,
            "size": _dir_size(QWEN_MODEL_PATH),
        },
        "GPT_SoVITS": {
            "status": "ready" if os.path.exists(GPT_SOVITS_PRETRAINED) else "partial",
            "path": GPT_SOVITS_PRETRAINED,
            "size": _dir_size(GPT_SOVITS_PRETRAINED),
        },
        "MuseTalk": {
            "status": "ready" if os.path.exists(MUSETALK_MODELS) else "missing",
            "path": MUSETALK_MODELS,
            "size": _dir_size(MUSETALK_MODELS),
            "note": "可后续下载: https://github.com/Kedreamix/Linly-Talker",
        },
        "GFPGAN": {
            "status": "ready" if os.path.exists(os.path.join(
                SADTALKER_ROOT, "gfpgan", "weights", "GFPGANv1.4.pth"
            )) else "missing",
            "path": os.path.join(SADTALKER_ROOT, "gfpgan"),
            "size": _dir_size(os.path.join(SADTALKER_ROOT, "gfpgan")),
        },
    }


def get_linly_download_script() -> str:
    """生成下载缺失模型的 shell 脚本（可在网络好时执行）。

    返回:
        str: 可执行的 bash 脚本内容
    """
    return """#!/bin/bash
# Linly-Talker 缺失模型下载脚本
# 在网络良好时执行此脚本下载剩余模型
# 生成时间: 2026-06-24

set -e
cd /home/zzy/Linly-Talker

echo "=== 下载 GPT_SoVITS 预训练模型 ==="
pip install modelscope -q
python3 -c "
from modelscope import snapshot_download
snapshot_download('Kedreamix/Linly-Talker',
    allow_file_pattern='GPT_SoVITS/pretrained_models/*',
    cache_dir='./Linly-Talker-Models')
echo 'GPT_SoVITS downloaded'
"

echo "=== 下载 MuseTalk 模型 ==="
python3 -c "
from modelscope import snapshot_download
snapshot_download('Kedreamix/Linly-Talker',
    allow_file_pattern='MuseTalk/*',
    cache_dir='./Linly-Talker-Models')
echo 'MuseTalk downloaded'
"

echo "=== 下载 CosyVoice TTS 模型 ==="
python3 -c "
from modelscope import snapshot_download
snapshot_download('Kedreamix/Linly-Talker',
    allow_file_pattern='checkpoints/CosyVoice_ckpt/*',
    cache_dir='./Linly-Talker-Models')
echo 'CosyVoice downloaded'
"

echo ""
echo "所有模型下载完成！"
echo "请运行: python3 linly_move_models.py 将模型移到正确目录"
"""


# ================================================================
# 自测
# ================================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                        datefmt="%H:%M:%S")
    print("Linly-Talker 模型状态检查:")
    print("=" * 50)
    status = check_models_status()
    for name, info in status.items():
        icon = "✅" if info["status"] == "ready" else ("⚠️" if info["status"] == "partial" else "❌")
        note = f" — {info['note']}" if info.get('note') else ""
        print(f"  {icon} {name}: {info['status']} ({info['size']}){note}")
    print("=" * 50)
    ready = sum(1 for v in status.values() if v["status"] == "ready")
    total = len(status)
    print(f"就绪: {ready}/{total}")

    # 生成下载脚本
    script = get_linly_download_script()
    script_path = "/home/zzy/Linly-Talker/download_missing_models.sh"
    with open(script_path, 'w') as f:
        f.write(script)
    print(f"\n📝 缺失模型下载脚本已生成: {script_path}")
    print("   网络好时运行: bash download_missing_models.sh")
