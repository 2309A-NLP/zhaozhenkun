"""
run.py - RAG工单6 主运行入口（流水线模式）
需求: 向量检索/全文检索/混合检索 — 完整流水线编排
功能: 1.解析双PDF → 2.文本分块+倒排 → 3.BGE-M3向量化 → 4.存入Milvus → 5.BM25全文索引 → 6.Web服务
"""
import logging, time, json, argparse, os

from config import PDF_NAMES, OUTPUT_DIR, PROJECT_DIR, WO_ID, LOG_FMT, LOG_DATEFMT

logging.basicConfig(format=LOG_FMT, datefmt=LOG_DATEFMT, level=logging.INFO)
logger = logging.getLogger("run")
logger.info("=" * 50)
logger.info(f"RAG工单6 启动 | 工单: {WO_ID} | PDF: {PDF_NAMES}")
logger.info("=" * 50)


def step1_parse():
    """步骤1: 解析双PDF"""
    logger.info("[1/6] 解析双PDF...")
    from pdf_parser import parse_all_pdfs
    result = parse_all_pdfs()
    all_pages, total_start = [], time.time()
    for pdf_name, pdf_result in result.items():
        if hasattr(pdf_result, 'pages'):
            for page in pdf_result.pages:
                all_pages.append({"page_num": page.page_num, "text": page.text, "source_pdf": pdf_name})
    total_text = "\n".join(p.text for r in result.values() if hasattr(r, 'pages') for p in r.pages)
    logger.info(f"[1/6] 完成! {len(all_pages)}页, {time.time()-total_start:.1f}秒")
    return {"pages": all_pages, "total_text": total_text}


def step2_chunk(pdf_result):
    """步骤2: 文本分块 + 倒排索引"""
    logger.info("[2/6] 文本分块+倒排索引...")
    from text_chunker import build_chunks, build_inverted_index, save_chunks
    chunks = build_chunks(pdf_result)
    save_chunks(chunks)
    json.dump(chunks, open(os.path.join(OUTPUT_DIR, "chunks_full.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    from text_chunker import save_inverted_index
    save_inverted_index(build_inverted_index(chunks))
    logger.info(f"[2/6] 完成! {len(chunks)}块")
    return chunks


def step3_embed(chunks):
    """步骤3: BGE-M3向量化"""
    logger.info("[3/6] BGE-M3向量化...")
    from embedder import create_embeddings
    emb = create_embeddings(chunks)
    logger.info(f"[3/6] 完成! {len(emb['dense_vectors'])}向量")
    return emb


def step4_milvus(embeddings):
    """步骤4: 存入Milvus"""
    logger.info("[4/6] 存入Milvus...")
    from milvus_handler import MilvusHandler
    h = MilvusHandler()
    h.connect()
    h.create_collection(drop=True)
    ids = h.insert(embeddings["dense_vectors"], embeddings["chunk_texts"], embeddings["chunk_metas"])
    logger.info(f"[4/6] 完成! {len(ids)}条")
    return h


def step5_fulltext(chunks):
    """步骤5: 构建BM25全文索引"""
    logger.info("[5/6] 构建BM25全文索引...")
    from fulltext_engine import FullTextEngine
    ft = FullTextEngine()
    ft.build(chunks)
    ft.save_index()
    logger.info(f"[5/6] 完成!")
    return ft


def step6_web():
    """步骤6: 启动Web服务"""
    logger.info("[6/6] 启动Web服务...")
    from app import get_app
    app = get_app()
    print(f"\n{'='*50}")
    print(f"  🌐 混合检索服务: http://0.0.0.0:5000")
    print(f"  🆔 {WO_ID}")
    print(f"  🔄 三种模式: 向量检索 / 全文检索 / 混合检索")
    print(f"{'='*50}\n")
    app.run(host="0.0.0.0", port=5000, debug=False)


def run_pipeline():
    """完整流水线"""
    total_start = time.time()
    pdf_result = step1_parse()
    chunks = step2_chunk(pdf_result)
    embeddings = step3_embed(chunks)
    step4_milvus(embeddings)
    step5_fulltext(chunks)
    logger.info(f"流水线完成! 总耗时: {time.time()-total_start:.1f}秒")
    step6_web()


def quick_start():
    """快速启动Web（数据已入库）"""
    step6_web()


def test_modes():
    """测试三种检索模式 + 小米MiMo问答"""
    from embedder import BgeM3Embedder
    from milvus_handler import MilvusHandler
    from fulltext_engine import FullTextEngine
    from reranker import Reranker
    from hybrid_search import HybridSearch
    e, m = BgeM3Embedder(), MilvusHandler()
    e.load()
    m.connect()
    m.create_collection()
    chunks = json.load(open(os.path.join(OUTPUT_DIR, "chunks_full.json"), encoding="utf-8")) if os.path.exists(os.path.join(OUTPUT_DIR, "chunks_full.json")) else []
    ft, r = FullTextEngine(), Reranker()
    if chunks:
        ft.build(chunks)
    hs = HybridSearch(e, m, ft, r)
    questions = [
        "武汉兴图新科注册资本是多少？",
        "武汉力源信息技术股份有限公司本次发行股数是多少？",
    ]
    from qa_generator import generate_answer
    for q in questions:
        print(f"\n{'='*50}\n问题: {q}")
        for mode in ["vector", "fulltext", "hybrid"]:
            result = hs.search(q, mode=mode)
            print(f"\n  [{mode}] 结果数: {result['total']}")
            if result["results"]:
                print(f"  最佳结果: {result['results'][0]['content'][:80]}...")
                best = result["results"][:3]
                ans = generate_answer(q, best)
                print(f"  MiMo答案: {ans['answer'][:60]}... (置信度:{ans['confidence']}, {ans['response_time']}秒)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG工单6 - 混合检索")
    parser.add_argument("--web-only", action="store_true", help="仅启动Web")
    parser.add_argument("--test", action="store_true", help="测试检索模式")
    args = parser.parse_args()
    if args.web_only:
        quick_start()
    elif args.test:
        test_modes()
    else:
        run_pipeline()
