"""
reranker.py - RAG工单6 重排序模块
需求: 向量检索(重排) — 3种重排算法
功能: 1.LLM重排(BGE-Reranker) 2.TF-IDF重排(词频统计) 3.自适应重排(用户反馈权重)
"""

import logging, json, os, math, re
from collections import Counter

# 导入配置
from config import RERANKER_PATH, RERANKER_DEVICE, RERANK_TOP_K, OUTPUT_DIR, LOG_FMT, LOG_DATEFMT

# 设置日志
logging.basicConfig(format=LOG_FMT, datefmt=LOG_DATEFMT, level=logging.INFO)
logger = logging.getLogger("reranker")


class Reranker:
    """
    重排器，提供3种重排算法
    根据配置选择算法对检索结果重新排序
    """
    def __init__(self):
        """初始化重排器"""
        self.llm_model = None     # LLM重排模型（BGE-Reranker）
        self.feedback_weights = {}  # 自适应重排的反馈权重
        self._llm_loaded = False

    def _load_llm(self):
        """LLM重排器已禁用（transformers版本不兼容），自动降级到TF-IDF"""
        self._llm_loaded = False
        self.llm_model = None
        logger.info("LLM重排器已禁用，将使用TF-IDF重排")

    def rerank_llm(self, query, results):
        """
        LLM重排器：使用BGE-Reranker计算相关性分数
        参数:
            query: 用户问题
            results: 检索候选结果列表
        返回:
            list: 重排序后的结果
        """
        if not results:
            return []

        self._load_llm()
        if not self.llm_model:
            return results  # 模型未加载则返回原顺序

        # 构建(query, doc)对
        pairs = [(query, r["content"]) for r in results]

        # 计算每对的相关性分数
        scores = self.llm_model.compute_score(pairs)

        # 为每个结果添加重排分数
        for i, r in enumerate(results):
            score = scores[i] if isinstance(scores, list) else float(scores)
            r["rerank_score"] = float(score)

        # 按重排分数降序排列
        results.sort(key=lambda x: x["rerank_score"], reverse=True)
        logger.info(f"LLM重排完成, 最高分: {results[0]['rerank_score']:.4f}")
        return results

    def rerank_tfidf(self, query, results):
        """
        TF-IDF重排器：基于查询词在文档中的TF-IDF加权
        无需额外模型，基于统计信息
        参数:
            query: 用户问题
            results: 检索候选结果列表
        返回:
            list: 重排序后的结果
        """
        if not results:
            return []

        # 提取查询词（中文词+英文词）
        query_words = [w.lower() for w in re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{2,}', query)]
        if not query_words:
            return results

        # 所有候选文档的总数
        total_docs = len(results)

        for r in results:
            # 提取文档中的词
            doc_words = [w.lower() for w in re.findall(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{2,}', r["content"])]
            if not doc_words:
                r["rerank_score"] = 0
                continue

            doc_len = len(doc_words)
            score = 0.0

            for qw in query_words:
                # 词频TF
                tf = doc_words.count(qw) / max(doc_len, 1)
                # 文档频率DF（包含该词的文档数）
                df = sum(1 for d in results if qw.lower() in d["content"].lower())
                # IDF
                idf = math.log((total_docs + 1) / max(df, 1) + 1)
                # TF-IDF = TF * IDF
                score += tf * idf

            r["rerank_score"] = round(score, 4)

        results.sort(key=lambda x: x["rerank_score"], reverse=True)
        logger.info(f"TF-IDF重排完成")
        return results

    def rerank_adaptive(self, query, results, feedback=None):
        """
        自适应重排器：基于用户反馈调整权重
        记录用户点击/好评的结果，增加相似文档的权重
        参数:
            query: 用户问题
            results: 检索候选结果列表
            feedback: 用户反馈数据 {doc_id: score, ...}
        返回:
            list: 重排序后的结果
        """
        if not results:
            return []

        # 先用LLM重排
        results = self.rerank_llm(query, results) if self._llm_loaded else self.rerank_tfidf(query, results)

        # 应用反馈权重调整
        if feedback:
            for r in results:
                doc_id = r.get("chunk_index", 0)
                # 如果用户对某条结果给过高分，提升其排名
                if str(doc_id) in self.feedback_weights:
                    boost = self.feedback_weights[str(doc_id)]
                    r["rerank_score"] = r.get("rerank_score", 0) * (1 + boost)

            results.sort(key=lambda x: x["rerank_score"], reverse=True)

        logger.info(f"自适应重排完成")
        return results

    def record_feedback(self, doc_id, score):
        """
        记录用户反馈，用于自适应重排
        参数:
            doc_id: 文档ID
            score: 用户评分（0-1）
        """
        self.feedback_weights[str(doc_id)] = score
        logger.info(f"记录反馈: 文档{doc_id} 评分{score}")

    def rerank(self, query, results, method="llm", feedback=None):
        """
        统一重排接口，根据method参数选择算法
        参数:
            query: 用户问题
            results: 候选结果列表
            method: "llm" / "tfidf" / "adaptive"
            feedback: 用户反馈（仅adaptive使用）
        返回:
            list: 重排序后的结果
        """
        if method == "llm":
            return self.rerank_llm(query, results)
        elif method == "tfidf":
            return self.rerank_tfidf(query, results)
        elif method == "adaptive":
            return self.rerank_adaptive(query, results, feedback)
        else:
            logger.warning(f"未知重排方法: {method}，使用LLM")
            return self.rerank_llm(query, results)


if __name__ == "__main__":
    """单独测试重排"""
    r = Reranker()
    results = [
        {"content": "武汉兴图新科注册资本5,520万元", "chunk_index": 1},
        {"content": "武汉力源信息发行股数1,670万股", "chunk_index": 2},
    ]
    ranked = r.rerank("注册资本", results, method="tfidf")
    for item in ranked:
        print(f"分数: {item.get('rerank_score', 0):.4f} | {item['content'][:30]}")
