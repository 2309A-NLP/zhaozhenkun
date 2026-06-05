"""
rerun_eval.py - 重新跑LLM评估（跳过PDF解析和QA生成）
工单编号: 人工智能NLP-RAG-功能测试及评估
功能: 加载已有的评估结果JSON，重新用LLM评分，
      保存更新后的评估报告
"""
import logging, json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from config import OUTPUT_DIR, LOG_FMT, LOG_DATEFMT
logging.basicConfig(format=LOG_FMT, datefmt=LOG_DATEFMT, level=logging.INFO)
logger = logging.getLogger("rerun_eval")

# 加载已有评估结果
json_path = OUTPUT_DIR / "evaluation_results.json"
with open(json_path, "r", encoding="utf-8") as f:
    old_data = json.load(f)

# 提取问答数据
questions = [{
    "id": r["question_id"],
    "question": r["question"],
    "reference_answer": r["reference_answer"],
} for r in old_data["item_results"]]

# 重建qa_results格式（从已有JSON中提取）
qa_results = []
for r in old_data["item_results"]:
    # 重建source_chunks（已有top_score但没有原始chunk数据，用score代替）
    top_score = r.get("top_score", 0)
    qa_results.append({
        "answer": r["generated_answer"],
        "source_chunks": [{"score": top_score, "source_pdf": "", "page_num": 0}],
        "response_time": r.get("response_time", 0),
    })

# 重新评估
from evaluator import Evaluator
ev = Evaluator()
data = ev.evaluate_all(questions, qa_results)
ev.save_results()

# 打印摘要
s = data["summary"]
print(f"\n{'='*55}")
print(f"  RAG工单7 评估报告（重新评分）")
print(f"{'='*55}")
print(f"  测试: {s.get('total_questions', 0)}题")
print(f"  LLM综合: {s.get('avg_llm_overall',0)}/10 | 相关: {s.get('avg_llm_relevance',0)}/10 | 完整: {s.get('avg_llm_completeness',0)}/10")
print(f"  F1(参考): {s.get('avg_keyword_f1',0):.4f} | 响应: {s.get('avg_response_time',0)}s | 高质量: {s.get('high_quality_ratio',0)*100:.0f}%")
print(f"  问题分析:")
for tp in s.get("typical_problems", []):
    print(f"    {tp['issue']}: {tp['count']}次 → {tp['suggestion']}")
print(f"\n  报告: {OUTPUT_DIR / 'evaluation_report.html'}")
print()
