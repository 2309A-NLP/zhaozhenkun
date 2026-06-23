# -*- coding: utf-8 -*-
"""
==============================================================================
功能说明：BGE-M3 文本向量化服务模块
==============================================================================
本文件实现了基于 BGE-M3 模型的文本向量化功能：
  - load_model(): 加载本地 BGE-M3 模型
  - encode_text(): 将文本编码为 1024 维向量
  - encode_batch(): 批量文本编码
  - compute_similarity(): 计算两段文本的余弦相似度

BGE-M3 是 BAAI 发布的多语言多粒度文本向量模型，支持中英文。
模型路径：bge-m3 本地模型
工单编号：人工智能NLP-Agent数字人项目-文生图智能体任务
==============================================================================
"""

import numpy as np                                 # 数值计算
import torch                                       # PyTorch 深度学习框架
import logging                                     # 日志模块
from typing import List, Optional                  # 类型提示
from sentence_transformers import SentenceTransformer  # 句向量模型库

from config import model_config                    # 导入模型配置

logger = logging.getLogger(__name__)               # 模块日志器


class EmbeddingService:
    """
    BGE-M3 文本向量化服务
    将文本（提示词、描述等）编码为高维向量，用于语义检索
    """

    def __init__(self, model_path: Optional[str] = None):
        """
        初始化向量服务（模型延迟加载）

        参数:
            model_path: BGE-M3 模型路径，默认使用配置中的路径
        """
        self.model_path = model_path or model_config.bge_m3_model_path  # 模型路径
        self.model = None                            # 模型实例（延迟加载）
        self.device = "cuda" if torch.cuda.is_available() else "cpu"  # 自动选择设备
        logger.info(f"向量服务初始化，设备: {self.device}, 模型: {self.model_path}")

    def load_model(self):
        """
        加载 BGE-M3 SentenceTransformer 模型
        首次调用较慢（需要加载约 2GB 模型权重）
        """
        if self.model is not None:                   # 已加载则跳过
            logger.debug("BGE-M3 模型已加载，跳过重复加载")
            return

        logger.info("正在加载 BGE-M3 模型...")       # 记录加载开始
        try:
            self.model = SentenceTransformer(        # 加载 SentenceTransformer
                self.model_path,                     # 本地模型路径
                device=self.device                   # 计算设备
            )
            logger.info("BGE-M3 模型加载完成")       # 记录加载成功
        except Exception as e:                       # 加载失败
            logger.error(f"BGE-M3 模型加载失败: {e}")  # 记录错误
            raise                                    # 抛出异常

    def encode_text(self, text: str) -> np.ndarray:
        """
        将单条文本编码为 1024 维向量

        参数:
            text: 输入文本（如图像生成提示词）

        返回:
            (1024,) numpy 浮点向量
        """
        if self.model is None:                       # 模型未加载
            self.load_model()                        # 加载模型

        logger.debug(f"编码文本: {text[:50]}...")     # 记录（截断显示）
        embedding = self.model.encode(               # 执行编码
            text,                                    # 输入文本
            normalize_embeddings=True                # L2 归一化（用于余弦相似度）
        )
        return embedding.astype(np.float32)          # 返回 float32 向量

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        """
        批量编码多条文本

        参数:
            texts: 文本列表

        返回:
            (N, 1024) numpy 向量矩阵
        """
        if self.model is None:                       # 模型未加载
            self.load_model()                        # 加载模型

        logger.info(f"批量编码 {len(texts)} 条文本")  # 记录批量大小
        embeddings = self.model.encode(              # 批量编码
            texts,                                   # 文本列表
            normalize_embeddings=True,               # L2 归一化
            batch_size=32,                           # 批处理大小
            show_progress_bar=False                  # 不显示进度条
        )
        return embeddings.astype(np.float32)         # 返回 float32 矩阵

    def compute_similarity(self, text1: str, text2: str) -> float:
        """
        计算两段文本的余弦相似度

        参数:
            text1: 第一段文本
            text2: 第二段文本

        返回:
            相似度分数（0~1，越大越相似）
        """
        vec1 = self.encode_text(text1)               # 编码文本1
        vec2 = self.encode_text(text2)               # 编码文本2
        similarity = float(np.dot(vec1, vec2))       # 余弦相似度（已归一化）
        logger.debug(f"相似度: {similarity:.4f}")     # 记录相似度
        return similarity                            # 返回相似度


# 模块级单例（全局复用）
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """
    获取全局 EmbeddingService 单例

    返回:
        EmbeddingService 实例
    """
    global _embedding_service
    if _embedding_service is None:                   # 未创建
        _embedding_service = EmbeddingService()      # 创建实例
    return _embedding_service                        # 返回实例


if __name__ == "__main__":
    from config import setup_logging                 # 导入日志配置
    setup_logging()                                  # 初始化日志
    svc = get_embedding_service()                    # 获取服务实例
    v = svc.encode_text("a photo of a cat")          # 测试编码
    logger = logging.getLogger(__name__)
    logger.info(f"向量维度: {v.shape}, 前5值: {v[:5]}")  # 打印结果
