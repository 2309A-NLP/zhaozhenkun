"""
评估对比模块
功能：整合 RAGAS 标准指标 + LLM 自定义4维评分，输出 RAG vs LightRAG 全面对比报告
完成：双评估体系（RAGAS + 4维）、RAG/LightRAG 对比、JSON 报告输出、控制台摘要打印
"""
import logging
import sys, os
# 将项目根目录加入路径，支持从任意子目录导入其他模块
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _sub in ["设计", "研发", "测试", "部署"]:
    _p = os.path.join(_root, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import json                        # 解析 LLM 返回的 JSON 评分结果
from datetime import datetime      # 生成评估报告时间戳

from llm_client import call_llm    # 调用小米 MiMo API（LLM 4维评分用）
from ragas_eval import evaluate_with_ragas  # RAGAS 标准指标评估
import config                      # 全局配置（评估输出路径等）

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

# ======================== 自定义 4 维度 LLM 评估 ========================

# LLM 4维度评估的系统提示词
EVAL_PROMPT = (
    "你是一个 RAG 评估专家。对回答从以下 4 维度评分（1~5分）：\n"
    "1. 相关性（relevance）：是否紧扣问题\n"
    "2. 完整性（completeness）：是否覆盖问题所有方面\n"
    "3. 准确性（accuracy）：信息是否准确，有无虚构\n"
    "4. 流畅性（fluency）：语言是否通顺、逻辑清晰\n\n"
    "返回 JSON：{\"relevance\":{\"score\":N,\"reason\":\"...\"},"
    "\"completeness\":{...},\"accuracy\":{...},\"fluency\":{...},"
    "\"overall\":平均分}"
)


def evaluate_answer(question: str, context: str, answer: str) -> dict:
    """
    用 LLM 对单个问答对进行 4 维度评分
    参数：
        question: 用户原始问题
        context:  检索到的上下文文本（截取前1500字符）
        answer:   系统生成的回答
    返回：
        {"relevance": {"score": int, "reason": str}, ...}
        每个维度含分数(1-5)和评分理由；失败时返回 score=0
    """
    # 构造评估 prompt：包含问题、上下文、回答
    prompt = f"问题：{question}\n\n检索上下文：\n{context[:1500]}\n\n系统回答：\n{answer}"
    try:
        # 调用 LLM 进行评分（低温度保证评分一致性）
        text = call_llm(prompt, EVAL_PROMPT, temperature=0.1)
        # 从返回文本中提取 JSON 对象
        start = text.find("{")      # JSON 起始位置
        end = text.rfind("}") + 1   # JSON 结束位置
        if start >= 0 and end > start:
            return json.loads(text[start:end])  # 解析并返回评分 dict
    except Exception as e:
        print(f"  ⚠️ 评估出错: {e}")
    # LLM 调用失败时的默认返回值
    return {d: {"score": 0, "reason": "评估失败"} for d in
            ["relevance", "completeness", "accuracy", "fluency"]}


def evaluate_batch(questions, rag_answers, lightrag_answers,
                   rag_contexts, lightrag_contexts,
                   enable_ragas=True) -> dict:
    """
    批量评估：对全部问题逐一评分，汇总生成对比报告
    参数：
        questions:         [{"id": int, "question": str}, ...] 问题列表
        rag_answers:       [{"question", "answer", "mode"}, ...] RAG 回答
        lightrag_answers:  [{"question", "answer", "mode"}, ...] LightRAG 回答
        rag_contexts:      [str, ...] RAG 检索的上下文字符串
        lightrag_contexts: [str, ...] LightRAG 检索的上下文字符串
        enable_ragas:      是否同时启用 RAGAS 标准指标评估
    返回：
        完整评估报告 dict，包含 llm_4dim / ragas / details / meta / comparison
    """
    rag_scores = []    # RAG 模式每题 4 维评分
    lr_scores = []     # LightRAG 模式每题 4 维评分
    details = []       # 每题详细评分（两个模式）
    print("📊 LLM 自定义 4 维度评估...")

    for i in range(len(questions)):
        q = questions[i]  # 当前问题
        print(f"  问题 {q['id']} ({i+1}/{len(questions)})...")
        # 对 RAG 回答评分
        re = evaluate_answer(q["question"], rag_contexts[i], rag_answers[i]["answer"])
        # 对 LightRAG 回答评分
        le = evaluate_answer(q["question"], lightrag_contexts[i], lightrag_answers[i]["answer"])
        rag_scores.append(re)   # 记录 RAG 评分
        lr_scores.append(le)    # 记录 LightRAG 评分
        # 记录详情（answer 截取前300字符，节省空间）
        details.append({
            "question_id": q["id"],
            "question": q["question"],
            "rag": {"answer": rag_answers[i]["answer"][:300], "eval": re},
            "lightrag": {"answer": lightrag_answers[i]["answer"][:300], "eval": le}
        })

    # 内部辅助：计算所有问题在各维度的平均分
    def avg_scores(score_list):
        """对评分列表按维度求平均"""
        dims = ["relevance", "completeness", "accuracy", "fluency"]
        avg_d = {}  # 各维度平均分
        for d in dims:
            # 过滤掉评分为0的值（评估失败的题）
            vals = [s[d]["score"] for s in score_list
                    if s.get(d, {}).get("score", 0) > 0]
            avg_d[d] = round(sum(vals) / len(vals), 2) if vals else 0
        avg_d["overall"] = round(sum(avg_d[d] for d in dims) / len(dims), 2)
        return avg_d

    # ======== 构建 LLM 4 维评估报告 ========
    llm_report = {
        "rag": {
            "avg": avg_scores(rag_scores),
            "per_question": [{"id": questions[i]["id"], "scores": rag_scores[i]}
                             for i in range(len(questions))]
        },
        "lightrag": {
            "avg": avg_scores(lr_scores),
            "per_question": [{"id": questions[i]["id"], "scores": lr_scores[i]}
                             for i in range(len(questions))]
        },
        "comparison": {
            "rag_overall": avg_scores(rag_scores)["overall"],
            "lightrag_overall": avg_scores(lr_scores)["overall"],
            "improvement": round(avg_scores(lr_scores)["overall"] -
                                 avg_scores(rag_scores)["overall"], 2)
        }
    }

    # ======== RAGAS 标准指标评估 ========
    ragas_result = None
    if enable_ragas:
        ragas_result = evaluate_with_ragas(
            questions, rag_answers, lightrag_answers,
            rag_contexts, lightrag_contexts
        )

    # ======== 组装完整报告 ========
    report = {
        "meta": {  # 报告元信息
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total": len(questions),
            "methods": ["LLM_4dimension"]  # 使用的评估方法列表
        },
        "llm_4dim": llm_report,  # LLM 4 维评分结果
        "details": details       # 每题详细评分
    }

    # 如果 RAGAS 可用，纳入报告
    if ragas_result and "error" not in ragas_result:
        report["meta"]["methods"].append("RAGAS")
        report["ragas"] = ragas_result

    # ======== 打印评估摘要 ========
    c4 = llm_report["comparison"]
    print(f"\n📊 LLM 4维: RAG={c4['rag_overall']}/5 | "
          f"LightRAG={c4['lightrag_overall']}/5 | "
          f"{'↑' if c4['improvement']>0 else '↓'}{abs(c4['improvement'])}")

    if ragas_result and "comparison" in ragas_result:
        rc = ragas_result["comparison"]
        print(f"📊 RAGAS:  RAG={rc['rag_overall']:.3f} | "
              f"LightRAG={rc['lightrag_overall']:.3f} | "
              f"{'↑' if rc['improvement']>0 else '↓'}{abs(rc['improvement']):.3f}")

    return report


def save_report(report: dict, path: str) -> None:
    """
    将评估报告保存为 JSON 文件
    参数：
        report: evaluate_batch 返回的完整评估报告
        path:   输出文件路径
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"💾 评估报告: {path}")


def print_comparison(report: dict) -> None:
    """
    打印 RAG vs LightRAG 的评估对比摘要到控制台
    含 RAGAS 标准指标 + LLM 4 维评分双体系
    参数：
        report: evaluate_batch 返回的完整评估报告
    """
    print("\n" + "=" * 60)
    print("📊 RAG vs LightRAG 完整评估对比")
    print("=" * 60)

    # ── 第一部分：RAGAS 标准指标 ──
    if "ragas" in report:
        ragas = report["ragas"]          # RAGAS 结果
        rc = ragas.get("comparison", {})  # 对比数据
        print("\n── RAGAS 标准指标 ──")
        print(f"  RAG 综合:      {rc.get('rag_overall', 0):.3f}")
        print(f"  LightRAG 综合: {rc.get('lightrag_overall', 0):.3f}")
        arrow = "↑" if rc.get("improvement", 0) > 0 else "↓"
        print(f"  差异:          {arrow} {abs(rc.get('improvement', 0)):.3f}")

        # 逐指标对比
        ragas_dims = {
            "faithfulness": "忠实度", "answer_relevancy": "回答相关性",
            "context_precision": "上下文精准度", "context_recall": "上下文召回率"
        }
        print("\n  RAGAS 各维度详析:")
        for d, cn in ragas_dims.items():
            r = ragas.get("rag", {}).get(d, 0)
            l = ragas.get("lightrag", {}).get(d, 0)
            arrow = "↑" if l > r else "↓" if l < r else "="
            print(f"    {cn}: RAG={r:.3f} → LightRAG={l:.3f} {arrow}")

    # ── 第二部分：LLM 4 维度评分 ──
    c4 = report["llm_4dim"]["comparison"]
    print("\n── LLM 4 维度评估 ──")
    print(f"  RAG 综合:      {c4['rag_overall']:.2f}/5")
    print(f"  LightRAG 综合: {c4['lightrag_overall']:.2f}/5")
    arrow = "↑" if c4["improvement"] > 0 else "↓"
    print(f"  差异:          {arrow} {abs(c4['improvement']):.2f} 分")

    # 逐维度对比
    dims_cn = {"relevance": "相关性", "completeness": "完整性",
               "accuracy": "准确性", "fluency": "流畅性"}
    print("\n  LLM 4维各维度详析:")
    for d, cn in dims_cn.items():
        r = report["llm_4dim"]["rag"]["avg"].get(d, 0)
        l = report["llm_4dim"]["lightrag"]["avg"].get(d, 0)
        arrow = "↑" if l > r else "↓" if l < r else "="
        print(f"    {cn}: RAG={r:.2f} → LightRAG={l:.2f} {arrow}")
    print("=" * 60)
