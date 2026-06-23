"""
run.py - RAG工单7 主入口（调用所有子模块）
工单编号: 人工智能NLP-RAG-功能测试及评估
功能: 协调全流程：①解析CCF_PDF→②分块→③BGE-M3向量化
      →④Milvus入库→⑤提取问题→⑥检索→⑦生成→⑧评估→⑨Web
      当sample_questions不足10题时自动补充CCF相关测试问题
"""

import logging, sys, time, argparse
from config import LOG_FMT, LOG_DATEFMT, WO_ID, OUTPUT_DIR

logging.basicConfig(format=LOG_FMT, datefmt=LOG_DATEFMT, level=logging.INFO)
logger = logging.getLogger("run")

# 补充问题（sample_questions不足10题时使用）
DEFAULT_QUESTIONS = [
    {"id": 5, "question": "招商银行2019年的营业收入和净利润增长情况如何？",
     "reference_answer": "招商银行2019年营业收入2697亿元增长8.5%,净利润928亿元增长15.3%"},
    {"id": 6, "question": "平安银行2019年的不良贷款率是多少？相比上年有何变化？",
     "reference_answer": "平安银行2019年末不良贷款率1.65%,较上年末下降0.10个百分点"},
    {"id": 7, "question": "中信证券2020年的主营业务收入构成如何？各业务板块收入占比？",
     "reference_answer": "中信证券2020年营业收入543亿元,证券投资业务收入占比最高"},
    {"id": 8, "question": "招商证券2021年的风险管理体系有什么特点？",
     "reference_answer": "招商证券2021年持续优化风险管理系统,完善信用风险管理机制"},
    {"id": 9, "question": "邮储银行2019年的资产总额和存款总额分别是多少？",
     "reference_answer": "邮储银行2019年末资产总额10.22万亿元,存款余额9.34万亿元"},
    {"id": 10, "question": "中国平安2019年的科技业务收入增长情况如何？",
     "reference_answer": "中国平安2019年科技业务总收入同比增长,通过陆金所金融壹账通布局"},
]


def step(msg, fn, *args, **kw):
    """通用步骤执行器，带日志和计时"""
    logger.info(f"步: {msg}")
    t0 = time.time()
    r = fn(*args, **kw)
    logger.info(f"  ✓ {time.time()-t0:.1f}s")
    return r


def print_summary(eval_data):
    """打印评估摘要到控制台"""
    s = eval_data["summary"]
    print(f"\n{'='*55}\n  {WO_ID}\n{'='*55}")
    print(f"  测试: {s.get('total_questions', 0)}题")
    print(f"  LLM综合: {s.get('avg_llm_overall',0)}/10 | 相关: {s.get('avg_llm_relevance',0)}/10 | 完整: {s.get('avg_llm_completeness',0)}/10")
    print(f"  F1(参考): {s.get('avg_keyword_f1',0):.4f} | 响应: {s.get('avg_response_time',0)}s | 高质量: {s.get('high_quality_ratio',0)*100:.0f}%")
    print(f"  问题分析:")
    for tp in s.get("typical_problems", []):
        print(f"    {tp['issue']}: {tp['count']}次 → {tp['suggestion']}")
    print(f"\n  报告: {OUTPUT_DIR / 'evaluation_report.html'}")
    print(f"  Web:  http://127.0.0.1:5007\n")


def pipeline_step_1_2():
    """步骤①~②: 解析PDF并分块"""
    from pdf_parser import parse_ccf_pdfs
    from text_chunker import build_chunks, save_chunks
    pdf = parse_ccf_pdfs()
    if not pdf["pages"]: raise RuntimeError("PDF解析失败")
    chunks = build_chunks(pdf)
    save_chunks(chunks)
    return chunks


def pipeline_step_3_4(chunks):
    """步骤③~④: 向量化并入库"""
    from embedder import create_embeddings
    from milvus_handler import create_index_and_insert
    data = create_embeddings(chunks)
    create_index_and_insert(data["dense_vectors"], data["chunk_texts"], data["chunk_metas"])
    return data


def pipeline_step_5_6_7(questions):
    """步骤⑤~⑦: 提取问题→检索→问答生成"""
    from embedder import BgeM3Embedder
    from retriever import Retriever
    from qa_generator import QAGenerator

    embedder = BgeM3Embedder()
    retriever = Retriever()
    qa = QAGenerator()
    results = []
    for q in questions:
        qvec = embedder.encode_query(q["question"])["dense_vecs"][0].tolist()
        hits = retriever.retrieve(qvec, q["question"])
        r = qa.generate(q["question"], hits)
        results.append(r)
        logger.info(f"  Q{q['id']} ✓")
    retriever.close()
    return results


def pipeline_step_8(questions, qa_results):
    """步骤⑧: 评估分析"""
    from evaluator import Evaluator
    ev = Evaluator()
    data = ev.evaluate_all(questions, qa_results)
    ev.save_results()
    return data


def _check_milvus():
    """检查Milvus是否有数据"""
    from milvus_handler import MilvusManager
    mgr = MilvusManager()
    mgr.connect()
    try:
        from pymilvus import utility, Collection
        if not utility.has_collection("rag_work_order_7"):
            mgr.close(); return False
        coll = Collection("rag_work_order_7")
        ok = coll.num_entities > 0
        coll.release()
        mgr.close()
        return ok
    except:
        mgr.close(); return False


def main():
    """主流程"""
    parser = argparse.ArgumentParser(description="RAG工单7 功能测试及评估")
    parser.add_argument("--web-only", action="store_true", help="仅启动Web")
    parser.add_argument("--test", action="store_true", help="测试模式(仅2题)")
    parser.add_argument("--rebuild", action="store_true", help="强制重建向量库")
    args = parser.parse_args()

    if args.web_only:
        from app import get_app
        return get_app().run(host="127.0.0.1", port=5007, debug=False)

    t0 = time.time()
    from pdf_parser import parse_sample_questions
    questions = step("⑤提取测试问题", parse_sample_questions)
    if args.test:
        questions = questions[:2]
    # 补充到10个问题
    if len(questions) < 10:
        existing_ids = {q["id"] for q in questions}
        for dq in DEFAULT_QUESTIONS:
            if dq["id"] not in existing_ids:
                questions.append(dq); existing_ids.add(dq["id"])
            if len(questions) >= 10: break
        logger.info(f"补充后共 {len(questions)} 个测试问题")

    if args.rebuild:
        logger.info("--rebuild模式: 强制重建向量库")
        chunks = step("①解析PDF+②分块", pipeline_step_1_2)
        step("③向量化+④入库", pipeline_step_3_4, chunks)
    elif not _check_milvus():
        chunks = step("①解析PDF+②分块", pipeline_step_1_2)
        step("③向量化+④入库", pipeline_step_3_4, chunks)
    else:
        logger.info("Milvus已有数据, 跳过①~④")

    qa_results = step("⑥检索+⑦问答", pipeline_step_5_6_7, questions)
    eval_data = step("⑧评估分析", pipeline_step_8, questions, qa_results)
    print_summary(eval_data)
    logger.info(f"总耗时: {time.time()-t0:.1f}s")

    # 步骤⑨: Web展示
    from app import get_app
    get_app().run(host="127.0.0.1", port=5007, debug=False)


if __name__ == "__main__":
    main()
