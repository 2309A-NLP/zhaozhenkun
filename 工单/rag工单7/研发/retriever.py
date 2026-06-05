"""
retriever.py - RAG工单7 检索模块
工单编号: 人工智能NLP-RAG-功能测试及评估
功能: 执行向量检索，从Milvus中为测试问题
      检索最相关的CCF年报文本块
"""

import logging, json, time

# 导入配置
from config import TOP_K, RERANKER_PATH, RERANKER_DEVICE, RERANK_TOP_K, OUTPUT_DIR, LOG_FMT, LOG_DATEFMT
from milvus_handler import MilvusManager

# 设置日志
logging.basicConfig(format=LOG_FMT, datefmt=LOG_DATEFMT, level=logging.INFO)
logger = logging.getLogger("retriever")


class Retriever:
    """RAG检索器：向量检索 + 可选的Reranker重排"""
    def __init__(self):
        self.milvus = MilvusManager()
        self.reranker = None
        self._reranker_loaded = False

    def _load_reranker(self):
        """延迟加载BGE-Reranker（仅需要时加载）"""
        if self._reranker_loaded:
            return
        from FlagEmbedding import FlagReranker
        logger.info(f"加载Reranker: {RERANKER_PATH}")
        self.reranker = FlagReranker(
            RERANKER_PATH,
            use_fp16=True,
            device=RERANKER_DEVICE,
        )
        self._reranker_loaded = True
        logger.info("Reranker加载完成")

    def retrieve(self, query_vector, query_text=None, top_k=None, use_rerank=False):
        """
        检索相关文档
        参数:
            query_vector: 查询向量
            query_text: 查询文本（Reranker需要）
            top_k: 返回数量
            use_rerank: 是否使用Reranker重排
        返回:
            list: 检索结果
        """
        k = top_k or TOP_K
        hits = self.milvus.search(query_vector, top_k=k)

        # 重排
        if use_rerank and query_text and len(hits) > 1:
            self._load_reranker()
            start = time.time()
            pairs = [[query_text, h["content"]] for h in hits]
            scores = self.reranker.compute_score(pairs)
            for i, s in enumerate(scores):
                hits[i]["rerank_score"] = s
            hits.sort(key=lambda h: h.get("rerank_score", 0), reverse=True)
            logger.info(f"重排完成! {time.time()-start:.2f}秒 (取top {RERANK_TOP_K})")
            hits = hits[:RERANK_TOP_K]

        return hits

    def close(self):
        """关闭Milvus连接"""
        self.milvus.close()


def retrieve_for_question(question, query_vector, retriever=None, use_rerank=False):
    """
    为单个问题执行检索的便捷函数
    参数:
        question: 问题文本
        query_vector: 向量
        retriever: Retriever实例
        use_rerank: 是否重排
    返回:
        dict: 检索结果
    """
    if retriever is None:
        retriever = Retriever()

    start = time.time()
    results = retriever.retrieve(query_vector, query_text=question, use_rerank=use_rerank)
    elapsed = time.time() - start

    return {
        "question": question,
        "results": results,
        "count": len(results),
        "time": round(elapsed, 3),
        "sources": list(set(r["source_pdf"] for r in results)),
    }


if __name__ == "__main__":
    """单独测试检索"""
    from embedder import BgeM3Embedder
    e = BgeM3Embedder()
    r = e.encode_query(["平安银行2019年盈利情况如何？"])
    vec = r["dense_vecs"][0].tolist()

    ret = Retriever()
    result = retrieve_for_question("平安银行2019年盈利情况如何？", vec, ret)
    print(f"检索到 {result['count']} 条, 耗时 {result['time']:.2f}秒")
    for hit in result["results"][:3]:
        print(f"  分数={hit['score']:.4f} | {hit['source_pdf']}:{hit['page_num']}")
    ret.close()
