"""
embedder.py - RAG工单8 向量嵌入模块
工单编号: 人工智能NLP-RAG-基于Graph RAG 实现金融问答
功能: 使用BGE-M3模型将CCF年报文本转换为稠密向量，
      FP16半精度运行，batch_size=2适配RTX 5060 8GB
"""

import logging, json, time
import numpy as np
from config import BGE_M3_PATH, BGE_M3_BATCH, BGE_M3_MAX_LEN, \
    BGE_M3_DEVICE, BGE_M3_FP16, OUTPUT_DIR, LOG_FMT, LOG_DATEFMT

logging.basicConfig(format=LOG_FMT, datefmt=LOG_DATEFMT, level=logging.INFO)
logger = logging.getLogger("embedder")


class BgeM3Embedder:
    """BGE-M3模型封装器，提供文本向量化功能"""

    def __init__(self):
        self.model = None
        self.tokenizer = None
        self._loaded = False

    def load(self):
        """延迟加载模型，避免导入时卡住"""
        if self._loaded:
            return
        logger.info(f"加载BGE-M3模型: {BGE_M3_PATH}")
        t0 = time.time()
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(
            BGE_M3_PATH,
            device=BGE_M3_DEVICE,
            trust_remote_code=True
        )
        if BGE_M3_FP16:
            self.model.half()
        self._loaded = True
        logger.info(f"模型加载完成! 耗时{time.time() - t0:.1f}s, "
                     f"设备={BGE_M3_DEVICE}, FP16={BGE_M3_FP16}")

    def encode_query(self, text):
        """
        编码单个查询文本，返回密集向量
        Args:
            text: 查询字符串
        Returns:
            dict: {"dense_vecs": [numpy数组]}
        """
        self.load()
        vec = self.model.encode(
            text,
            normalize_embeddings=True,
            show_progress_bar=False
        )
        return {"dense_vecs": [vec]}

    def encode_batch(self, texts, batch_size=BGE_M3_BATCH):
        """
        批量编码文本列表
        Args:
            texts: 文本列表
            batch_size: 批处理大小
        Returns:
            list: 每个元素为numpy向量
        """
        self.load()
        logger.info(f"向量化{len(texts)}个文本(batch={batch_size})...")
        all_vecs = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            # 手动截断到最大长度（truncation=True自动处理）
            vecs = self.model.encode(
                batch,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            all_vecs.extend(vecs)
        logger.info(f"向量化完成! 共{len(all_vecs)}个向量")
        return all_vecs


def create_embeddings(chunks):
    """
    对chunks执行批量向量化
    Args:
        chunks: 文本块列表（含content字段）
    Returns:
        dict: {"dense_vectors": [向量列表],
               "chunk_texts": [文本列表],
               "chunk_metas": [元信息列表]}
    """
    embedder = BgeM3Embedder()
    texts = [c["content"] for c in chunks]
    metas = [{
        "index": c["index"],
        "source_pdf": c.get("source_pdf", ""),
        "page_num": c.get("page_num", 0)
    } for c in chunks]
    dense_vectors = embedder.encode_batch(texts)
    data = {
        "dense_vectors": dense_vectors,
        "chunk_texts": texts,
        "chunk_metas": metas,
    }
    logger.info(f"嵌入完成: {len(dense_vectors)}向量, 维度={len(dense_vectors[0])}")
    return data


if __name__ == "__main__":
    """单独测试向量嵌入功能"""
    embedder = BgeM3Embedder()
    result = embedder.encode_query("平安银行2019年营业收入")
    print(f"查询向量维度: {len(result['dense_vecs'][0])}")
    result = create_embeddings([
        {"content": "平安银行2019年实现营收1379亿元", "index": 0, "source_pdf": "test"},
        {"content": "招商银行零售业务收入占比持续提升", "index": 1, "source_pdf": "test"},
    ])
    print(f"批量嵌入: {len(result['dense_vectors'])}个向量")
