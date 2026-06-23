"""
embedder.py - RAG工单6 向量嵌入模块
需求: 向量检索(召回) — BGE-M3文本向量化
功能: 使用BGE-M3模型将文本转为稠密向量，FP16+batch=2安全运行在RTX5060
"""

import logging, json, os, time

# 导入配置
from config import BGE_M3_PATH, BGE_M3_BATCH, BGE_M3_MAX_LEN, BGE_M3_DEVICE, BGE_M3_FP16, OUTPUT_DIR, LOG_FMT, LOG_DATEFMT

# 设置日志
logging.basicConfig(format=LOG_FMT, datefmt=LOG_DATEFMT, level=logging.INFO)
logger = logging.getLogger("embedder")


class BgeM3Embedder:
    """
    BGE-M3嵌入模型封装
    支持文本批量向量化，FP16减少显存占用
    """
    def __init__(self):
        """初始化，模型延迟加载"""
        self.model = None
        self._loaded = False

    def load(self):
        """加载BGE-M3模型（仅第一次调用时加载）"""
        if self._loaded:
            return
        logger.info(f"加载BGE-M3: {BGE_M3_PATH}")
        start = time.time()
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(
                BGE_M3_PATH, device=BGE_M3_DEVICE, trust_remote_code=True,
            )
            if BGE_M3_FP16 and BGE_M3_DEVICE == "cuda":
                self.model.half()
            self._loaded = True
            logger.info(f"BGE-M3加载完成! {time.time()-start:.1f}秒")
        except Exception as e:
            logger.error(f"BGE-M3加载失败: {e}")
            raise

    def encode(self, texts):
        """
        批量编码文本为稠密向量
        参数:
            texts: 文本字符串列表
        返回:
            dict: {"dense_vecs": ndarray, "lexical_weights": list}
        """
        self.load()
        logger.info(f"编码 {len(texts)} 条文本")
        start = time.time()
        # 调用模型编码，返回稠密向量
        embeddings = self.model.encode(
            sentences=texts, batch_size=BGE_M3_BATCH,
            show_progress_bar=True, normalize_embeddings=True,
        )
        embeddings = {"dense_vecs": embeddings}
        elapsed = time.time() - start
        logger.info(f"编码完成! {elapsed:.2f}秒")
        return embeddings

    def encode_query(self, query):
        """编码单条查询"""
        return self.encode([query])


def create_embeddings(chunks):
    """
    为所有文本块创建向量嵌入
    参数:
        chunks: text_chunker返回的文本块列表
    返回:
        dict: 包含dense_vectors, chunk_texts, chunk_metas
    """
    # 创建嵌入器实例
    embedder = BgeM3Embedder()
    logger.info(f"为 {len(chunks)} 个文本块生成向量")

    # 提取所有文本内容
    texts = [c["content"] for c in chunks]

    # 分批处理，每批50条
    batch_size = 50
    all_vecs = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        logger.info(f"批次 {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}")
        result = embedder.encode(batch)
        all_vecs.extend(result["dense_vecs"].tolist())

    # 准备元数据
    metas = [{
        "index": c["index"],
        "source_pdf": c["source_pdf"],
        "page_num": c["page_num"],
    } for c in chunks]

    result = {
        "dense_vectors": all_vecs,
        "chunk_texts": texts,
        "chunk_metas": metas,
    }

    # 保存向量信息
    out_path = os.path.join(OUTPUT_DIR, "embeddings.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "count": len(all_vecs),
            "dim": len(all_vecs[0]) if all_vecs else 0,
        }, f, ensure_ascii=False, indent=2)

    logger.info(f"向量化完成! {len(all_vecs)} 个向量")
    return result


if __name__ == "__main__":
    """单独测试向量化"""
    e = BgeM3Embedder()
    r = e.encode(["武汉兴图新科注册资本是多少？"])
    print(f"向量形状: {r['dense_vecs'].shape}")
