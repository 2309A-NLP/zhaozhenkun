"""
run_all.py - RAG工单6 统一全流程入口（全部模块 + 小米API + 评估测试）
需求: 向量检索/全文检索/混合检索 + 多轮对话 + 准确率≥90%评估
功能: PDF解析→分块→向量化→Milvus→全文索引→混合检索→小米API→评估测试
"""
import logging, time, json, argparse, os

from config import OUTPUT_DIR, WO_ID, LOG_FMT, LOG_DATEFMT

logging.basicConfig(format=LOG_FMT, datefmt=LOG_DATEFMT, level=logging.INFO)
logger = logging.getLogger("run_all")
logger.info(f"{'='*50}\nRAG工单6 全流程 | 工单: {WO_ID}\n{'='*50}")


def banner(t):
    logger.info(f"\n{'='*30}\n{t}\n{'='*30}")


def step_pdf_parse():
    """模块1: pdf_parser — PDF解析"""
    banner("📄 [模块1] PDF解析")
    from pdf_parser import parse_all_pdfs, print_parse_summary
    r = parse_all_pdfs()
    print_parse_summary(r)
    all_p, txt = [], ""
    for n, pr in r.items():
        if hasattr(pr, 'pages'):
            for p in pr.pages:
                all_p.append({"page_num": p.page_num, "text": p.text, "source_pdf": n})
            txt += pr.total_text
    logger.info(f"✅ PDF完成: {len(all_p)}页\n")
    return {"pages": all_p, "total_text": txt}


def step_chunk(pdf_result):
    """模块2: text_chunker — 分块+倒排"""
    banner("🔪 [模块2] 文本分块+倒排")
    from text_chunker import build_chunks, build_inverted_index, save_chunks, save_inverted_index
    chunks = build_chunks(pdf_result)
    save_chunks(chunks)
    json.dump(chunks, open(os.path.join(OUTPUT_DIR, "chunks_full.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    inv = build_inverted_index(chunks)
    save_inverted_index(inv)
    logger.info(f"✅ 分块: {len(chunks)}块, 倒排: {len(inv)}词\n")
    return chunks


def step_embed(chunks):
    """模块3: embedder — BGE-M3向量化"""
    banner("🧠 [模块3] BGE-M3向量化")
    emb = __import__("embedder", fromlist=["create_embeddings"]).create_embeddings(chunks)
    logger.info(f"✅ 向量化: {len(emb['dense_vectors'])}个\n")
    return emb


def step_milvus(embeddings):
    """模块4: milvus_handler — Milvus入库"""
    banner("🗄️  [模块4] Milvus入库")
    from milvus_handler import MilvusHandler
    h = MilvusHandler()
    h.connect()
    h.create_collection(drop=True)
    ids = h.insert(embeddings["dense_vectors"], embeddings["chunk_texts"], embeddings["chunk_metas"])
    logger.info(f"✅ Milvus: {len(ids)}条\n")
    return h


def step_fulltext(chunks):
    """模块5: fulltext_engine — BM25全文索引"""
    banner("📑 [模块5] BM25全文索引")
    from fulltext_engine import FullTextEngine
    ft = FullTextEngine()
    ft.build(chunks)
    ft.save_index()
    logger.info(f"✅ BM25: {len(ft.inverted_index)}词\n")
    return ft


def step_mimo_qa(searcher):
    """模块6-8: 混合检索+重排+小米API问答"""
    banner("🤖 [模块6-8] 混合检索+重排+小米API问答")
    from qa_generator import generate_answer
    qs = ["武汉兴图新科电子股份有限公司注册资本是多少？",
          "武汉力源信息技术股份有限公司本次发行股数是多少？",
          "公司本次发行前每股净资产是多少？"]
    for q in qs:
        print(f"\n{'─'*40}\n❓ {q}")
        for m in ["vector", "fulltext", "hybrid"]:
            r = searcher.search(q, mode=m)
            print(f"  [{m}] {r['total']}条", end="")
            if r["results"]:
                print(f" | top: {r['results'][0]['content'][:50]}...")
        hybrid = searcher.search(q, mode="hybrid")
        if hybrid["results"]:
            ans = generate_answer(q, hybrid["results"][:3], use_mimo=True)
            print(f"  💡 MiMo: {ans['answer'][:120]}\n  📊 置信:{ans['confidence']} | ⏱{ans['response_time']:.1f}s")
    logger.info("✅ 小米API问答完成\n")


def step_evaluation(searcher):
    """模块9: evaluator — LLM评估测试（10题）"""
    banner("📊 [模块9] 评估测试（10题 × LLM 4维评分）")
    from evaluator import run_evaluation
    report = run_evaluation(searcher)
    return report


def full_pipeline():
    """完整9步流水线"""
    t0 = time.time()
    pdf = step_pdf_parse()
    chunks = step_chunk(pdf)
    emb = step_embed(chunks)
    milvus = step_milvus(emb)
    ft = step_fulltext(chunks)
    from embedder import BgeM3Embedder
    from reranker import Reranker
    from hybrid_search import HybridSearch
    e, r = BgeM3Embedder(), Reranker()
    e.load()
    del emb
    searcher = HybridSearch(e, milvus, ft, r)
    step_mimo_qa(searcher)
    report = step_evaluation(searcher)
    logger.info(f"\n{'='*50}\n🏁 全流程完成! 总耗时: {time.time()-t0:.1f}秒")
    if report:
        logger.info(f"📊 评估: {report['passed']}/{report['total_questions']}通过, "
                     f"准确率{report['accuracy_pct']}%, 均分{report['average_score']}")
    logger.info(f"{'='*50}")


def quick_test():
    """快速测试（缓存数据+小米API+评估）"""
    t0, p = time.time(), os.path.join(OUTPUT_DIR, "chunks_full.json")
    if not os.path.exists(p):
        logger.error(f"缓存不存在: {p}")
        return
    chunks = json.load(open(p, encoding="utf-8"))
    logger.info(f"📦 缓存: {len(chunks)}块")
    from embedder import BgeM3Embedder
    from milvus_handler import MilvusHandler
    from fulltext_engine import FullTextEngine
    from reranker import Reranker
    from hybrid_search import HybridSearch
    e, m, ft, r = BgeM3Embedder(), MilvusHandler(), FullTextEngine(), Reranker()
    e.load(); m.connect(); m.create_collection(); ft.build(chunks)
    searcher = HybridSearch(e, m, ft, r)
    step_mimo_qa(searcher)
    step_evaluation(searcher)
    logger.info(f"快速测试完成! {time.time()-t0:.1f}秒")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG工单6 混合检索+评估 (MiMo API)")
    parser.add_argument("--quick", action="store_true", help="快速测试")
    parser.add_argument("--eval-only", action="store_true", help="只做评估（需已有Milvus数据）")
    args = parser.parse_args()
    if args.eval_only:
        t0 = time.time()
        chunks = json.load(open(os.path.join(OUTPUT_DIR, "chunks_full.json"), encoding="utf-8"))
        from embedder import BgeM3Embedder
        from milvus_handler import MilvusHandler
        from fulltext_engine import FullTextEngine
        from reranker import Reranker
        from hybrid_search import HybridSearch
        e, m, ft, r = BgeM3Embedder(), MilvusHandler(), FullTextEngine(), Reranker()
        e.load(); m.connect(); m.create_collection(); ft.build(chunks)
        step_evaluation(HybridSearch(e, m, ft, r))
        logger.info(f"评估完成! {time.time()-t0:.1f}秒")
    elif args.quick:
        quick_test()
    else:
        full_pipeline()
