"""
主入口模块（部署层 — 全流程总调度）
功能：整合全部 13 个子模块，一键完成解析→分块→编码→实体提取→构图→检索→问答→评估
完成：argparse 命令行（--test 快速验证 / --rebuild 重建缓存），8 步自动化流水线
"""
import logging

logger = logging.getLogger(__name__)
logger.info("RAG工单12 GraphRAG 启动")
import sys, os
# 将项目根目录加入路径，支持从任意子目录导入其他模块
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _sub in ["设计", "研发", "测试", "部署", "优化"]:
    _p = os.path.join(_root, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import os, sys, json, argparse           # 命令行解析 / JSON 读写
import numpy as np                       # 向量数值运算
from sentence_transformers import SentenceTransformer  # BGE-M3 模型
import torch                             # GPU 检测

# ── 按流水线顺序导入所有模块 ──
from pdf_parser import parse_all_pdfs             # Step 1: PDF 解析
from text_chunker import chunk_all_pages          # Step 2: 文本分块
from embedder import encode_chunks                # Step 3: BGE-M3 向量编码
from entity_extractor import extract_all_chunks, merge_extractions  # Step 4: 实体提取
from graph_builder import build_graph, save_graph, load_graph, graph_to_html  # Step 5: 图谱
from retriever import rag_retrieve, lightrag_retrieve  # Step 6: 双模式检索
from qa_generator import build_context, batch_generate   # Step 7: 问答生成
from evaluator import evaluate_batch, save_report        # Step 8: 评估
from optimizer import validate_cache, PipelineTimer      # 优化层：缓存验证 + 耗时统计
import config                                  # 全局配置


def main(test_mode=False, rebuild=False) -> dict:
    """
    LightRAG 全流程主函数（8 步自动化流水线）
    参数：
        test_mode: True=仅处理前2题快速验证
        rebuild:   True=强制重建所有缓存
    返回：
        完整结果汇总 dict（含评分、统计、输出路径）
    """
    timer = PipelineTimer()  # 全流程计时器
    print("=" * 60)
    print("🚀 LightRAG 优化系统 — 全流程启动")
    print("=" * 60)

    # ======== Step 1: PDF 解析 ========
    print("\n📄 Step 1/8: 解析 PDF...")
    timer.start("PDF解析")
    cache_file = os.path.join(config.CACHE_DIR, "parsed_pages.json")
    if rebuild or not os.path.exists(cache_file):
        pdf_data = parse_all_pdfs()  # 调用 PyMuPDF 解析
        # 序列化为 JSON 缓存（将 dict[filename] 转为标准格式）
        serializable = {
            fn: [{"source_pdf": fn, "page_num": p["page_num"], "text": p["text"]}
                 for p in pages]
            for fn, pages in pdf_data.items()
        }
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)
    else:
        with open(cache_file, "r", encoding="utf-8") as f:
            pdf_data = json.load(f)  # 从缓存加载
    total_pages = sum(len(p) for p in pdf_data.values())
    timer.stop()
    print(f"  ✅ {total_pages} 页")

    # ======== Step 2: 文本分块 ========
    print("\n🔪 Step 2/8: 文本分块...")
    timer.start("文本分块")
    if rebuild or not os.path.exists(config.CHUNKS_CACHE):
        chunks = chunk_all_pages(pdf_data)  # 重叠分块算法
        with open(config.CHUNKS_CACHE, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False, indent=2)
    else:
        with open(config.CHUNKS_CACHE, "r", encoding="utf-8") as f:
            chunks = json.load(f)  # 从缓存加载
    timer.stop()
    print(f"  ✅ {len(chunks)} 块")

    # ======== Step 3: BGE-M3 向量编码 ========
    print("\n🔢 Step 3/8: BGE-M3 向量编码...")
    timer.start("向量编码")
    vectors, chunk_meta = encode_chunks(chunks, use_cache=not rebuild)
    timer.stop()
    print(f"  ✅ {vectors.shape}")

    # ======== Step 4: 实体/关系提取（LightRAG 核心） ========
    print("\n🔍 Step 4/8: 实体/关系提取...")
    timer.start("实体提取")
    ext_cache = os.path.join(config.CACHE_DIR, "entity_extractions.json")
    if rebuild or not os.path.exists(ext_cache):
        # 测试模式仅提取前 50 chunk，全量模式最多 200 chunk
        limit = 50 if test_mode else 200
        extractions = extract_all_chunks(chunks, max_chunks=limit)
        merged = merge_extractions(extractions)  # 去重合并
        with open(ext_cache, "w", encoding="utf-8") as f:
            json.dump({"extractions": extractions, "merged": merged}, f,
                      ensure_ascii=False, indent=2)
    else:
        with open(ext_cache, "r", encoding="utf-8") as f:
            merged = json.load(f)["merged"]  # 从缓存加载
    timer.stop()
    print(f"  ✅ {len(merged['entities'])} 实体, {len(merged['relations'])} 关系")

    # ======== Step 5: 知识图谱构建 ========
    print("\n🕸️ Step 5/8: 构建知识图谱...")
    timer.start("图谱构建")
    if rebuild or not os.path.exists(config.GRAPH_CACHE):
        graph = build_graph(merged["entities"], merged["relations"])
        save_graph(graph, config.GRAPH_CACHE)       # JSON 序列化
        graph_to_html(graph, config.GRAPH_VIZ_PATH)  # D3.js 可视化
    else:
        graph = load_graph(config.GRAPH_CACHE)      # 从缓存加载
    timer.stop()
    print(f"  ✅ {graph.number_of_nodes()} 节点, {graph.number_of_edges()} 边")

    # ======== Step 6: 双模式检索 ========
    print("\n📡 Step 6/8: 双模式检索...")
    timer.start("检索")
    # 确定问题范围：测试模式仅取前 N 题
    questions = config.TEST_QUESTIONS
    if test_mode:
        questions = questions[:config.TEST_MODE_QUESTIONS]
        print(f"  🧪 测试模式: 前 {config.TEST_MODE_QUESTIONS} 题")

    # 延迟加载查询用的 BGE-M3 模型（与 embedder 重用同一模型）
    q_model = SentenceTransformer(
        config.BGE_MODEL_PATH, device="cuda", trust_remote_code=True
    )
    q_model.half()  # FP16 半精度
    q_model.max_seq_length = config.ENCODE_KWARGS["max_length"]

    rag_ctxs = []   # RAG 检索到的上下文列表
    lr_ctxs = []    # LightRAG 检索到的上下文列表
    for q in questions:
        print(f"  📝 问题 [{q['id']}]: {q['question'][:50]}...")
        # 将问题文本编码为向量
        q_vec = np.array(
            q_model.encode(q["question"], normalize_embeddings=True),
            dtype=np.float32
        )
        # RAG 检索（纯向量）
        rag_r = rag_retrieve(q_vec, vectors, chunk_meta)
        for r in rag_r:
            for c in chunks:
                if c["chunk_id"] == r["chunk_id"]:
                    r["text"] = c["text"]; break  # 补充 text 字段
        rag_ctxs.append(build_context(rag_r))
        # LightRAG 检索（向量 + 图谱）
        lr_r = lightrag_retrieve(q_vec, vectors, chunk_meta, chunks, graph, q["question"])
        for r in lr_r:
            if not r.get("text"):
                for c in chunks:
                    if c["chunk_id"] == r["chunk_id"]:
                        r["text"] = c["text"]; break
        lr_ctxs.append(build_context(lr_r))
    timer.stop()

    # ======== Step 7: 问答生成 ========
    print("\n🤖 Step 7/8: 问答生成...")
    timer.start("问答生成")
    rag_ans, lr_ans = batch_generate(questions, rag_ctxs, lr_ctxs)
    # 预览前3题的问答结果
    for i in range(min(3, len(questions))):
        print(f"\n  Q{i+1}: {rag_ans[i]['question'][:50]}...")
        print(f"  [RAG] {rag_ans[i]['answer'][:80]}...")
        print(f"  [LightRAG] {lr_ans[i]['answer'][:80]}...")
    timer.stop()

    # ======== Step 8: RAGAS + LLM 4维评估 ========
    print("\n📊 Step 8/8: RAGAS + LLM 4维评估...")
    timer.start("评估")
    report = evaluate_batch(
        questions, rag_ans, lr_ans, rag_ctxs, lr_ctxs, enable_ragas=True
    )
    save_report(report, config.EVAL_OUTPUT)
    timer.stop()

    # ======== 打印耗时统计 ========
    timer.print_summary()

    # ======== 返回结果汇总 ========
    return {
        "success": True,
        "chunks": len(chunks),
        "entities": len(merged["entities"]),
        "relations": len(merged["relations"]),
        "graph_nodes": graph.number_of_nodes(),
        "graph_edges": graph.number_of_edges(),
        "questions": len(questions),
        "rag_overall": report["llm_4dim"]["comparison"]["rag_overall"],
        "lightrag_overall": report["llm_4dim"]["comparison"]["lightrag_overall"],
        "improvement": report["llm_4dim"]["comparison"]["improvement"],
        "eval_report": config.EVAL_OUTPUT,
        "graph_viz": config.GRAPH_VIZ_PATH
    }


if __name__ == "__main__":
    """命令行入口：支持 --test 和 --rebuild 参数"""
    parser = argparse.ArgumentParser(description="LightRAG 优化系统 — 全流程评估")
    parser.add_argument("--test", action="store_true",
                        help="测试模式（仅处理前2题快速验证）")
    parser.add_argument("--rebuild", action="store_true",
                        help="强制重建所有缓存")
    args = parser.parse_args()
    try:
        r = main(test_mode=args.test, rebuild=args.rebuild)
        # 打印最终结果摘要
        print("\n" + "=" * 60)
        print(f"✅ 完成! RAG={r['rag_overall']}/5 "
              f"LightRAG={r['lightrag_overall']}/5 "
              f"{'↑' if r['improvement']>0 else '↓'}"
              f"{abs(r['improvement']):.2f}")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ 失败: {e}", file=sys.stderr)
        import traceback


        traceback.print_exc()  # 打印完整堆栈便于排查
        sys.exit(1)
