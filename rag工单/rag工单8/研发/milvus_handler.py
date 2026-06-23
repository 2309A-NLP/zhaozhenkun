"""
milvus_handler.py - RAG工单8 Milvus向量库操作模块
工单编号: 人工智能NLP-RAG-基于Graph RAG 实现金融问答
功能: 管理CCF年报向量的Milvus集合，支持创建/插入/搜索/
      删除操作，使用IVF_FLAT索引加速检索
"""

import logging, json, time
import numpy as np
from config import MILVUS_HOST, MILVUS_PORT, MILVUS_COLL, \
    MILVUS_DIM, TOP_K, OUTPUT_DIR, LOG_FMT, LOG_DATEFMT

logging.basicConfig(format=LOG_FMT, datefmt=LOG_DATEFMT, level=logging.INFO)
logger = logging.getLogger("milvus_handler")


class MilvusManager:
    """Milvus向量数据库管理器，封装连接/集合/CRUD操作"""

    def __init__(self, host=MILVUS_HOST, port=MILVUS_PORT):
        self.host = host
        self.port = port
        self.collection_name = MILVUS_COLL
        self.dim = MILVUS_DIM
        self.client = None

    def connect(self):
        """连接到Milvus服务"""
        from pymilvus import connections
        connections.connect(host=self.host, port=self.port)
        logger.info(f"已连接Milvus: {self.host}:{self.port}")
        return True

    def close(self):
        """关闭连接"""
        try:
            from pymilvus import connections
            connections.disconnect("default")
        except Exception:
            pass

    def drop_collection(self):
        """删除现有集合（重建用）"""
        from pymilvus import utility
        if utility.has_collection(self.collection_name):
            utility.drop_collection(self.collection_name)
            logger.info(f"已删除集合: {self.collection_name}")

    def ensure_collection(self):
        """确保集合存在，不存在则创建"""
        from pymilvus import Collection, CollectionSchema, FieldSchema, DataType, utility
        if utility.has_collection(self.collection_name):
            logger.info(f"集合已存在: {self.collection_name}")
            return Collection(self.collection_name)
        # 定义字段：id自增、向量、文本内容、源文件名、页码
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.dim),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="source_pdf", dtype=DataType.VARCHAR, max_length=255),
            FieldSchema(name="page_num", dtype=DataType.INT64),
        ]
        schema = CollectionSchema(fields, description="CCF金融年报向量库")
        collection = Collection(self.collection_name, schema)
        logger.info(f"已创建集合: {self.collection_name}, 维度={self.dim}")
        return collection

    def build_index(self, collection):
        """创建IVF_FLAT索引加速检索"""
        index_params = {
            "metric_type": "IP",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128},
        }
        collection.create_index("embedding", index_params)
        collection.load()
        logger.info("索引创建完成, 集合已加载")

    def insert_vectors(self, collection, vectors, texts, metas):
        """
        批量插入向量数据
        Args:
            collection: Milvus集合对象
            vectors: 向量列表
            texts: 文本列表
            metas: 元数据列表([{source_pdf, page_num, index}])
        """
        entities = [
            [v.tolist() if isinstance(v, np.ndarray) else v for v in vectors],
            texts,
            [m.get("source_pdf", "") for m in metas],
            [m.get("page_num", 0) for m in metas],
        ]
        mr = collection.insert(entities)
        logger.info(f"插入完成: {len(vectors)}条")
        return mr

    def search(self, collection, query_vector, top_k=TOP_K):
        """
        向量检索
        Args:
            collection: Milvus集合对象
            query_vector: 查询向量（list或numpy array）
            top_k: 返回Top-K结果
        Returns:
            list: [{"id", "distance", "text", "source_pdf", "page_num"}]
        """
        collection.load()
        qv = [query_vector.tolist()] if isinstance(query_vector, np.ndarray) else [query_vector]
        results = collection.search(
            data=qv,
            anns_field="embedding",
            param={"metric_type": "IP", "params": {"nprobe": 10}},
            limit=top_k,
            output_fields=["text", "source_pdf", "page_num"],
        )
        hits = []
        for hits_row in results:
            for hit in hits_row:
                hits.append({
                    "id": hit.id,
                    "distance": hit.score,
                    "text": hit.entity.get("text", ""),
                    "source_pdf": hit.entity.get("source_pdf", ""),
                    "page_num": hit.entity.get("page_num", 0),
                })
        return hits

    def get_total_count(self):
        """获取集合中的向量总数"""
        from pymilvus import Collection, utility
        if not utility.has_collection(self.collection_name):
            return 0
        collection = Collection(self.collection_name)
        collection.load()
        count = collection.num_entities
        collection.release()
        return count


def create_index_and_insert(dense_vectors, chunk_texts, chunk_metas):
    """便捷函数：创建索引并插入数据"""
    mgr = MilvusManager()
    mgr.connect()
    # 先删除旧集合，确保全新索引
    mgr.drop_collection()
    collection = mgr.ensure_collection()
    mgr.insert_vectors(collection, dense_vectors, chunk_texts, chunk_metas)
    mgr.build_index(collection)
    count = collection.num_entities
    logger.info(f"入库完成! 共{count}条向量")
    mgr.close()
    return count


if __name__ == "__main__":
    """单独测试Milvus操作"""
    mgr = MilvusManager()
    mgr.connect()
    count = mgr.get_total_count()
    print(f"集合 {MILVUS_COLL} 中现有向量: {count}")
    mgr.close()
