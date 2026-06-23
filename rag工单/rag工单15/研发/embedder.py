# -*- coding: utf-8 -*-
"""
BGE-M3 嵌入模块 — 将文本转换为语义向量。

功能说明：
- 使用 SentenceTransformer 加载 BGE-M3 模型
- 将文本块批量转换为 1024 维向量
- 支持 FP16 半精度推理（减少显存占用）
- 提供安全的模型加载和降级处理
"""
import logging
import numpy as np  # 导入numpy，用于向量运算

logger = logging.getLogger(__name__)
logger.info("embedder 模块加载")


def load_bge_model(model_path, device="cuda"):
    """
    加载 BGE-M3 嵌入模型。

    参数:
        model_path: BGE-M3 模型文件路径
        device: 运行设备，默认cuda（GPU加速）

    返回:
        model: SentenceTransformer 模型实例，加载失败则返回None
    """
    print(f"🔄 正在加载 BGE-M3 模型: {model_path}")  # 打印加载提示
    print(f"  设备: {device}")  # 打印设备信息
    try:  # 尝试加载模型
        from sentence_transformers import SentenceTransformer  # 导入嵌入库

        # 加载模型，指定设备
        model = SentenceTransformer(model_path, device=device)
        # 切换为半精度浮点数（FP16），减少显存占用
        model.half()
        print(f"  ✅ BGE-M3 加载成功！向量维度: 1024")  # 打印成功提示
        return model  # 返回模型
    except Exception as e:  # 如果加载失败
        print(f"  ⚠️ BGE-M3 加载失败: {e}")  # 打印错误信息
        print(f"  ⚠️ 将使用随机向量模拟（仅用于测试）")  # 提示降级
        return None  # 返回None，后续使用降级方案

def embed_texts(model, texts, batch_size=2, max_seq_length=256):
    """
    将文本列表批量编码为向量。

    参数:
        model: BGE-M3 模型实例（None时使用降级方案）
        texts: 文本列表
        batch_size: 批处理大小

    返回:
        numpy数组，形状为(len(texts), 1024)
    """
    if model is None:  # 如果模型加载失败
        print(f"  ⚠️ 使用随机向量降级（测试模式）")  # 提示降级
        # 为每条文本生成随机1024维向量
        return np.random.randn(len(texts), 1024).astype(np.float32)

    print(f"  📊 编码 {len(texts)} 条文本，批次大小 {batch_size}")  # 打印编码信息
    try:  # 尝试编码
        # 使用模型编码文本，转换为列表
        embeddings = model.encode(
            texts,  # 待编码的文本
            batch_size=batch_size,  # 批处理大小
            show_progress_bar=False,  # 不显示进度条（11条数据不需要）
            normalize_embeddings=True,  # 归一化向量（便于余弦相似度计算）
            convert_to_numpy=True,  # 直接返回numpy数组
        )
        # 确保返回numpy数组
        return np.array(embeddings, dtype=np.float32)
    except Exception as e:  # 如果编码失败
        print(f"  ⚠️ 编码失败: {e}")  # 打印错误信息
        return np.random.randn(len(texts), 1024).astype(np.float32)  # 降级

def cosine_similarity(query_vec, doc_vecs):
    """
    计算查询向量与文档向量的余弦相似度。

    参数:
        query_vec: 查询向量，形状 (dim,)
        doc_vecs: 文档向量矩阵，形状 (n, dim)

    返回:
        相似度分数列表
    """
    # 归一化查询向量
    query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
    # 归一化文档向量（逐行）
    doc_norms = doc_vecs / (np.linalg.norm(doc_vecs, axis=1, keepdims=True) + 1e-10)
    # 计算点积（等价于余弦相似度）
    scores = np.dot(doc_norms, query_norm)
    return scores.tolist()  # 返回分数列表
