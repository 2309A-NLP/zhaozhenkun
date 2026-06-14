"""
主入口模块 - 一站式完成 Embedding 模型微调全流程
调度数据准备 → 基线评估 → LoRA 微调 → 微调后评估 → 对比报告生成
逐步执行，每个步骤可独立查看结果。
工单编号：人工智能NLP-RAG项目-11-Embeddings模型微调任务V1.0
"""

import logging
import sys  # 系统模块
import time  # 时间模块
import json  # JSON 读写
import torch  # PyTorch（用于 step4 加载模型时指定 dtype）
from pathlib import Path  # 路径模块

from config import setup_logging, ensure_dirs, OUTPUT_DIR, MODEL_DIR, DATA_DIR, EVAL_DIR
from config import setup_logging, PDF_PATHS, LORA_CONFIG, TRAIN_CONFIG

setup_logging()
logger = logging.getLogger(__name__)


def step_data_preparation():
    """
    Step 1: 数据准备 - PDF 解析 → 文本切分 → 三元组构造 → 训练/评估集划分
    """
    print("\n" + "=" * 60)
    print("Step 1/4: 数据准备")
    print("=" * 60)
    print(f"  PDF 数据: {PDF_PATHS}")

    from data_prep import prepare_training_data
    train_data, eval_data = prepare_training_data()

    print(f"  结果: 训练集 {len(train_data)} 条, 评估集 {len(eval_data)} 条")
    return train_data, eval_data


def step_baseline_evaluation(eval_data):
    """
    Step 2: 加载原始模型，评估微调前的检索效果（Baseline）
    """
    print("\n" + "=" * 60)
    print("Step 2/4: 微调前基线评估")
    print("=" * 60)

    from evaluator import EmbeddingEvaluator
    from trainer import EmbeddingFineTuner

    print("[加载原始模型]")
    tuner = EmbeddingFineTuner()
    tuner.load_model()

    print("\n[基线评估]")
    evaluator = EmbeddingEvaluator()
    metrics = evaluator.evaluate(tuner, "微调前(Baseline)", eval_data)
    return tuner, evaluator, metrics


def step_fine_tune(tuner, train_data, eval_data):
    """
    Step 3: LoRA 微调训练
    """
    print("\n" + "=" * 60)
    print("Step 3/4: LoRA 微调训练")
    print("=" * 60)
    print(f"  训练轮数: {TRAIN_CONFIG['epochs']}")
    print(f"  批次大小: {TRAIN_CONFIG['batch_size']}")
    print(f"  学习速率: {TRAIN_CONFIG['learning_rate']}")
    print(f"  LoRA rank: {LORA_CONFIG['r']}")

    tuner.train(train_data, eval_data)
    model_path = tuner.save_final_model()
    return model_path


def step_finetuned_evaluation(evaluator, eval_data):
    """
    Step 4: 重新加载微调后的模型，评估检索效果
    """
    print("\n" + "=" * 60)
    print("Step 4/4: 微调后评估与对比")
    print("=" * 60)

    from trainer import EmbeddingFineTuner

    print("[加载微调后的模型]")
    # 直接用 HuggingFace 加载基础模型 + LoRA adapter（避免嵌套 LoRA）
    final_model_dir = MODEL_DIR / "final"
    if not final_model_dir.exists():
        print(f"[错误] 微调模型不存在: {final_model_dir}")
        print("请先运行训练步骤")
        return None

    from transformers import AutoModel, AutoTokenizer
    from peft import PeftModel
    from config import setup_logging, get_model_path

    base_path = get_model_path()
    print(f"  [基础模型] {base_path}")
    base_model = AutoModel.from_pretrained(
        base_path, trust_remote_code=True, torch_dtype=torch.float16
    )
    # 加载 LoRA adapter（直接包装基础模型，单层 LoRA）
    tuned_tuner = EmbeddingFineTuner()
    tuned_tuner.model = PeftModel.from_pretrained(base_model, final_model_dir)
    tuned_tuner.tokenizer = AutoTokenizer.from_pretrained(base_path)
    tuned_tuner.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    tuned_tuner.model.to(tuned_tuner.device)
    print(f"  [加载] LoRA 权重已加载: {final_model_dir}")

    print("\n[微调后评估]")
    tuned_metrics = evaluator.evaluate(tuned_tuner, "微调后(Fine-tuned)", eval_data)

    print("\n[生成对比报告]")
    comparison = evaluator.compare()
    report_path = evaluator.save_report(comparison)

    # 打印最终结论
    print("\n" + "=" * 60)
    print("微调完成！请查看评估报告")
    print("=" * 60)
    print(f"  评估报告: {report_path}")

    return tuned_metrics


def run_full_pipeline():
    """
    一站式完整流水线：数据准备 → 基线评估 → 微调训练 → 微调后评估
    """
    print("\n" + "★" * 60)
    print("Embedding 模型微调流水线 - 完整流程")
    print("★" * 60 + "\n")
    print(f"  输出目录: {OUTPUT_DIR}")
    print(f"  LoRA rank: {LORA_CONFIG['r']}")
    print(f"  训练参数: epochs={TRAIN_CONFIG['epochs']}, "
          f"batch={TRAIN_CONFIG['batch_size']}, "
          f"lr={TRAIN_CONFIG['learning_rate']}")

    total_start = time.time()

    # Step 1: 数据准备
    train_data, eval_data = step_data_preparation()

    if not train_data or not eval_data:
        print("[错误] 数据准备失败，无法继续")
        return

    # Step 2: 基线评估
    tuner, evaluator, _ = step_baseline_evaluation(eval_data)

    # Step 3: 微调
    step_fine_tune(tuner, train_data, eval_data)

    # Step 4: 微调后评估
    # 注意：这里需要重新创建 tuner 来加载微调后的模型
    step_finetuned_evaluation(evaluator, eval_data)

    total_elapsed = time.time() - total_start
    print(f"\n[总计] 全流程耗时: {total_elapsed:.0f}秒 ({total_elapsed/60:.1f}分钟)")


def run_step_by_step():
    """
    分步执行模式：用户可选择单独运行某个步骤。
    各步骤之间通过文件传递数据，可独立执行。
    """
    print("\n" + "★" * 60)
    print("Embedding 模型微调 - 分步执行")
    print("★" * 60)
    print("  可用步骤:")
    print("    1) 数据准备")
    print("    2) 基线评估")
    print("    3) 微调训练")
    print("    4) 微调后评估")
    print("    5) 生成最终报告")
    print("")

    # 由于是 CLI 环境，采用函数调用的方式而非交互式
    # 用户可在 main.py 中取消注释指定步骤
    pass


if __name__ == "__main__":
    """
    主入口：默认执行完整流水线。
    可通过命令行参数选择模式：
      python main.py          → 完整流水线
      python main.py --step 1 → 只运行数据准备
      python main.py --step 2 → 只运行基线评估（需要已准备好数据）
      python main.py --step 3 → 只运行微调训练（需要已准备好数据）
      python main.py --step 4 → 只运行微调后评估（需要已训练好模型）
    """
    if len(sys.argv) == 1:
        # 无参数：执行完整流水线
        run_full_pipeline()
    elif len(sys.argv) == 3 and sys.argv[1] == "--step":
        step = sys.argv[2]
        ensure_dirs()

        # 加载已有的评估数据
        eval_path = DATA_DIR / "eval_triplets.json"
        train_path = DATA_DIR / "train_triplets.json"

        train_data = None
        eval_data = None

        if train_path.exists():
            import json
            with open(train_path, "r", encoding="utf-8") as f:
                train_data = json.load(f)
        if eval_path.exists():
            import json
            with open(eval_path, "r", encoding="utf-8") as f:
                eval_data = json.load(f)

        if step == "1":
            step_data_preparation()
        elif step == "2":
            if eval_data:
                step_baseline_evaluation(eval_data)
            else:
                print("[错误] 缺少评估数据，请先运行步骤 1")
        elif step == "3":
            if train_data and eval_data:
                tuner, _, _ = step_baseline_evaluation(eval_data)
                step_fine_tune(tuner, train_data, eval_data)
            else:
                print("[错误] 缺少训练或评估数据，请先运行步骤 1")
        elif step == "4":
            if eval_data:
                from evaluator import EmbeddingEvaluator
                evaluator = EmbeddingEvaluator()
                step_finetuned_evaluation(evaluator, eval_data)
            else:
                print("[错误] 缺少评估数据，请先运行步骤 1")
        else:
            print(f"[错误] 未知步骤: {step}")
    else:
        print("用法: python main.py [--step <1|2|3|4>]")
        print("  不带参数: 执行完整流水线")
        print("  --step 1: 仅数据准备")
        print("  --step 2: 仅基线评估")
        print("  --step 3: 仅微调训练")
        print("  --step 4: 仅微调后评估")
