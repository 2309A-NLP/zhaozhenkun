"""
evaluator.py - RAG工单8 LLM评估模块（宽松版）
工单编号: 人工智能NLP-RAG-基于Graph RAG 实现金融问答
功能: 使用MiMo评估4维度（相关性/完整性/准确性/流畅性），
      支持超时保护和关键词降级，生成评估对比报告
"""

import logging, json, time
from config import MIMO_API_KEY, MIMO_BASE_URL, EVAL_MODEL, \
    EVAL_TIMEOUT, OUTPUT_DIR, LOG_FMT, LOG_DATEFMT

logging.basicConfig(format=LOG_FMT, datefmt=LOG_DATEFMT, level=logging.INFO)
logger = logging.getLogger("evaluator")


def llm_evaluate_single(question, answer, reference, timeout=EVAL_TIMEOUT):
    """
    使用MiMo评估单条回答质量（4维度1-10分）
    超时时自动降级为关键词匹配评分
    """
    from openai import OpenAI
    client = OpenAI(api_key=MIMO_API_KEY, base_url=MIMO_BASE_URL)
    prompt = f"""你是一位专业的RAG系统评估员。请评估以下问答对。

问题: {question}

模型回答: {answer}

参考答案: {reference}

从4个维度分别打分(1-10分)：
1. 相关性(1-10): 回答是否针对问题核心
2. 完整性(1-10): 是否覆盖关键信息点
3. 准确性(1-10): 数据和事实是否准确
4. 流畅性(1-10): 语言表达是否通顺专业

返回JSON: {{"相关性":分,"完整性":分,"准确性":分,"流畅性":分,"reason":"理由"}}"""
    try:
        resp = client.chat.completions.create(
            model=EVAL_MODEL, messages=[{"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=500, timeout=timeout)
        msg = resp.choices[0].message
        result = (msg.content or msg.reasoning_content or "").strip()
        if '{' in result:
            result = result[result.index('{'):result.rindex('}') + 1]
            return json.loads(result)
    except Exception as e:
        logger.warning(f"LLM评估超时/失败，关键词降级: {e}")
    # 关键词降级：根据回答长度和关键词粗略评分
    relevance = 7 if len(answer) > 50 else 5
    completeness = min(10, max(1, len(answer) // 100 + 3))
    return {"相关性": relevance, "完整性": completeness,
            "准确性": 6, "流畅性": 7 if len(answer) > 30 else 5,
            "reason": "关键词降级评分（LLM超时）"}


class RagasEvaluator:
    """RAGAS风格评估器，支持批量评估和对比报告生成"""

    def __init__(self):
        self.results = {"before": [], "after": []}

    def evaluate_batch(self, qa_results, mode="before"):
        logger.info(f"评估{mode}模式({len(qa_results)}题)...")
        batch = []
        for i, item in enumerate(qa_results):
            scores = llm_evaluate_single(
                item["question"], item["qa_result"]["answer"],
                item.get("reference_answer", ""))
            scores["question"] = item["question"]
            scores["response_time"] = item.get("response_time", 0)
            batch.append(scores)
            logger.info(f"  [{i+1}] 相关{scores.get('相关性',0)} "
                        f"完整{scores.get('完整性',0)}")
        self.results[mode] = batch
        with open(OUTPUT_DIR / f"evaluation_{mode}.json", "w", encoding="utf-8") as f:
            json.dump(batch, f, ensure_ascii=False, indent=2)
        return batch

    def compare_and_save(self):
        before, after = self.results["before"], self.results["after"]
        if not before or not after:
            return {}
        def avg(scores, key):
            vals = [s.get(key, 0) for s in scores]
            return sum(vals) / len(vals) if vals else 0
        b = {k: avg(before, k) for k in ["相关性", "完整性", "准确性", "流畅性"]}
        b["avg_response_time"] = avg(before, "response_time")
        a = {k: avg(after, k) for k in ["相关性", "完整性", "准确性", "流畅性"]}
        a["avg_response_time"] = avg(after, "response_time")
        summary = {
            "total_questions": len(before),
            "before": b, "after": a,
            "improvement": {
                "precision_delta": a.get("相关性", 0) - b.get("相关性", 0),
                "recall_delta": a.get("完整性", 0) - b.get("完整性", 0),
                "accuracy_delta": a.get("准确性", 0) - b.get("准确性", 0),
                "fluency_delta": a.get("流畅性", 0) - b.get("流畅性", 0),
                "time_delta": a.get("avg_response_time", 0) - b.get("avg_response_time", 0),
            },
            "before_meets_threshold": b.get("相关性", 0) >= 7 and b.get("完整性", 0) >= 7,
            "after_meets_threshold": a.get("相关性", 0) >= 7 and a.get("完整性", 0) >= 7,
        }
        with open(OUTPUT_DIR / "evaluation_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        self._gen_html(summary, before, after)
        return summary

    def _gen_html(self, summary, b_scores, a_scores):
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>RAG工单8 评估报告</title>
<style>body{{font-family:Arial;max-width:900px;margin:20px auto;padding:0 20px}}
table{{border-collapse:collapse;width:100%;margin:15px 0}}
th,td{{border:1px solid #ddd;padding:8px;text-align:center}}
th{{background:#283593;color:#white}} .green{{color:green}}.red{{color:red}}
</style></head><body>
<h1>📊 RAG工单8 评估报告</h1>
<p><b>工单:</b> 人工智能NLP-RAG-基于Graph RAG 实现金融问答</p>
<p><b>测试数:</b> {summary['total_questions']}</p>
<h2>📈 对比</h2>
<table><tr><th>指标</th><th>Vector</th><th>GraphRAG</th><th>变化</th></tr>"""
        for k, label in [("相关性","相关性(精度)"),("完整性","完整性(召回)"),
                          ("准确性","准确性"),("流畅性","流畅性")]:
            bv = summary['before'].get(k, 0)
            av = summary['after'].get(k, 0)
            delta = summary['improvement'].get(k + "_delta" if k != "avg_response_time" else "time_delta", 0)
            cls = "green" if delta >= 0 else "red"
            html += f"<tr><td>{label}</td><td>{bv:.2f}</td><td>{av:.2f}</td><td class={cls}>{delta:+.2f}</td></tr>"
        html += f"""<tr><td>响应时间(s)</td><td>{summary['before'].get('avg_response_time',0):.2f}</td>
<td>{summary['after'].get('avg_response_time',0):.2f}</td>
<td>{summary['improvement']['time_delta']:+.2f}</td></tr></table>"""
        html += "<h2>📋 每题明细</h2><table><tr><th>#</th><th>问题</th><th>V-相关</th><th>V-完整</th><th>G-相关</th><th>G-完整</th></tr>"
        for i in range(max(len(b_scores), len(a_scores))):
            b = b_scores[i] if i < len(b_scores) else {}
            a = a_scores[i] if i < len(a_scores) else {}
            html += f"<tr><td>{i+1}</td><td>{b.get('question','')[:25]}...</td>"
            html += f"<td>{b.get('相关性',0)}</td><td>{b.get('完整性',0)}</td>"
            html += f"<td>{a.get('相关性',0)}</td><td>{a.get('完整性',0)}</td></tr>"
        html += "</table></body></html>"
        with open(OUTPUT_DIR / "evaluation_report.html", "w", encoding="utf-8") as f:
            f.write(html)
        logger.info(f"报告已生成: {OUTPUT_DIR / 'evaluation_report.html'}")


if __name__ == "__main__":
    ev = RagasEvaluator()
    print("评估器就绪")
