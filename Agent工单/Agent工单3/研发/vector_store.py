# -*- coding: utf-8 -*-
"""
==============================================================================
功能说明：Milvus 向量数据库操作模块
==============================================================================
本文件实现了基于 Milvus 的向量存储与检索功能：
  - connect(): 连接 Milvus 服务
  - create_collection(): 创建向量集合（含索引）
  - insert_vector(): 插入文本向量与元数据
  - search_similar(): 语义检索相似提示词
  - get_collection_stats(): 获取集合统计信息

使用 pymilvus 操作 Milvus 2.x 向量数据库。
工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
==============================================================================
"""

import time                                      # 时间模块
import logging                                   # 日志模块
from typing import List, Dict, Optional, Any     # 类型提示
from pymilvus import (                           # Milvus Python SDK
    connections,                                 # 连接管理
    Collection,                                  # 集合对象
    FieldSchema,                                 # 字段定义
    CollectionSchema,                            # 集合 Schema
    DataType,                                    # 数据类型
    utility                                      # 工具函数
)
import numpy as np                               # 数值计算

from config import milvus_config                 # 导入 Milvus 配置

logger = logging.getLogger(__name__)             # 模块日志器


class VectorStore:
    """
    Milvus 向量数据库操作封装
    管理向量集合的创建、插入、检索等操作
    """

    def __init__(self):
        """初始化向量存储（不立即连接）"""
        self.collection = None                   # 集合对象（延迟初始化）
        self.connected = False                   # 连接状态标记
        logger.info("向量存储初始化完成")         # 记录初始化

    def connect(self):
        """
        连接 Milvus 服务
        如已连接则跳过
        """
        if self.connected:                       # 已连接
            logger.debug("已连接 Milvus，跳过")   # 跳过
            return

        try:
            connections.connect(                 # 建立连接
                alias="default",                 # 连接别名
                host=milvus_config.host,         # 服务地址
                port=milvus_config.port          # 服务端口
            )
            self.connected = True                # 标记已连接
            logger.info(f"Milvus 连接成功: {milvus_config.host}:{milvus_config.port}")
        except Exception as e:                   # 连接失败
            logger.error(f"Milvus 连接失败: {e}")  # 记录错误
            raise                                # 抛出异常

    def create_collection(self):
        """
        创建 Milvus 向量集合
        包含 id / prompt_text / embedding / image_path / task_type / created_at 字段
        如集合已存在则跳过
        """
        self.connect()                           # 确保已连接
        name = milvus_config.collection_name     # 集合名称

        if utility.has_collection(name):         # 集合已存在
            self.collection = Collection(name)   # 加载已有集合
            logger.info(f"集合 '{name}' 已存在，直接加载")
            return

        # 定义字段 Schema
        fields = [
            FieldSchema("id", DataType.INT64, is_primary=True, auto_id=True),  # 主键
            FieldSchema("prompt_text", DataType.VARCHAR, max_length=1024),      # 提示词文本
            FieldSchema("embedding", DataType.FLOAT_VECTOR, dim=milvus_config.vector_dim),  # 向量
            FieldSchema("image_path", DataType.VARCHAR, max_length=512),        # 图像保存路径
            FieldSchema("task_type", DataType.VARCHAR, max_length=64),          # 任务类型
            FieldSchema("created_at", DataType.VARCHAR, max_length=32),         # 创建时间
        ]

        schema = CollectionSchema(fields, description="面部生成提示词向量集合")  # 创建 Schema
        self.collection = Collection(name, schema)   # 创建集合

        # 创建向量索引（加速检索）
        index_params = {                         # 索引参数
            "index_type": milvus_config.index_type,  # 索引类型
            "metric_type": milvus_config.metric_type,  # 距离度量
            "params": {"nlist": milvus_config.nlist}   # 聚类中心数
        }
        self.collection.create_index("embedding", index_params)  # 创建索引
        logger.info(f"集合 '{name}' 创建完成，索引: {milvus_config.index_type}")

    def insert_vector(
        self,
        prompt_text: str,
        embedding: np.ndarray,
        image_path: str = "",
        task_type: str = "rotation"
    ) -> int:
        """
        向集合中插入一条向量记录

        参数:
            prompt_text: 生成时使用的提示词
            embedding: 1024 维向量
            image_path: 生成图像的保存路径
            task_type: 任务类型（rotation/outpaint）

        返回:
            插入记录的 ID
        """
        self._ensure_ready()                     # 确保集合就绪
        from datetime import datetime            # 导入时间模块
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # 当前时间

        data = [                                 # 插入数据
            [prompt_text],                       # 提示词
            [embedding.tolist()],                # 向量转列表
            [image_path],                        # 图像路径
            [task_type],                         # 任务类型
            [ts]                                 # 时间戳
        ]

        result = self.collection.insert(data)    # 执行插入
        self.collection.flush()                  # 刷新确保持久化
        pk = result.primary_keys[0]              # 获取主键
        logger.info(f"向量插入成功, id={pk}, prompt='{prompt_text[:30]}...'")
        return pk                                # 返回主键

    def search_similar(
        self,
        query_embedding: np.ndarray,
        top_k: Optional[int] = None,
        task_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        语义检索最相似的提示词记录

        参数:
            query_embedding: 查询向量 (1024,)
            top_k: 返回结果数量（默认使用配置值）
            task_type: 可选过滤任务类型

        返回:
            相似记录列表，每条含 id / prompt_text / image_path / distance / task_type
        """
        self._ensure_ready()                     # 确保集合就绪
        self.collection.load()                   # 加载集合到内存

        k = top_k or milvus_config.top_k         # Top-K 值
        search_params = {                        # 检索参数
            "metric_type": milvus_config.metric_type,
            "params": {"nprobe": 16}
        }

        output_fields = ["prompt_text", "image_path", "task_type", "created_at"]

        # 可选过滤表达式
        expr = f'task_type == "{task_type}"' if task_type else None

        results = self.collection.search(        # 执行检索
            data=[query_embedding.tolist()],     # 查询向量
            anns_field="embedding",              # 检索字段
            param=search_params,                 # 检索参数
            limit=k,                             # Top-K
            expr=expr,                           # 过滤表达式
            output_fields=output_fields          # 输出字段
        )

        records = []                             # 结果列表
        for hit in results[0]:                   # 遍历检索结果
            records.append({                     # 构建记录字典
                "id": hit.id,                    # 记录 ID
                "distance": float(hit.distance), # 相似度距离
                "prompt_text": hit.entity.get("prompt_text"),    # 提示词
                "image_path": hit.entity.get("image_path"),      # 图像路径
                "task_type": hit.entity.get("task_type"),        # 任务类型
                "created_at": hit.entity.get("created_at"),      # 创建时间
            })

        logger.info(f"检索到 {len(records)} 条相似记录, top_1 distance={records[0]['distance']:.4f}" if records else "未检索到相似记录")
        return records                           # 返回结果

    def get_collection_stats(self) -> Dict[str, Any]:
        """
        获取集合统计信息

        返回:
            包含集合名称、记录数等信息的字典
        """
        self._ensure_ready()                     # 确保就绪
        stats = {                                # 构建统计字典
            "collection_name": milvus_config.collection_name,
            "num_entities": self.collection.num_entities,  # 记录总数
            "vector_dim": milvus_config.vector_dim,        # 向量维度
            "index_type": milvus_config.index_type,        # 索引类型
        }
        logger.info(f"集合统计: {stats}")         # 记录统计
        return stats                             # 返回统计

    def _ensure_ready(self):
        """内部方法：确保连接和集合已就绪"""
        if not self.connected:                   # 未连接
            self.connect()                       # 建立连接
        if self.collection is None:              # 集合未创建
            self.create_collection()             # 创建集合


# 模块级单例
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """获取全局 VectorStore 单例"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


if __name__ == "__main__":
    from config import setup_logging
    setup_logging()
    vs = get_vector_store()
    vs.create_collection()
    logger.info(f"集合统计: {vs.get_collection_stats()}")
