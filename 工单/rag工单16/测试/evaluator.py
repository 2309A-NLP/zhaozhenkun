# -*- coding: utf-8 -*-
"""
评估模块 — 实施专业评估（BLEU/ROUGE + 术语准确率 + 图纸推理准确率）。

功能说明：
- 使用Qwen2.5-VL:3b (Ollama)作为VLM评估，看图回答问题
- 使用MiMo API作为文本基线模型进行对比
- 支持双模型对比评估（基线模型 vs 微调后模型）
- 计算BLEU-4和ROUGE-L分数
- 计算工业专业术语准确率
- 计算图纸推理准确率（Group 2/3问题）
- 按问题类型分层统计
- 生成含失败案例分析的评估报告
"""
import logging  # 导入logging模块，用于结构化日志输出

logger = logging.getLogger(__name__)  # 获取当前模块的logger
import json  # 导入json模块
import re  # 导入re模块，用于正则匹配
import time  # 导入time模块
from pathlib import Path  # 导入Path类
from collections import Counter  # 导入Counter，用于ngram计数


def load_eval_set(eval_path):
    """加载评估集数据。"""
    with open(eval_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info(f"  📚 加载评估集: {len(data)} 条")
    return data


def compute_bleu(ref, hyp):
    """
    计算BLEU-4分数（简化版）。
    基于n-gram精确率，n=1到4。
    """
    if not hyp or not ref:
        return 0.0
    max_n, matches, total = 4, 0, 0
    for n in range(1, max_n + 1):
        r_ng = Counter(zip(*[list(ref)[i:] for i in range(n)]))
        h_ng = Counter(zip(*[list(hyp)[i:] for i in range(n)]))
        for ng, c in h_ng.items():
            matches += min(c, r_ng.get(ng, 0))
        total += sum(h_ng.values())
    if total == 0:
        return 0.0
    p = matches / total
    # 简短惩罚（brevity penalty）
    if len(hyp) < len(ref):
        p *= 1 - len(ref) / max(len(hyp), 1)
    return min(p, 1.0)


def compute_rouge_l(ref, hyp):
    """
    计算ROUGE-L分数（基于最长公共子序列LCS）。
    动态规划求最长公共子序列。
    """
    if not hyp or not ref:
        return 0.0
    m, n = len(str(ref)), len(str(hyp))
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if str(ref)[i - 1] == str(hyp)[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    lcs = dp[m][n]
    if lcs == 0:
        return 0.0
    p, r = lcs / n, lcs / m
    return 2 * p * r / (p + r) if p + r > 0 else 0.0


def check_terms(answer, terms):
    """
    检查答案中专业术语的使用情况。

    参数:
        answer: 模型回答文本
        terms: 专业术语列表

    返回:
        (正确使用数, 术语总数)
    """
    correct = sum(1 for t in terms if t in str(answer))
    return correct, len(terms)


def judge_correct(pred, exp, q_type):
    """
    判断预测答案是否正确（宽松语义匹配）。

    参数:
        pred: 模型预测答案
        exp: 标准答案
        q_type: 问题类型（text/image_text/reasoning）

    返回:
        True=正确, False=错误
    """
    if not pred or pred in ("【API失败】", "【无回答】", "【Ollama未运行】"):
        return False
    # 去除空格后比较包含关系
    pc = "".join(str(pred).strip().split())
    ec = "".join(str(exp).strip().split())
    if ec in pc or pc in ec:
        return True
    # 图文/推理问题：关键数字匹配
    if q_type in ("image_text", "reasoning"):
        pn = set(re.findall(r'\d+', pc))
        en = set(re.findall(r'\d+', ec))
        if pn and en and pn == en:
            return True
    return False


def call_mimo_api(question, config):
    """
    调用MiMo API生成答案（文本基线模型）。

    参数:
        question: 问题文本
        config: 配置模块引用

    返回:
        答案文本
    """
    from openai import OpenAI
    try:
        client = OpenAI(api_key=config.MIMO_API_KEY, base_url=config.MIMO_BASE_URL)
        resp = client.chat.completions.create(
            model=config.MIMO_MODEL,
            messages=[
                {"role": "system", "content": "你是一个工业专利分析助手。"},
                {"role": "user", "content": f"请回答：{question}"}
            ],
            timeout=config.MIMO_TIMEOUT)
        msg = resp.choices[0].message
        return (msg.content or msg.reasoning_content or "无响应").strip()
    except Exception as e:
        logger.warning(f"  ⚠️ MiMo API失败: {e}")
        return None


def call_ollama_vlm(question, image_path, vlm_client):
    """
    调用Ollama Qwen2.5-VL:3b进行图文问答。

    参数:
        question: 问题文本
        image_path: 图片路径（可为空）
        vlm_client: OllamaVLM实例

    返回:
        答案文本
    """
    try:
        return vlm_client.ask(question, image_path=image_path)
    except Exception as e:
        logger.warning(f"  ⚠️ Ollama VLM调用失败: {e}")
        return "【API失败】"


def run_evaluation(config, eval_data, vlm_client=None, mock_api=False,
                   compare_mode=False):
    """
    执行完整评估流程。按问题类型分层统计并生成报告。

    参数:
        config: 配置模块引用
        eval_data: 评估数据集
        vlm_client: OllamaVLM实例（用于VLM评估）
        mock_api: 是否模拟API调用
        compare_mode: 是否执行双模型对比评估

    返回:
        评估报告字典
    """
    logger.info("\n📊 开始专业评估...")
    max_eval = min(100, len(eval_data))  # 最多评估100条
    terms = config.INDUSTRY_TERMS  # 工业术语词典
    type_map = {1: "text", 2: "image_text", 3: "reasoning"}  # 类型映射

    # ===== 评估MiMo基线（纯文本模型） =====
    logger.info("\n📌 [评估模型1] MiMo API (基线文本模型)")
    baseline_results = _evaluate_model(
        eval_data[:max_eval], config, terms, type_map,
        mock_api=mock_api, model_name="MiMo API"
    )

    # ===== 评估Qwen2.5-VL:3b（视觉语言模型） =====
    ollama_results = None
    if vlm_client:
        logger.info("\n📌 [评估模型2] Qwen2.5-VL:3b (Ollama 视觉模型)")
        ollama_results = _evaluate_model(
            eval_data[:max_eval], config, terms, type_map,
            vlm_client=vlm_client, model_name="Qwen2.5-VL:3b"
        )
    else:
        logger.warning("\n  ⚠️ Ollama VLM客户端未提供，跳过VLM评估")
        logger.info("  💡 确保Ollama已运行: ollama serve")
        logger.info("  并在调用前创建: from vlm_client import OllamaVLM")

    # ===== 生成评估报告 =====
    report = _generate_report(config, baseline_results, ollama_results,
                              max_eval, compare_mode)

    # ===== 保存报告 =====
    report_path = Path(config.OUTPUT_DIR) / "eval_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logger.info(f"\n  ✅ 评估报告已保存: {report_path}")

    # ===== 打印摘要 =====
    _print_summary(report)

    return report


def _evaluate_model(eval_data, config, terms, type_map,
                    mock_api=False, vlm_client=None, model_name="模型"):
    """
    评估单个模型在评估集上的表现。

    参数:
        eval_data: 评估数据列表
        config: 配置模块引用
        terms: 工业术语列表
        type_map: 类型映射字典
        mock_api: 是否模拟
        vlm_client: Ollama VLM客户端
        model_name: 模型名称（用于报告）

    返回:
        评估结果字典
    """
    results = []  # 每条结果的详细信息
    # 分组统计：正确数/总数
    group_stats = {
        "text": {"correct": 0, "total": 0},
        "image_text": {"correct": 0, "total": 0},
        "reasoning": {"correct": 0, "total": 0},
    }

    for idx, item in enumerate(eval_data):
        # 提取评估信息
        question = item["question"]  # 问题文本
        expected = item["answer"]  # 标准答案
        group = item.get("group", 1)  # 问题组别
        q_type = type_map.get(group, "text")  # 问题类型
        image_path = item.get("image", "")  # 图片路径
        has_image = item.get("has_image", False)  # 是否有图片

        # 更新分组统计
        group_stats[q_type]["total"] += 1

        # 进展提示
        if (idx + 1) % 20 == 0:
            logger.info(f"    进度: {idx + 1}/{len(eval_data)}")

        # ===== 生成预测答案 =====
        if mock_api:
            # 模拟模式：直接用标准答案作为预测
            prediction = f"模拟答案: {expected}"
        elif vlm_client and model_name == "Qwen2.5-VL:3b":
            # VLM模式：传入图片+问题
            img_for_vlm = image_path if (has_image and image_path) else None
            prediction = call_ollama_vlm(question, img_for_vlm, vlm_client)
        else:
            # MiMo API模式：纯文本问答
            prediction = call_mimo_api(question, config)

        # 如果API失败，标记
        if prediction is None:
            prediction = "【API失败】"

        # ===== 计算各项指标 =====
        bleu = compute_bleu(expected, prediction)
        rouge = compute_rouge_l(expected, prediction)
        term_correct, term_total = check_terms(prediction, terms)
        term_acc = term_correct / max(term_total, 1)

        # 判断答案是否正确
        correct = judge_correct(prediction, expected, q_type)
        if correct:
            group_stats[q_type]["correct"] += 1

        # 保存结果
        results.append({
            "idx": idx,
            "group": group,
            "type": q_type,
            "question": question[:80],  # 截断显示
            "expected": expected[:80],
            "prediction": str(prediction)[:80],
            "bleu": round(bleu, 4),
            "rouge_l": round(rouge, 4),
            "term_acc": round(term_acc, 4),
            "correct": correct,
            "has_image": has_image,
        })

    # ===== 计算汇总统计 =====
    total_correct = sum(v["correct"] for v in group_stats.values())
    total_count = sum(v["total"] for v in group_stats.values())
    accuracy = total_correct / max(total_count, 1) * 100

    avg_bleu = sum(r["bleu"] for r in results) / max(len(results), 1)
    avg_rouge = sum(r["rouge_l"] for r in results) / max(len(results), 1)
    avg_term = sum(r["term_acc"] for r in results) / max(len(results), 1)

    composite = (config.BLEU_WEIGHT * avg_bleu +
                 config.ROUGE_WEIGHT * avg_rouge +
                 config.TERM_ACC_WEIGHT * avg_term +
                 config.DRAWING_ACC_WEIGHT * (accuracy / 100))

    return {
        "model_name": model_name,
        "eval_count": len(results),
        "accuracy": round(accuracy, 1),
        "bleu_avg": round(avg_bleu, 4),
        "rouge_l_avg": round(avg_rouge, 4),
        "term_acc_avg": round(avg_term, 4),
        "composite": round(composite, 4),
        "group_stats": {k: {"correct": v["correct"], "total": v["total"],
                            "accuracy": round(v["correct"] / max(v["total"], 1) * 100, 1)}
                        for k, v in group_stats.items()},
        "results": results,
    }


def _generate_report(config, baseline, ollama, max_eval, compare_mode):
    """
    生成最终的评估报告，含双模型对比。

    参数:
        config: 配置模块引用
        baseline: MiMo基线评估结果
        ollama: Qwen2.5-VL评估结果（可为None）
        max_eval: 评估条数
        compare_mode: 是否对比模式

    返回:
        完整报告字典
    """
    report = {
        "eval_config": {
            "total_eval": max_eval,
            "mode": "对比模式" if compare_mode else "单模型模式",
            "bleu_weight": config.BLEU_WEIGHT,
            "rouge_weight": config.ROUGE_WEIGHT,
            "term_weight": config.TERM_ACC_WEIGHT,
            "drawing_weight": config.DRAWING_ACC_WEIGHT,
        },
        "models": {},
        "comparison": None,
    }

    # 添加基线模型结果
    if baseline:
        report["models"]["MiMo_API"] = {
            "name": baseline["model_name"],
            "accuracy": baseline["accuracy"],
            "bleu_avg": baseline["bleu_avg"],
            "rouge_l_avg": baseline["rouge_l_avg"],
            "term_acc_avg": baseline["term_acc_avg"],
            "composite": baseline["composite"],
            "group_stats": baseline["group_stats"],
        }

    # 添加VLM模型结果
    if ollama:
        report["models"]["Qwen2.5_VL"] = {
            "name": ollama["model_name"],
            "accuracy": ollama["accuracy"],
            "bleu_avg": ollama["bleu_avg"],
            "rouge_l_avg": ollama["rouge_l_avg"],
            "term_acc_avg": ollama["term_acc_avg"],
            "composite": ollama["composite"],
            "group_stats": ollama["group_stats"],
        }

    # 双模型对比
    if compare_mode and baseline and ollama:
        report["comparison"] = {
            "accuracy_diff": round(ollama["accuracy"] - baseline["accuracy"], 1),
            "composite_diff": round(ollama["composite"] - baseline["composite"], 4),
            "winner": "Qwen2.5-VL" if ollama["accuracy"] > baseline["accuracy"]
                      else "MiMo" if baseline["accuracy"] > ollama["accuracy"]
                      else "平局",
        }

    return report


def _print_summary(report):
    """打印评估报告摘要到终端。"""
    logger.info("\n" + "=" * 55)
    logger.info("评估摘要")
    logger.info(f"   模式: {report['eval_config']['mode']}")
    logger.info(f"   评估条数: {report['eval_config']['total_eval']}")
    logger.info("=" * 55)

    for model_key, model_data in report["models"].items():
        logger.info(f"\n  🤖 {model_data['name']}")
        logger.info(f"   ┌──────────────┬──────────┐")
        logger.info(f"   │ 准确率       │ {model_data['accuracy']:>6.1f}%    │")
        logger.info(f"   │ BLEU-4       │ {model_data['bleu_avg']:.4f}   │")
        logger.info(f"   │ ROUGE-L      │ {model_data['rouge_l_avg']:.4f}   │")
        logger.info(f"   │ 术语准确率   │ {model_data['term_acc_avg']:.2%}   │")
        logger.info(f"   │ 综合评分     │ {model_data['composite']:.4f}   │")
        logger.info(f"   └──────────────┴──────────┘")

        # 按类型显示
        logger.info(f"   📂 分类型准确率:")
        for q_type, stats in model_data["group_stats"].items():
            if stats["total"] > 0:
                bar = "█" * int(stats["accuracy"] / 5) + "░" * (20 - int(stats["accuracy"] / 5))
                logger.info(f"     {q_type:<12s} {stats['accuracy']:>5.1f}% {bar} ({stats['correct']}/{stats['total']})")

        # 达标判断
        if model_data["accuracy"] >= 80:
            logger.info(f"     ✅ 达标 (≥80%)")
        else:
            logger.warning(f"     ⚠️ 未达标 ({model_data['accuracy']:.1f}% < 80%)")

    # 对比结果
    if report["comparison"]:
        logger.info("\n" + "=" * 55)
        logger.info("双模型对比")
        diff = report["comparison"]["accuracy_diff"]
        symbol = "📈" if diff > 0 else "📉" if diff < 0 else "➡️"
        logger.info(f"   {symbol} 准确率差异: {diff:+.1f}%")
        logger.info(f"   🏆 胜者: {report['comparison']['winner']}")
        logger.info("=" * 55)
