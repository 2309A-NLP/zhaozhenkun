"""
hybrid_search.py - RAG工单6 混合检索模块
需求: 提供三种检索策略 — 1.向量检索(召回+重排) 2.全文检索(BM25) 3.混合检索(加权RRF融合)
功能: 统一检索接口，支持权重配置，向量/全文/混合三种模式切换
"""
import logging, json, os

from config import TOP_K, RERANK_TOP_K, HYBRID_WEIGHT_VECTOR, HYBRID_WEIGHT_FULLTEXT, OUTPUT_DIR, LOG_FMT, LOG_DATEFMT

logging.basicConfig(format=LOG_FMT, datefmt=LOG_DATEFMT, level=logging.INFO)
logger = logging.getLogger("hybrid_search")


class HybridSearch:
    """混合检索器：整合向量检索和全文检索，支持三种策略"""
    def __init__(self, embedder, milvus, fulltext_engine, reranker):
        self.embedder = embedder
        self.milvus = milvus
        self.fulltext = fulltext_engine
        self.reranker = reranker

    def vector_search(self, query, top_k=None, rerank_top_k=None, rerank_method="llm", **kwargs):
        """向量检索：BGE-M3向量召回 + 重排序"""
        top_k = top_k or TOP_K
        rerank_top_k = rerank_top_k or RERANK_TOP_K
        q_vec = self.embedder.encode_query(query)["dense_vecs"][0].tolist()
        results = self.milvus.search(q_vec, top_k=top_k)
        if not results:
            return {"results": [], "mode": "vector", "total": 0}
        ranked = self.reranker.rerank(query, results, method=rerank_method)[:rerank_top_k]
        if ranked:
            max_s = max(r.get("rerank_score", r.get("distance", 0)) for r in ranked)
            if max_s > 0:
                for r in ranked:
                    r["score"] = round(r.get("rerank_score", r.get("distance", 0)) / max_s, 4)
        logger.info(f"向量检索完成: {len(ranked)}条")
        return {"results": ranked, "mode": "vector", "total": len(ranked)}

    def fulltext_search(self, query, top_k=None, **kwargs):
        """全文检索：BM25关键词匹配 + 分数归一化"""
        results = self.fulltext.search(query, top_k=top_k or RERANK_TOP_K)
        if results:
            max_s = max(r["bm25_score"] for r in results)
            if max_s > 0:
                for r in results:
                    r["score"] = round(r["bm25_score"] / max_s, 4)
                    r["rerank_score"] = r["bm25_score"]
        return {"results": results, "mode": "fulltext", "total": len(results)}

    def hybrid_search(self, query, weight_vector=None, weight_fulltext=None, top_k=None, rerank_method="llm", **kwargs):
        """混合检索：向量+全文分别执行 → RRF倒数排名融合，支持权重调整"""
        w_v = weight_vector or HYBRID_WEIGHT_VECTOR
        w_f = weight_fulltext or HYBRID_WEIGHT_FULLTEXT
        top_k = top_k or RERANK_TOP_K
        logger.info(f"混合检索(向量{w_v}+全文{w_f})")
        vec_r = self.vector_search(query, rerank_method="llm")["results"]
        ft_r = self.fulltext_search(query)["results"]
        if not vec_r and not ft_r:
            return {"results": [], "mode": "hybrid", "total": 0}
        k, seen = 60, {}
        for rank, r in enumerate(vec_r):
            key = r["content"][:100]
            sc = w_v / (k + rank + 1)
            if key not in seen:
                seen[key] = {"content": r["content"], "page_num": r["page_num"],
                             "source_pdf": r.get("source_pdf", ""),
                             "vec_score": r.get("score", 0), "ft_score": 0, "rrf_score": sc}
            else:
                seen[key]["rrf_score"] += sc
                seen[key]["vec_score"] = max(seen[key]["vec_score"], r.get("score", 0))
        for rank, r in enumerate(ft_r):
            key = r["content"][:100]
            sc = w_f / (k + rank + 1)
            if key not in seen:
                seen[key] = {"content": r["content"], "page_num": r["page_num"],
                             "source_pdf": r.get("source_pdf", ""),
                             "vec_score": 0, "ft_score": r.get("bm25_score", 0), "rrf_score": sc}
            else:
                seen[key]["rrf_score"] += sc
                seen[key]["ft_score"] = max(seen[key]["ft_score"], r.get("bm25_score", 0))
        merged = sorted(seen.values(), key=lambda x: x["rrf_score"], reverse=True)
        if merged:
            mx = max(r["rrf_score"] for r in merged)
            for r in merged:
                r["score"] = round(r["rrf_score"] / mx, 4) if mx > 0 else 0
                r["mode"] = "hybrid"
        result = merged[:top_k]
        return {"results": result, "mode": "hybrid", "total": len(result),
                "vector_count": len(vec_r), "fulltext_count": len(ft_r)}

    def search(self, query, mode="hybrid", **kwargs):
        """统一检索接口：mode='vector'/'fulltext'/'hybrid'"""
        if mode == "vector":
            return self.vector_search(query, **kwargs)
        elif mode == "fulltext":
            return self.fulltext_search(query, **kwargs)
        else:
            return self.hybrid_search(query, **kwargs)


if __name__ == "__main__":
    print("此模块需要embedder/milvus/fulltext/reranker实例，通过run.py调用")
