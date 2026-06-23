"""
evaluator.py - RAG工单6 评估测试模块
需求: 任务目标验证 — 准确率/召回率评估
功能: 关键词匹配评估（检出答案中是否包含参考答案的关键数字/名称），生成评估报告
"""
import logging, json, time, os, re
from config import OUTPUT_DIR, LOG_FMT, LOG_DATEFMT

logging.basicConfig(format=LOG_FMT, datefmt=LOG_DATEFMT, level=logging.INFO)
logger = logging.getLogger("evaluator")

TEST_QUESTIONS = [
    {"q": "武汉兴图新科电子股份有限公司注册资本是多少？", "ref": "5,520万元", "kw": ["5520", "5,520", "5520万元"]},
    {"q": "武汉力源信息技术股份有限公司本次发行股数是多少？", "ref": "1,670万股", "kw": ["1670", "1,670", "1670万股"]},
    {"q": "公司本次发行前每股净资产是多少？", "ref": "3.55元/股", "kw": ["3.55", "3.55元"]},
    {"q": "武汉力源信息发行后总股本是多少？", "ref": "6,670万股", "kw": ["6670", "6,670", "6670万股"]},
    {"q": "本次发行的主承销商是谁？", "ref": "国信证券", "kw": ["国信证券"]},
    {"q": "武汉兴图新科的上市地点是？", "ref": "上海证券交易所", "kw": ["上海证券交易所", "科创板"]},
    {"q": "本次发行前力源信息的净资产（截至2010年6月30日）是多少？", "ref": "2.18元/股", "kw": ["2.18"]},
    {"q": "武汉力源信息在报告期内的主要业务是什么？", "ref": "IC等电子元器件的代理销售", "kw": ["IC", "电子元器件", "代理销售"]},
    {"q": "本次发行的股票类型是什么？", "ref": "人民币普通股（A股）", "kw": ["人民币普通股", "A股"]},
    {"q": "武汉力源信息披露的财务报告审计截止日是什么时候？", "ref": "2010年6月30日", "kw": ["2010", "6月30日", "2010年6月30日"]},
]


def keyword_score(answer, keywords):
    """关键词匹配评估：检测答案中包含关键信息，任一关键词命中即满分"""
    if not answer:
        return False, 0
    answer_lower = answer.lower()
    for kw in keywords:
        if kw.lower() in answer_lower:
            return True, 10
    return False, 0


def run_evaluation(searcher):
    """执行评估测试：混合检索+MiMo问答+关键词评分"""
    logger.info("=" * 50)
    logger.info("📊 评估测试 (10题 × 混合检索 + MiMo + 关键词匹配)")
    logger.info("=" * 50)
    from qa_generator import generate_answer

    results, total_score, t_start = [], 0.0, time.time()

    for i, item in enumerate(TEST_QUESTIONS):
        q, ref, kw = item["q"], item["ref"], item["kw"]
        logger.info(f"[{i + 1}/10] {q[:40]}...")

        # 混合检索 + MiMo问答
        search_r = searcher.search(q, mode="hybrid")
        if not search_r["results"]:
            ans = {"answer": "未检索到相关内容", "confidence": "low", "sources": [], "response_time": 0}
        else:
            ans = generate_answer(q, search_r["results"][:3], use_mimo=True)

        answer_text = ans["answer"]
        passed, score = keyword_score(answer_text, kw)
        total_score += score

        results.append({
            "question": q, "reference": ref,
            "answer": answer_text[:200], "confidence": ans["confidence"],
            "response_time": ans["response_time"],
            "keywords": kw, "score": score, "passed": passed,
        })
        status = "✅" if passed else "⚠️"
        detail = answer_text[:60].replace('\n', ' ')
        print(f"  {status} {score}/10 | {detail}... | ⏱{ans['response_time']:.1f}s")

    elapsed = time.time() - t_start
    passed_count = sum(1 for r in results if r["passed"])
    accuracy = (passed_count / len(TEST_QUESTIONS)) * 100
    avg_score = total_score / len(TEST_QUESTIONS)

    report = {
        "total_questions": len(TEST_QUESTIONS),
        "passed": passed_count,
        "accuracy_pct": round(accuracy, 1),
        "average_score": round(avg_score, 2),
        "total_time_sec": round(elapsed, 1),
        "results": results,
    }
    rp = os.path.join(OUTPUT_DIR, "evaluation_report.json")
    json.dump(report, open(rp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    logger.info(f"评估报告已保存: {rp}")

    print(f"\n{'=' * 50}")
    print(f"📊 评估结果汇总")
    print(f"{'=' * 50}")
    print(f"  总题数: {len(TEST_QUESTIONS)}")
    print(f"  通过: {passed_count}/{len(TEST_QUESTIONS)} ({accuracy:.0f}%)")
    print(f"  目标准确率≥90%: {'✅ 达标!' if accuracy >= 90 else '❌ 未达标'}")
    print(f"  平均分: {avg_score:.1f}/10")
    print(f"  总耗时: {elapsed:.1f}秒")
    print(f"{'=' * 50}\n")
    return report


if __name__ == "__main__":
    print("此模块需通过run_all.py调用")
