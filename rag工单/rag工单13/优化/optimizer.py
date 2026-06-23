"""
optimizer.py - RAG工单13 优化策略模块
需求: 实现性能优化策略 — 工单"优化"部分（查询嵌入缓存、向量索引加速、LLM参数调优）
功能: 1.QueryEmbeddingCache(相同问题MD5缓存) 2.VectorIndex(预归一化加速检索) 3.optimize_llm_params
"""
import logging
import numpy as np, hashlib  # 需求：向量计算 + MD5缓存键
import 研发.config as config           # 需求：读取LLM参数

logger = logging.getLogger(__name__)


class QueryEmbeddingCache:
    """查询嵌入缓存——需求：避免相同问题重复编码（优化查询嵌入阶段的响应时间）"""
    def __init__(self):
        self._cache = {}       # {md5_key: np.ndarray}

    def get(self, question):
        """获取缓存向量——命中返回向量，未命中返回None"""
        return self._cache.get(hashlib.md5(question.encode()).hexdigest())

    def set(self, question, vector):
        """缓存向量——需求：用问题文本的MD5作为key"""
        self._cache[hashlib.md5(question.encode()).hexdigest()] = vector

    def clear(self):
        self._cache.clear()

    @property
    def size(self):
        return len(self._cache)


class VectorIndex:
    """预归一化向量索引——需求：通过预计算范数加速余弦相似度检索"""
    def __init__(self, vectors):
        self.vectors = vectors       # 原始向量矩阵 (N, dim)
        self.norms = np.linalg.norm(vectors, axis=1, keepdims=True)  # 需求：预计算范数
        self.norms[self.norms == 0] = 1.0
        self.normalized = vectors / self.norms  # 需求：预归一化（减少检索时计算量）

    def search(self, query_vec, top_k=5):
        """搜索Top-K相似向量（点积即余弦相似度）——需求：加速向量检索阶段"""
        q_norm = np.linalg.norm(query_vec)
        q_normalized = query_vec / q_norm if q_norm > 0 else query_vec
        scores = np.dot(self.normalized, q_normalized)  # 已归一化，点积=余弦
        top_k = min(top_k, len(scores))
        indices = np.argpartition(scores, -top_k)[-top_k:]
        order = np.argsort(scores[indices])[::-1]
        return indices[order], scores[indices[order]]

    @property
    def size(self):
        return len(self.vectors)


def optimize_llm_params(bottleneck_info):
    """根据瓶颈分析调整LLM参数——需求：针对LLM生成耗时过高的自动调优"""
    suggestions = {}
    for b in bottleneck_info.get("bottlenecks", []):
        if b["stage"] == "llm_generation":
            avg_time = b["avg_seconds"]
            if avg_time > 10:
                suggestions["max_tokens"] = max(512, config.LLM_MAX_TOKENS // 2)
                suggestions["temperature"] = 0.1
                suggestions["note"] = "LLM耗时过长，已降低max_tokens加速"
            elif avg_time > 5:
                suggestions["max_tokens"] = max(1024, config.LLM_MAX_TOKENS - 512)
                suggestions["note"] = "LLM耗时适中，已适度优化"
            else:
                suggestions["note"] = "LLM性能良好，无需调整"
            break
    if not suggestions:
        suggestions["note"] = "未检测到LLM瓶颈，使用默认参数"
    return suggestions
