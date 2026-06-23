"""
benchmark.py - RAG工单13 基准测试模块
需求: 运行RAG基准测试，对比优化前后性能 — 工单"基准测试"部分（各组件独立测试+对比）
功能: 1.run_baseline(优化前基线) 2.run_optimized(缓存+预归一化索引+模型复用) 3.compare(对比)
"""
import logging
import json, time, numpy as np   # 需求：序列化结果、计时、向量计算
import 研发.config as config              # 需求：测试问题、检索参数
from 研发.timer import Timer              # 需求：各阶段计时
from 研发.rag_pipeline import load_or_build_index, rag_query  # 需求：完整RAG流水线
from 优化.bottleneck_analyzer import analyze_bottlenecks      # 需求：瓶颈分析
from 优化.optimizer import QueryEmbeddingCache, VectorIndex  # 需求：优化策略

logger = logging.getLogger(__name__)
logger.info("基准测试模块加载")



def run_baseline(questions):
    """优化前基线测试——需求：测量原始RAG系统的性能数据作为基准"""
    print("\n📊 [基线] 加载索引...")
    timer = Timer()
    chunks, vectors, chunk_meta = load_or_build_index(timer)  # 需求：构建/加载向量索引
    print(f"📊 [基线] 运行{len(questions)}个测试问题...")
    q_timer = Timer()
    results = []
    for i, q in enumerate(questions):
        print(f"  [{i+1}/{len(questions)}] {q[:30]}...", end=" ", flush=True)
        t0 = time.time()
        result = rag_query(q, chunks, vectors, chunk_meta, q_timer)  # 需求：执行RAG查询
        elapsed = time.time() - t0
        print(f"{elapsed:.2f}s")
        results.append({"question": q, "total_time": round(elapsed, 3),
                        "stages": result["stage_timings"],
                        "answer_preview": result["answer"][:100]})
    analysis = analyze_bottlenecks(q_timer)  # 需求：对基线结果做瓶颈分析
    return {"mode": "baseline", "question_count": len(questions),
            "total_time": round(q_timer.get_total_time(), 3),
            "avg_time_per_query": round(q_timer.get_total_time() / max(len(questions), 1), 3),
            "results": results, "bottleneck_analysis": analysis}


def run_optimized(questions):
    """优化后测试——需求：应用缓存+预归一化索引+模型复用后测量提升"""
    print("\n📊 [优化后] 加载索引并构建加速索引...")
    timer = Timer()
    chunks, vectors, chunk_meta = load_or_build_index(timer)  # 需求：复用索引缓存
    vec_index = VectorIndex(vectors)  # 需求：优化1-预归一化向量索引
    q_cache = QueryEmbeddingCache()   # 需求：优化2-查询嵌入缓存
    from sentence_transformers import SentenceTransformer
    import torch
    model = SentenceTransformer(config.BGE_MODEL_PATH, device="cuda", trust_remote_code=True)
    model.half()                       # 需求：FP16半精度
    model.max_seq_length = config.ENCODE_KWARGS["max_length"]  # 需求：序列长度控制
    print(f"📊 [优化后] 运行{len(questions)}个测试问题...")
    results = []
    for i, q in enumerate(questions):
        print(f"  [{i+1}/{len(questions)}] {q[:30]}...", end=" ", flush=True)
        t0 = time.time()
        cached_vec = q_cache.get(q)
        if cached_vec is not None:
            q_vec = cached_vec            # 需求：缓存命中，跳过编码
        else:
            q_vec = model.encode(q, normalize_embeddings=True)  # 需求：未命中则编码并缓存
            q_vec = np.array(q_vec, dtype=np.float32)
            q_cache.set(q, q_vec)
        indices, scores = vec_index.search(q_vec, top_k=config.VECTOR_TOP_K)  # 需求：优化检索
        context_parts = [f"[第{chunks[idx]['page']}页]\n{chunks[idx]['text']}" for idx in indices]
        context = "\n\n".join(context_parts)
        from 研发.llm_client import call_llm
        prompt = (f"请基于以下文献内容回答用户问题。\n\n【文献内容】\n{context}\n\n"
                  f"【用户问题】\n{q}\n\n请给出简洁准确的回答：")
        try:
            answer = call_llm(prompt, temperature=config.LLM_TEMPERATURE, max_tokens=config.LLM_MAX_TOKENS)
        except Exception as e:
            answer = f"[失败]{e}"
        elapsed = time.time() - t0
        print(f"{elapsed:.2f}s")
        results.append({"question": q, "total_time": round(elapsed, 3),
                        "cache_hit": cached_vec is not None, "answer_preview": answer[:100]})
    return {"mode": "optimized", "question_count": len(questions),
            "total_time": round(sum(r["total_time"] for r in results), 3),
            "avg_time_per_query": round(sum(r["total_time"] for r in results) / max(len(results), 1), 3),
            "results": results}


def compare(baseline, optimized):
    """优化前后对比——需求：量化提升幅度（秒数/百分比/3秒阈值是否达标）"""
    b_avg, o_avg = baseline["avg_time_per_query"], optimized["avg_time_per_query"]
    improvement = b_avg - o_avg
    pct = (improvement / b_avg * 100) if b_avg > 0 else 0
    return {"baseline_avg_seconds": b_avg, "optimized_avg_seconds": o_avg,
            "improvement_seconds": round(improvement, 3),
            "improvement_percent": round(pct, 1),
            "under_3s_threshold": o_avg < 3.0,  # 需求：验收标准——3秒内返回
            "baseline_total": baseline["total_time"],
            "optimized_total": optimized["total_time"]}

