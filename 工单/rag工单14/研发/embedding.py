"""
向量嵌入模块
功能：加载 BGE-M3 模型（FP16半精度），将文本块批量编码为向量
说明：安全配置 batch=2, max_length=1024，在 RTX5060(8GB) 上稳定运行
"""
import logging
import os                               # 路径操作
import numpy as np                      # 存向量数据
import pickle                           # 序列化存储
from sentence_transformers import SentenceTransformer  # 加载 BGE 系列模型
import torch                            # 检测 GPU 和 FP16

from config import (
    BGE_MODEL_PATH,                     # BGE-M3 模型路径
    EMBED_BATCH_SIZE,                   # 批量大小（安全=2）
    EMBED_MAX_LENGTH,                   # 最大序列长度（安全=1024）
    EMBED_USE_FP16,                     # 是否使用半精度
    EMBED_DIM,                          # 向量维度
    VECTOR_STORE_DIR,                   # 向量存储目录
)

logger = logging.getLogger(__name__)
logger.info("embedding 模块加载")

def load_bge_m3() -> SentenceTransformer:
    """
    加载 BGE-M3 模型，配置 FP16 半精度和最大序列长度
    返回：配置好的 SentenceTransformer 模型对象
    """
    # 检查模型目录是否存在
    if not os.path.exists(BGE_MODEL_PATH):
        raise FileNotFoundError(f"BGE-M3模型路径不存在: {BGE_MODEL_PATH}")

    print(f"  ⏳ 加载BGE-M3模型从: {BGE_MODEL_PATH}")

    # 加载模型，指定使用 GPU（device="cuda"）
    model = SentenceTransformer(
        BGE_MODEL_PATH,
        device="cuda",                   # 强制使用 GPU
        trust_remote_code=True,          # 信任远程代码（BGE需要）
    )

    # 设置最大序列长度（必须用 model.max_seq_length，不是 encode(max_length=)）
    model.max_seq_length = EMBED_MAX_LENGTH
    print(f"  ✓ max_seq_length 设为: {model.max_seq_length}")

    # 切换到 FP16 半精度，显存占用减半，速度更快
    if EMBED_USE_FP16 and torch.cuda.is_available():
        model.half()
        print(f"  ✓ 已启用 FP16 半精度")

    # 打印 GPU 信息
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        vram = torch.cuda.get_device_properties(0).total_memory / 1024**3
        print(f"  ✓ GPU: {gpu_name} ({vram:.1f}GB)")

    return model

def encode_chunks(model, chunks: list[dict]) -> np.ndarray:
    """
    将文本块批量编码为向量
    参数：model — 已加载的 BGE-M3 模型
          chunks — pdf_parser 返回的分块列表
    返回：numpy 数组，形状 (len(chunks), EMBED_DIM)
    """
    # 从每个块中提取文本
    texts = [c["text"] for c in chunks]

    # 调用模型编码
    print(f"  ⏳ 编码 {len(texts)} 个文本块...")
    embeddings = model.encode(
        texts,
        batch_size=EMBED_BATCH_SIZE,     # 小批量，防止 GPU OOM
        show_progress_bar=True,          # 显示进度条
        normalize_embeddings=True,       # 归一化，后续余弦相似度可直接用点积
    )

    print(f"  ✓ 编码完成：{embeddings.shape[0]} 个向量，维度 {embeddings.shape[1]}")
    return embeddings

def save_embeddings(chunks: list[dict], embeddings: np.ndarray):
    """
    将分块和向量保存到磁盘，下次启动可直接加载
    参数：chunks — 分块列表
          embeddings — 向量矩阵
    """
    # chunks 序列化
    chunks_path = os.path.join(VECTOR_STORE_DIR, "chunks.pkl")
    os.makedirs(os.path.dirname(chunks_path), exist_ok=True)
    with open(chunks_path, "wb") as f:
        pickle.dump(chunks, f)

    # embeddings 存为 .npy 格式
    emb_path = os.path.join(VECTOR_STORE_DIR, "embeddings.npy")
    np.save(emb_path, embeddings)

    print(f"  ✓ 已保存: {chunks_path}")
    print(f"  ✓ 已保存: {emb_path}")

def load_embeddings() -> tuple:
    """
    从磁盘加载分块和向量
    返回：(chunks, embeddings) 元组，文件不存在或读取失败时返回 None, None
    """
    chunks_path = os.path.join(VECTOR_STORE_DIR, "chunks.pkl")
    emb_path = os.path.join(VECTOR_STORE_DIR, "embeddings.npy")

    if not os.path.exists(chunks_path) or not os.path.exists(emb_path):
        return None, None  # 缓存不存在，需要重新编码

    try:
        with open(chunks_path, "rb") as f:
            chunks = pickle.load(f)
        embeddings = np.load(emb_path)
        return chunks, embeddings
    except Exception as e:
        print(f"  ⚠ 向量缓存读取失败（将重建）: {e}")
        return None, None

# ======================== 独立测试入口 ========================
if __name__ == "__main__":
    # 测试本模块：加载模型 + 编码一段文本
    model = load_bge_m3()
    test_vec = encode_chunks(model, [{"text": "静电除尘器的发明人是谁？"}])
    print(f"  向量形状: {test_vec.shape}")
