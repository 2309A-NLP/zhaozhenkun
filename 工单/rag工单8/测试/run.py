"""
run.py - RAG工单8 主入口（调用所有子模块）
工单编号: 人工智能NLP-RAG-基于Graph RAG 实现金融问答
|功能: 协调全流程：解析CCF年报PDF→文本分块→BGE-M3向量化
|      →Milvus入库→MiMo实体提取→NetworkX知识图谱构建
      →纯向量检索(无图)→GraphRAG混合检索(有图)→评估对比
      →结果保存→Web展示
"""

import logging, sys, time, json, argparse
from config import LOG_FMT, LOG_DATEFMT, WO_ID, OUTPUT_DIR

logging.basicConfig(format=LOG_FMT, datefmt=LOG_DATEFMT, level=logging.INFO)
logger = logging.getLogger("run")

_counter = [1]
def step(msg, fn, *args, **kw):
    """通用步骤执行器，带日志和计时"""
    logger.info(f"📌 步{_counter[0]}: {msg}")
    _counter[0] += 1
    t0 = time.time()
    r = fn(*args, **kw)
    logger.info(f"  ✅ {time.time()-t0:.1f}s")
    return r

def _milvus_ok():
    try:
        from pymilvus import utility, Collection
        from milvus_handler import MilvusManager
        mgr = MilvusManager(); mgr.connect()
        ok = utility.has_collection("rag_work_order_8") and Collection("rag_work_order_8").num_entities > 0
        Collection("rag_work_order_8").release(); mgr.close()
        return ok
    except: return False

def pipeline_pcv():
    from pdf_parser import parse_ccf_pdfs
    from text_chunker import build_chunks, save_chunks
    from embedder import create_embeddings
    from milvus_handler import create_index_and_insert
    pdf = parse_ccf_pdfs()
    chunks = build_chunks(pdf); save_chunks(chunks)
    emb = create_embeddings(chunks)
    cnt = create_index_and_insert(emb["dense_vectors"], emb["chunk_texts"], emb["chunk_metas"])
    return chunks, emb

def pipeline_graph(chunks):
    from entity_graph_builder import GraphBuilder
    b = GraphBuilder(); b.build_from_chunks(chunks, max_chunks=30); b.save()
    return b

def run_questions(questions, graph_builder, use_graph, chunks=None):
    from embedder import BgeM3Embedder
    from graph_retriever import GraphRetriever
    from qa_generator import QAGenerator
    embedder = BgeM3Embedder(); retriever = GraphRetriever(graph_builder)
    if chunks: retriever.set_chunks(chunks)
    qa = QAGenerator()
    mode = "GraphRAG" if use_graph else "Vector"
    logger.info(f"🔍 {mode}模式({len(questions)}题)...")
    results = []
    for i, q in enumerate(questions):
        t0 = time.time()
        qv = embedder.encode_query(q["question"])["dense_vecs"][0]
        cr = retriever.retrieve(qv.tolist(), q["question"], use_graph=use_graph) if use_graph else retriever.retrieve_vector_only(qv)
        qar = qa.generate(q["question"], cr, use_graph=use_graph)
        results.append({"question":q["question"],"reference_answer":q.get("reference_answer",""),
                        "retrieved_chunks":cr[:3],"response_time":round(time.time()-t0+qar.get("response_time",0),2),
                        "qa_result":qar})
        logger.info(f"  [{i+1}/{len(questions)}] ✅ {q['question'][:30]}...")
    retriever.close(); return results

def print_summary(s):
    if not s: return
    b, a, imp = s["before"], s["after"], s["improvement"]
    print(f"\n{'='*55}\n  {WO_ID}\n  {s['total_questions']}题评估\n{'='*55}")
    print(f"  指标         | Vector      | GraphRAG    | 变化")
    print(f"  {'-'*52}")
    for k, col in [("相关性","相关性"),("完整性","完整性"),("准确性","准确性"),("流畅性","流畅性")]:
        print(f"  {col:12s} | {b.get(k,0):.2f}          | {a.get(k,0):.2f}          | {imp.get(k+'_delta',0):+.2f}")
    print(f"  响应时间     | {b.get('avg_response_time',0):.2f}s       | {a.get('avg_response_time',0):.2f}s       | {imp.get('time_delta',0):+.2f}s")
    print(f"{'='*55}")
    print(f"  标准: 相关性≥7 完整性≥7 | Vector:{'✅' if s.get('before_meets_threshold') else '❌'} GraphRAG:{'✅' if s.get('after_meets_threshold') else '❌'}")
    print(f"  📄 {OUTPUT_DIR/'evaluation_report.html'}\n  🌐 http://0.0.0.0:5008\n")

def main():
    parser = argparse.ArgumentParser(description="RAG工单8 GraphRAG金融问答")
    parser.add_argument("--web-only", action="store_true", help="仅启动Web")
    parser.add_argument("--test", action="store_true", help="测试模式(2题)")
    parser.add_argument("--rebuild", action="store_true", help="强制重建")
    args = parser.parse_args()
    if args.web_only:
        from app import get_app
        print("🌐 http://0.0.0.0:5008")
        return get_app().run(host="0.0.0.0", port=5008, debug=False)
    t0 = time.time()
    from pdf_parser import parse_sample_questions
    questions = step("提取测试问题", parse_sample_questions)
    if not questions: logger.error("❌ 无测试问题"); return
    if args.test: questions = questions[:2]
    # 检查/重建数据
    if args.rebuild or not _milvus_ok():
        if args.rebuild: logger.info("🔄 强制重建")
        chunks, _ = step("①~④ 解析→分块→向量化→入库", pipeline_pcv)
        gb = step("⑤ 构建知识图谱", pipeline_graph, chunks)
        with open(str(OUTPUT_DIR/"chunks_data.json"),"w",encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)
    else:
        logger.info("✅ Milvus已有数据, 从文件加载...")
        import networkx as nx; from collections import defaultdict
        from entity_graph_builder import GraphBuilder
        chunks = []; gb = None
        cp = OUTPUT_DIR/"chunks_data.json"
        if cp.exists():
            with open(cp,"r",encoding="utf-8") as f: chunks = json.load(f)
        gp = OUTPUT_DIR/"knowledge_graph.json"
        if gp.exists():
            gb = GraphBuilder(); gb.graph = nx.Graph()
            with open(gp,"r",encoding="utf-8") as f:
                gd = json.load(f)
            for n in gd.get("nodes",[]): gb.graph.add_node(n["name"],type=n.get("type",""))
            for e in gd.get("edges",[]): gb.graph.add_edge(e["source"],e["target"],relation=e.get("relation","相关"))
            gb.entity_to_chunks = defaultdict(set,{k:set(v) for k,v in gd.get("entity_to_chunks",{}).items()})
            gb._built = True
    # 纯向量
    logger.info(f"\n{'='*40}\n🔵 纯向量检索\n{'='*40}")
    before = step("⑥ 纯向量检索+问答", run_questions, questions, gb, False, chunks)
    # GraphRAG
    logger.info(f"\n{'='*40}\n🟢 GraphRAG混合检索\n{'='*40}")
    after = step("⑦ GraphRAG检索+问答", run_questions, questions, gb, True, chunks)
    # 保存结果
    with open(OUTPUT_DIR/"qa_results.json","w",encoding="utf-8") as f:
        json.dump({"vector": before, "graphrag": after}, f, ensure_ascii=False, indent=2)
    # 评估
    from evaluator import RagasEvaluator
    ev = RagasEvaluator()
    step("⑧ 评估Vector", ev.evaluate_batch, before, "before")
    step("⑨ 评估GraphRAG", ev.evaluate_batch, after, "after")
    summary = step("⑩ 对比报告", ev.compare_and_save)
    print_summary(summary)
    logger.info(f"⏱ 总耗时: {time.time()-t0:.1f}s")
    from app import get_app
    print(f"🌐 http://0.0.0.0:5008\n📄 {OUTPUT_DIR/'evaluation_report.html'}")
    get_app().run(host="0.0.0.0", port=5008, debug=False)

if __name__ == "__main__":
    main()
