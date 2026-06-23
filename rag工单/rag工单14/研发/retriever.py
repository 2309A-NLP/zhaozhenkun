"""
检索与重排序模块
功能：构建 FAISS 向量索引进行相似度搜索，再用 BGE-Reranker 对结果重排序
说明：先向量检索 Top-K 候选，再精排得到最终答案上下文
"""
import logging
import os                                  # 路径操作
import numpy as np                         # 向量运算
import pickle                              # 序列化存储
import faiss                               # Facebook 向量检索库

from sentence_transformers import CrossEncoder  # 交叉编码器用于重排序

logger = logging.getLogger(__name__)
logger.info("retriever 模块加载")

from config import (

    TOP_K_RETRIEVAL,                       # 向量检索返回数
    TOP_K_RERANK,                          # 重排序后保留数
    RERANKER_PATH,                         # BGE-Reranker 路径
    EMBED_DIM,                             # 向量维度
    VECTOR_STORE_DIR,                      # 存储目录
)

def build_faiss_index(embeddings: np.ndarray) -> faiss.Index:
    """
    用 FAISS 构建向量索引（余弦相似度搜索）
    参数：embeddings — numpy 矩阵，每行一个向量
    返回：构建好的 FAISS 索引对象
    """
    # embeddings 已经是归一化的，用内积（Inner Product）等价于余弦相似度
    dim = embeddings.shape[1]              # 向量维度
    index = faiss.IndexFlatIP(dim)         # 内积索引（余弦相似度）
    index.add(embeddings)                  # 将向量加入索引
    print(f"  ✓ FAISS索引构建完成：{index.ntotal} 个向量")
    return index

def save_index(index: faiss.Index):
    """
    保存 FAISS 索引到磁盘
    参数：index — FAISS 索引对象
    """
    path = os.path.join(VECTOR_STORE_DIR, "faiss_index.bin")
    # 确保目录存在（Windows上需要显式创建）
    os.makedirs(VECTOR_STORE_DIR, exist_ok=True)
    print(f"  💾 保存FAISS索引到: {path}")
    faiss.write_index(index, path)  # 直接用路径字符串
    print(f"  ✓ FAISS索引已保存")

def load_index() -> faiss.Index:
    """
    从磁盘加载 FAISS 索引
    返回：FAISS 索引对象，不存在或读取失败时返回 None
    """
    path = os.path.join(VECTOR_STORE_DIR, "faiss_index.bin")
    if not os.path.exists(path):
        return None
    try:
        return faiss.read_index(path)
    except Exception as e:
        print(f"  ⚠ FAISS索引读取失败（将重建）: {e}")
        return None

def vector_search(query_vec: np.ndarray, index: faiss.Index, top_k: int = None) -> tuple:
    """
    在 FAISS 索引中搜索最相似的 top_k 个向量
    参数：query_vec — 查询向量 (1, dim)
          index — FAISS 索引
          top_k — 返回结果数，默认使用配置值
    返回：(相似度数组, 索引数组)
    """
    if top_k is None:
        top_k = TOP_K_RETRIEVAL

    # 确保查询向量形状正确 (1, dim)
    if query_vec.ndim == 1:
        query_vec = query_vec.reshape(1, -1)

    scores, indices = index.search(query_vec, top_k)  # 执行搜索
    return scores[0], indices[0]                       # 解包为 1D 数组

# ======================== Reranker 单例缓存 ========================
_reranker = None   # 全局缓存 Reranker 模型，避免每次检索都重新加载

def rerank(query: str, chunks: list[dict], top_k: int = None) -> list[dict]:
    """
    用 BGE-Reranker 对检索结果进行重排序
    参数：query — 原始查询文本
          chunks — 待重排序的候选块列表
          top_k — 最终保留数
    返回：重排序后的块列表，按匹配度从高到低排列
    """
    global _reranker

    if top_k is None:
        top_k = TOP_K_RERANK

    if not chunks:
        return []

    # 检查重排序模型路径
    if not os.path.exists(RERANKER_PATH):
        print(f"  ⚠ Reranker模型不存在: {RERANKER_PATH}，跳过重排序")
        return chunks[:top_k]

    # 加载交叉编码器（仅在第一次调用时加载，后续复用缓存）
    if _reranker is None:
        print(f"  ⏳ 加载Reranker模型...")
        _reranker = CrossEncoder(
            RERANKER_PATH,
            device="cuda",                     # GPU 加速
        )
        print(f"  ✓ Reranker模型加载完成")

    # 构造 (query, chunk_text) 对
    pairs = [(query, c["text"]) for c in chunks]

    # 计算每对的匹配分数
    scores = _reranker.predict(pairs)

    # 将分数绑定到块上
    scored = list(zip(scores, chunks))
    scored.sort(key=lambda x: x[0], reverse=True)  # 按分数降序排列

    # 取 top_k 个
    top = scored[:top_k]
    return [item[1] for item in top]

def retrieve(
    query: str,
    query_vec: np.ndarray,
    index: faiss.Index,
    chunks: list[dict],
    do_rerank: bool = True,
) -> list[dict]:
    """
    完整检索流程：向量搜索 → 获取候选块 → 可选重排序
    参数：query — 查询文本
          query_vec — 查询向量
          index — FAISS 索引
          chunks — 全部块列表
          do_rerank — 是否执行重排序
    返回：检索到的相关块列表
    """
    # 第一步：向量搜索，获取候选块索引
    scores, indices = vector_search(query_vec, index, TOP_K_RETRIEVAL)

    # 第二步：根据索引获取块内容
    candidates = []
    for i, idx in enumerate(indices):
        chunk = chunks[idx].copy()         # 复制避免修改原数据
        chunk["score"] = float(scores[i])  # 附上相似度分数
        candidates.append(chunk)

    # 第三步：如果启用重排序，执行交叉编码器精排
    if do_rerank and len(candidates) > 1:
        return rerank(query, candidates, TOP_K_RERANK)
    else:
        return candidates[:TOP_K_RERANK]

# ======================= 独立测试入口 =======================
if __name__ == "__main__":
    # 简单测试
    test_emb = np.random.rand(10, EMBED_DIM).astype(np.float32)
    idx = build_faiss_index(test_emb)
    print(f"  测试索引大小: {idx.ntotal}")
