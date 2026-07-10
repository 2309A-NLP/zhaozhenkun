# 该文件功能：提供真实 FAISS 索引适配，若环境异常则自动回退到点积检索。
import numpy as np

try:
    # 这里尝试导入真实 faiss。
    import faiss
except Exception:
    # 这里在 faiss 不可用时记为 None。
    faiss = None


class SimpleVectorIndex:
    """这里定义轻量向量索引。"""

    def __init__(self):
        # 这里初始化原始向量缓存。
        self.vectors = []
        # 这里初始化 faiss 索引对象。
        self.index = None

    def rebuild(self, vectors: list):
        # 这里重建向量索引。
        self.vectors = vectors
        # 这里在没有向量时直接清空索引。
        if not vectors:
            self.index = None
            return
        # 这里在 faiss 可用时建立真实索引。
        if faiss is not None:
            matrix = np.array(vectors, dtype="float32")
            self.index = faiss.IndexFlatIP(matrix.shape[1])
            self.index.add(matrix)
            return
        # 这里在 faiss 不可用时走回退模式。
        self.index = None

    def search(self, query_vector: np.ndarray, top_k: int = 3):
        # 这里优先使用真实 faiss 检索。
        if self.index is not None:
            scores, indices = self.index.search(np.array([query_vector], dtype="float32"), top_k)
            return [(int(idx), round(float(score), 4)) for idx, score in zip(indices[0], scores[0]) if idx >= 0]
        # 这里在回退模式下执行点积检索。
        scored = []
        for index, vector in enumerate(self.vectors):
            scored.append((index, round(float(np.dot(query_vector, vector)), 4)))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]
