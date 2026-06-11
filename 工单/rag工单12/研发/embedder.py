"""
向量嵌入模块
功能：使用 BGE-M3 模型将文本块编码为稠密向量，支持 FP16 半精度和缓存
完成：适配 8GB 显存（batch=2, max_length=1024），带进度条和缓存加载
"""
import logging

logger = logging.getLogger(__name__)
import sys, os
# 将项目根目录加入路径，支持从任意子目录导入其他模块
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _sub in ["设计", "研发", "测试", "部署"]:
    _p = os.path.join(_root, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import os       # 路径和文件操作
import json     # 保存元数据
import numpy as np  # 向量存储和运算

import config  # 读取模型路径和编码参数


def _lazy_load_model():
    """
    延迟加载 BGE-M3 模型
    返回：SentenceTransformer 模型实例（FP16，CUDA）
    """
    from sentence_transformers import SentenceTransformer
    import torch



    print(f"📦 加载 BGE-M3: {config.BGE_MODEL_PATH}")
    model = SentenceTransformer(
        config.BGE_MODEL_PATH, device="cuda", trust_remote_code=True
    )
    if torch.cuda.is_available():
        model.half()  # FP16 半精度，显存减半
        print(f"  ✅ FP16 已启用, GPU: {torch.cuda.get_device_name(0)}")
    return model


def encode_chunks(
    chunks: list[dict], use_cache: bool = True
) -> tuple[np.ndarray, list[dict]]:
    """
    编码文本块为向量
    参数：
        chunks: [{"chunk_id", "text", ...}, ...]
        use_cache: 是否尝试从缓存加载
    返回：
        (vectors, chunk_meta)
        vectors: (N, hidden_dim) numpy 数组
        chunk_meta: 每个向量的元数据
    """
    # 尝试加载缓存
    if use_cache and os.path.exists(config.VECTORS_CACHE):
        print("📂 从缓存加载向量...")
        vectors = np.load(config.VECTORS_CACHE)
        with open(config.EMBEDDINGS_META, "r", encoding="utf-8") as f:
            chunk_meta = json.load(f)
        print(f"  ✅ {len(vectors)} 个向量, dim={vectors.shape[1]}")
        return vectors, chunk_meta

    # 提取文本和元数据
    texts = [c["text"] for c in chunks]
    chunk_meta = [
        {"chunk_id": c["chunk_id"], "source_pdf": c["source_pdf"],
         "page_num": c["page_num"]}
        for c in chunks
    ]

    model = _lazy_load_model()
    # 设置最大序列长度（sentence-transformers 2.x 需通过模型属性设置）
    model.max_seq_length = config.ENCODE_KWARGS["max_length"]
    print(f"🔢 编码 {len(texts)} 个文本块, batch={config.ENCODE_KWARGS['batch_size']}, "
          f"max_seq={model.max_seq_length}...")

    embeddings = model.encode(
        texts,
        batch_size=config.ENCODE_KWARGS["batch_size"],
        show_progress_bar=config.ENCODE_KWARGS["show_progress_bar"],
        normalize_embeddings=True  # 归一化，方便余弦相似度
    )

    vectors = np.array(embeddings, dtype=np.float32)
    print(f"  ✅ 完成: {vectors.shape}")

    # 缓存
    np.save(config.VECTORS_CACHE, vectors)
    with open(config.EMBEDDINGS_META, "w", encoding="utf-8") as f:
        json.dump(chunk_meta, f, ensure_ascii=False, indent=2)
    print(f"💾 已缓存: {config.VECTORS_CACHE}")

    return vectors, chunk_meta


def cosine_similarity(query_vec: np.ndarray, all_vecs: np.ndarray) -> np.ndarray:
    """
    计算查询向量与所有向量的余弦相似度
    因为 encode 时已 normalize_embeddings=True，直接点积即可
    """
    if query_vec.ndim == 1:
        query_vec = query_vec.reshape(1, -1)
    return np.dot(all_vecs, query_vec.T).flatten()


def search_similar(
    query_vec: np.ndarray, vectors: np.ndarray, top_k: int = 10
) -> tuple[np.ndarray, np.ndarray]:
    """检索最相似的 top_k 个向量，返回 (indices, scores)"""
    scores = cosine_similarity(query_vec, vectors)
    top_indices = np.argsort(scores)[::-1][:top_k]
    return top_indices, scores[top_indices]
