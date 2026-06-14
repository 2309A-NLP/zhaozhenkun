# -*- coding: utf-8 -*-
"""
微调配置模块 — 生成LLaMA-Factory兼容的LoRA微调YAML配置文件。

功能说明：
- 生成标准的LLaMA-Factory YAML配置文件
- 配置LoRA参数（rank、alpha、target_modules等）
- 配置训练参数（batch_size、learning_rate、epoch等）
- 配置数据集路径和预处理参数
- 配置日志和模型保存策略
- 支持Qwen2.5-VL系列VLM微调
"""
import logging  # 导入logging模块，用于结构化日志输出

logger = logging.getLogger(__name__)  # 获取当前模块的logger
import os  # 导入os模块
import json  # 导入json模块
from pathlib import Path  # 导入Path类


def generate_lora_config(config, output_dir):
    """
    生成LLaMA-Factory LoRA微调YAML配置文件。

    参数:
        config: 配置模块引用
        output_dir: 输出目录路径

    返回:
        yaml文件路径
    """
    output_path = Path(output_dir)  # 输出目录的Path对象
    output_path.mkdir(parents=True, exist_ok=True)  # 确保目录存在

    # ===== 构建YAML配置内容 =====
    # 参考LLaMA-Factory官方示例格式
    # 适配Qwen2.5-VL系列VLM
    yaml_content = f"""### model
model_name_or_path: {config.BASE_MODEL}
trust_remote_code: true

### method
stage: sft
do_train: true
finetuning_type: lora
lora_rank: {config.LORA_RANK}
lora_alpha: {config.LORA_ALPHA}
lora_dropout: {config.LORA_DROPOUT}
lora_target: all
# LoRA目标模块（all=全部线性层，对VLM同时微调视觉和语言部分）

### dataset
dataset: vlm_finetune_data
dataset_dir: {output_path}
template: qwen2_vl
cutoff_len: {config.MAX_SEQ_LEN}
preprocessing_num_workers: 4
dataloader_num_workers: 2
val_size: 0.1

### output
output_dir: {output_path / 'checkpoints'}
logging_steps: {config.LOGGING_STEPS}
save_steps: {config.SAVE_STEPS}
plot_loss: true
overwrite_output_dir: true
save_only_model: false
report_to: none

### train
per_device_train_batch_size: {config.BATCH_SIZE}
gradient_accumulation_steps: {config.GRADIENT_ACCUMULATION}
learning_rate: {config.LEARNING_RATE}
num_train_epochs: {config.NUM_EPOCHS}
lr_scheduler_type: {config.LR_SCHEDULER}
warmup_ratio: {config.WARMUP_RATIO}
fp16: true
ddp_timeout: 180000000

### eval
per_device_eval_batch_size: 1
eval_strategy: steps
eval_steps: {config.EVAL_STEPS}
"""
    # 保存YAML文件
    yaml_path = output_path / "lora_finetune.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(yaml_content)

    logger.info(f"  ✅ LoRA配置已生成: {yaml_path}")  # 打印保存信息

    # ===== 同时生成dataset_info.json =====
    # LLaMA-Factory需要dataset_info.json来识别数据集
    dataset_info = {
        "vlm_finetune_data": {  # 数据集键名
            "file_name": "vlm_finetune_data.jsonl",  # 数据文件名
            "format": "image_question_answer",  # 数据格式（VLM标准格式）
            "columns": {  # 字段映射
                "images": "image",  # 图像路径字段（Qwen2.5-VL使用images复数）
                "query": "question",  # 问题字段
                "response": "answer",  # 答案字段
            },
        }
    }

    info_path = output_path / "dataset_info.json"
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(dataset_info, f, ensure_ascii=False, indent=2)

    logger.info(f"  ✅ dataset_info.json已生成: {info_path}")  # 打印保存信息

    return str(yaml_path)  # 返回YAML路径


def print_training_command(yaml_path, model_path="Qwen/Qwen2.5-VL-3B-Instruct"):
    """
    打印LLaMA-Factory训练启动命令。

    参数:
        yaml_path: 配置文件路径
        model_path: 模型路径（本地或HuggingFace名称）
    """
    # 构建LLaMA-Factory训练命令
    cmd = (
        f"# ===== 启动LoRA微调（Qwen2.5-VL-3B）=====\n"
        f"# 方式一：使用LLaMA-Factory命令行\n"
        f"llamafactory-cli train {yaml_path}\n\n"
        f"# 方式二：使用Python脚本\n"
        f"python -m llamafactory.cli.train {yaml_path}\n\n"
        f"# ===== 模型合并 =====\n"
        f"# 微调完成后，将LoRA权重合并到基础模型\n"
        f"llamafactory-cli export --model_name_or_path {model_path} "
        f"--adapter_name_or_path ./output/checkpoints "
        f"--export_dir ./output/vlm_finetuned\n\n"
        f"# ===== 使用Ollama部署微调模型（可选）=====\n"
        f"# 1. 将合并后的模型转为GGUF格式\n"
        f"# 2. 创建Ollama Modelfile指向GGUF文件\n"
        f"# 3. ollama create my-finetuned-vlm -f Modelfile\n"
    )
    logger.info(f"\n🚀 训练启动命令:")
    logger.info(cmd)  # 打印命令
