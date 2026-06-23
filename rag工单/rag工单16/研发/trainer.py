# -*- coding: utf-8 -*-
"""
微调启动器模块 — 执行LoRA微调训练并监控训练过程。

功能说明：
- 检查LLaMA-Factory环境是否就绪
- 生成微调配置（调用train_config模块）
- 启动LoRA微调训练（使用llamafactory-cli命令）
- 监控训练损失和评估指标
- 训练完成后导出微调后的模型
- 提供训练日志和可视化数据
"""
import logging  # 导入logging模块，用于结构化日志输出

logger = logging.getLogger(__name__)  # 获取当前模块的logger
import subprocess  # 导入subprocess，用于执行系统命令
import sys  # 导入sys模块
from pathlib import Path  # 导入Path类


def check_environment(config):
    """
    检查微调环境是否就绪。

    参数:
        config: 配置模块引用

    返回:
        环境检查结果字典
    """
    logger.info("正在检查微调环境...")
    env_status = {
        "llamafactory_installed": False,
        "torch_available": False,
        "cuda_available": False,
        "data_ready": False,
    }

    # 检查LLaMA-Factory
    try:
        import llamafactory
        env_status["llamafactory_installed"] = True
        logger.info("  ✅ LLaMA-Factory: 已安装")
    except ImportError:
        logger.warning("  ⚠️ LLaMA-Factory: 未安装")

    # 检查PyTorch和CUDA
    try:
        import torch
        env_status["torch_available"] = True
        env_status["cuda_available"] = torch.cuda.is_available()
        if env_status["cuda_available"]:
            logger.info(f"  ✅ CUDA: 可用 ({torch.cuda.get_device_name(0)})")
        else:
            logger.warning("  ⚠️ CUDA: 不可用（将使用CPU训练，速度较慢）")
    except ImportError:
        logger.warning("  ⚠️ PyTorch: 未安装")

    # 检查llamafactory-cli命令
    try:
        r = subprocess.run(["llamafactory-cli", "--help"],
                          capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            logger.info("  ✅ llamafactory-cli: 可用")
            env_status["cli_available"] = True
        else:
            env_status["cli_available"] = False
            logger.warning("  ⚠️ llamafactory-cli: 命令异常")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        env_status["cli_available"] = False
        logger.warning("  ⚠️ llamafactory-cli: 未找到（可用模拟模式）")

    # 检查微调数据
    ft_path = Path(config.OUTPUT_DIR) / "vlm_finetune_data.jsonl"
    if ft_path.exists():
        file_size = ft_path.stat().st_size
        env_status["data_ready"] = file_size > 100
        if env_status["data_ready"]:
            logger.info(f"  ✅ 微调数据: 就绪 ({file_size // 1024}KB)")
        else:
            logger.warning("  ⚠️ 微调数据: 文件为空或过小")
    else:
        logger.warning("  ⚠️ 微调数据: 未找到，请先运行 data_prep.py")

    return env_status


def run_training(config, yaml_path, mock_mode=False):
    """
    启动LoRA微调训练。

    参数:
        config: 配置模块引用
        yaml_path: YAML配置文件路径
        mock_mode: 是否使用模拟模式

    返回:
        训练结果字典
    """
    logger.info(f"\n🎯 启动LoRA微调训练...")

    if mock_mode:
        logger.info("  🧪 模拟模式：模拟训练过程（用于测试流程）")
        return _mock_training(config)

    # 检查llamafactory-cli
    try:
        subprocess.run(["llamafactory-cli", "--help"],
                      capture_output=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        logger.warning("  ⚠️ llamafactory-cli不可用，切换至模拟模式")
        return _mock_training(config)

    # ===== 构建训练命令 =====
    cmd = ["llamafactory-cli", "train", yaml_path]

    logger.info(f"  运行命令: {' '.join(cmd)}")
    logger.info(f"  配置文件: {yaml_path}")
    logger.info(f"  基础模型: {config.BASE_MODEL}")
    logger.info(f"  训练数据: {config.OUTPUT_DIR}/vlm_finetune_data.jsonl")
    logger.info(f"  开始训练...（训练日志将实时输出）\n")

    try:
        # 实时输出训练日志
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        # 逐行读取输出
        last_loss = None
        for line in iter(process.stdout.readline, ""):
            logger.info(f"  {line}", end="")
            # 提取loss值
            if "loss:" in line.lower():
                import re
                m = re.search(r'loss[=:]\s*([\d.]+)', line)
                if m:
                    last_loss = float(m.group(1))

        process.wait()
        success = process.returncode == 0

        if success:
            logger.info(f"\n  ✅ 训练完成！最终loss: {last_loss:.4f}" if last_loss
                  else "\n  ✅ 训练完成！")
        else:
            logger.error(f"\n  ❌ 训练失败 (exit code: {process.returncode})")

        return {
            "success": success,
            "output_dir": str(Path(config.OUTPUT_DIR) / "checkpoints"),
            "final_loss": last_loss,
        }

    except Exception as e:
        logger.error(f"  ❌ 训练出错: {e}")
        return {"success": False, "error": str(e)}


def _mock_training(config):
    """模拟训练过程（用于测试和演示）。"""
    logger.info("\n  📊 模拟训练进度:")
    import time
    total_steps = 50
    for step in range(1, total_steps + 1):
        time.sleep(0.02)
        if step % 10 == 0:
            loss = max(0.1, 2.5 - step * 0.05)
            logger.info(f"     Step {step}/{total_steps} | loss: {loss:.4f} | "
                  f"lr: {config.LEARNING_RATE:.2e}")
    logger.info(f"\n  ✅ 模拟训练完成！共 {config.NUM_EPOCHS} 个epoch")
    return {
        "success": True,
        "mock_mode": True,
        "output_dir": str(Path(config.OUTPUT_DIR) / "checkpoints"),
        "final_loss": 0.15,
    }
