"""
milvus_handler.py - RAG工单6 Milvus向量库模块
需求: 向量检索(召回) — 向量存储与相似度搜索
功能: Milvus向量库操作封装：连接管理、集合创建、批量插入、向量搜索(IP内积)
"""

import logging, json, os

# 导入配置
from config import MILVUS_HOST, MILVUS_PORT, MILVUS_COLL, MILVUS_DIM, OUTPUT_DIR, LOG_FMT, LOG_DATEFMT

# 设置日志
logging.basicConfig(format=LOG_FMT, datefmt=LOG_DATEFMT, level=logging.INFO)
logger = logging.getLogger("milvus_handler")


class MilvusHandler:
    """
    Milvus操作封装
    提供连接、集合管理、插入和向量搜索功能
    """
    def __init__(self):
        """初始化，延迟连接Milvus"""
        self.collection = None
        self._connected = False

    def connect(self):
        """连接Milvus服务"""
        if self._connected:
            return
        logger.info(f"连接Milvus: {MILVUS_HOST}:{MILVUS_PORT}")
        try:
            from pymilvus import connections
            # 建立与Milvus服务的连接
            connections.connect(alias="default", host=MILVUS_HOST, port=MILVUS_PORT)
            self._connected = True
            logger.info("Milvus连接成功!")
        except Exception as e:
            logger.error(f"连接失败: {e}")
            raise

    def create_collection(self, drop=False):
        """
        创建向量集合，定义字段结构
        参数:
            drop: 是否删除重建
        """
        self.connect()
        try:
            from pymilvus import utility, Collection, CollectionSchema, FieldSchema, DataType

            # 如果集合已存在，根据参数决定是否删除
            if utility.has_collection(MILVUS_COLL):
                if drop:
                    utility.drop_collection(MILVUS_COLL)
                    logger.info(f"删除旧集合: {MILVUS_COLL}")
                else:
                    self.collection = Collection(MILVUS_COLL)
                    logger.info(f"使用已有集合: {MILVUS_COLL}")
                    return

            # 定义字段：主键id、向量vector、文本和元数据字段
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=MILVUS_DIM),
                FieldSchema(name="chunk_index", dtype=DataType.INT64),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
                FieldSchema(name="page_num", dtype=DataType.INT64),
                FieldSchema(name="source_pdf", dtype=DataType.VARCHAR, max_length=255),
            ]
            schema = CollectionSchema(fields=fields, description="工单6混合检索")
            self.collection = Collection(name=MILVUS_COLL, schema=schema)

            # 创建IVF_FLAT索引加速搜索
            index_params = {"metric_type": "IP", "index_type": "IVF_FLAT", "params": {"nlist": 1024}}
            self.collection.create_index(field_name="vector", index_params=index_params)
            self.collection.load()
            logger.info(f"集合创建成功: {MILVUS_COLL}")

        except Exception as e:
            logger.error(f"创建集合失败: {e}")
            raise

    def insert(self, vectors, texts, metas):
        """
        批量插入向量和文本数据
        参数:
            vectors: 稠密向量列表
            texts: 文本内容列表
            metas: 元数据列表（含index, page_num, source_pdf）
        返回:
            list: 插入数据的ID列表
        """
        self.connect()
        if not self.collection:
            self.create_collection()

        logger.info(f"插入 {len(vectors)} 条数据")

        # 提取元数据字段
        indices = [m["index"] for m in metas]
        page_nums = [m["page_num"] for m in metas]
        sources = [m["source_pdf"] for m in metas]

        all_ids = []
        batch_size = 100

        # 分批插入，每批100条
        for i in range(0, len(vectors), batch_size):
            end = min(i + batch_size, len(vectors))
            entities = [
                vectors[i:end],      # vector列
                indices[i:end],      # chunk_index列
                texts[i:end],        # content列
                page_nums[i:end],    # page_num列
                sources[i:end],      # source_pdf列
            ]
            result = self.collection.insert(entities)
            all_ids.extend(result.primary_keys)

        self.collection.flush()
        logger.info(f"插入完成! 共{len(all_ids)}条")
        return all_ids

    def search(self, query_vector, top_k=10):
        """
        向量相似度搜索
        参数:
            query_vector: 查询向量
            top_k: 返回最多k条结果
        返回:
            list: [{id, distance, content, page_num, source_pdf}, ...]
        """
        self.connect()
        if not self.collection:
            from pymilvus import Collection
            self.collection = Collection(MILVUS_COLL)
        self.collection.load()

        # 设置搜索参数
        search_params = {"metric_type": "IP", "params": {"nprobe": 16}}
        results = self.collection.search(
            data=[query_vector],
            anns_field="vector",
            param=search_params,
            limit=top_k,
            output_fields=["chunk_index", "content", "page_num", "source_pdf"],
        )

        # 解析搜索结果
        search_results = []
        for hits in results:
            for hit in hits:
                try:
                    fields = hit.fields if hasattr(hit, 'fields') else hit.entity
                    search_results.append({
                        "id": hit.id,
                        "distance": hit.distance,
                        "chunk_index": fields.get("chunk_index", 0),
                        "content": fields.get("content", ""),
                        "page_num": fields.get("page_num", 0),
                        "source_pdf": fields.get("source_pdf", ""),
                    })
                except Exception:
                    search_results.append({
                        "id": hit.id, "distance": hit.distance,
                        "content": str(hit), "page_num": 0, "source_pdf": "",
                    })

        return search_results

    def drop(self):
        """删除集合"""
        self.connect()
        try:
            from pymilvus import utility
            if utility.has_collection(MILVUS_COLL):
                utility.drop_collection(MILVUS_COLL)
                self.collection = None
                logger.info(f"集合已删除: {MILVUS_COLL}")
        except Exception as e:
            logger.error(f"删除失败: {e}")


if __name__ == "__main__":
    """单独测试Milvus"""
    h = MilvusHandler()
    h.create_collection(drop=True)
    print("集合创建成功!")
