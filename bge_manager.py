# -*- coding: utf-8 -*-
import torch  # 导入PyTorch深度学习框架，用于GPU加速和模型推理
import numpy as np  # 导入NumPy数值计算库，用于数组操作和数学运算
from typing import List, Dict  # 导入类型注解，用于指定函数参数和返回值的类型
import time  # 导入时间模块，用于性能计时（虽然当前代码未使用）
import hashlib  # 导入哈希库，用于生成文本的MD5哈希值（降级方案时使用）
from utils import reduce_dimension  # 从utils模块导入降维函数，用于向量维度适配

# 全局变量声明
bge_model = None  # BGE-M3嵌入模型实例，用于将文本转换为向量
reranker_model = None  # BGE-Reranker重排序模型实例，用于对检索结果重新排序
reranker_tokenizer = None  # 重排序模型的分词器，用于将文本转换为模型输入格式


def load_bge_models(config: dict, device: str):
    """
    加载BGE模型（BGE-M3嵌入模型和BGE-Reranker重排序模型）

    参数:
        config: 配置字典，包含模型路径等信息
        device: 运行设备，'cuda'表示GPU，'cpu'表示CPU
    """
    global bge_model, reranker_model, reranker_tokenizer  # 声明使用全局变量

    try:
        # 尝试导入SentenceTransformer库（用于加载嵌入模型）
        from sentence_transformers import SentenceTransformer
        print("[INFO] 正在加载 BGE-M3 模型...")  # 打印加载提示
        # 加载BGE-M3模型，指定设备（GPU或CPU）
        bge_model = SentenceTransformer(config["bge_m3_path"], device=device)
        # 打印加载成功信息，显示向量维度和设备
        print(f"[OK] BGE-M3 加载成功 | 维度: {bge_model.get_sentence_embedding_dimension()} | 设备: {device}")
    except Exception as e:
        # 加载失败时打印错误信息
        print(f"[WARN] BGE-M3 加载失败: {e}")

    try:
        # 尝试导入Transformers库的模型和分词器类
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        print("[INFO] 正在加载 BGE-Reranker 模型...")  # 打印加载提示
        # 加载重排序模型的分词器
        reranker_tokenizer = AutoTokenizer.from_pretrained(config["bge_reranker_path"])
        # 加载重排序模型，移动到指定设备，并设置为评估模式
        reranker_model = AutoModelForSequenceClassification.from_pretrained(
            config["bge_reranker_path"]
        ).to(device).eval()  # .eval()禁用Dropout等训练专用层
        print(f"[OK] BGE-Reranker 加载成功 | 设备: {device}")
    except Exception as e:
        # 加载失败时打印错误信息
        print(f"[WARN] BGE-Reranker 加载失败: {e}")


class BGMManager:
    """
    BGE模型管理器类
    负责文本向量化（嵌入）和检索结果重排序
    """

    def __init__(self, device: str, vector_dim: int):
        """
        初始化BGE管理器

        参数:
            device: 运行设备，'cuda'或'cpu'
            vector_dim: 目标向量维度（通常与Milvus中的向量维度一致）
        """
        self.device = device  # 保存设备信息
        self.vector_dim = vector_dim  # 保存目标向量维度
        # 获取BGE模型的输出维度，如果模型未加载则使用目标维度
        self.bge_dim = bge_model.get_sentence_embedding_dimension() if bge_model else vector_dim
        self.embedding_cache = {}  # 初始化嵌入缓存字典，避免重复计算相同文本的向量

    def embed(self, text: str) -> List[float]:
        """
        将文本转换为向量（嵌入）

        参数:
            text: 输入文本字符串

        返回:
            向量列表，长度为vector_dim
        """
        cache_key = text[:1200]  # 使用前1200个字符作为缓存键，减少内存使用
        if cache_key in self.embedding_cache:  # 检查缓存中是否已有该文本的向量
            return self.embedding_cache[cache_key]  # 直接返回缓存的向量

        if bge_model:  # 如果BGE-M3模型已成功加载
            try:
                # 使用BGE模型编码文本，normalize_embeddings=True使向量归一化（长度为1）
                vector = bge_model.encode(cache_key, normalize_embeddings=True).tolist()
                # 如果向量维度与目标维度不一致，进行降维或升维
                if len(vector) != self.vector_dim:
                    vector = reduce_dimension(vector, self.vector_dim)
                self.embedding_cache[cache_key] = vector  # 存入缓存
                return vector  # 返回向量
            except Exception as e:
                # 编码失败时打印错误信息，继续执行降级方案
                print(f"BGE编码失败: {e}")

        # 降级方案：当BGE模型不可用时，使用简单的哈希方法生成伪向量
        h = hashlib.md5(text.encode()).digest()  # 计算文本的MD5哈希值（16字节）
        # 生成伪向量：使用哈希值的每个字节乘以索引，归一化到0-1范围
        vector = [(h[i % 16] * (i + 1)) % 255 / 255.0 for i in range(self.vector_dim)]
        norm = np.linalg.norm(vector)  # 计算向量的L2范数（欧几里得长度）
        # 归一化：使向量长度为1（单位向量），范数为0时保持原样
        vector = (vector / norm).tolist() if norm > 0 else vector
        self.embedding_cache[cache_key] = vector  # 存入缓存
        return vector  # 返回向量

    def rerank(self, query: str, results: List[Dict], top_k: int) -> List[Dict]:
        """
        使用BGE-Reranker模型对检索结果重排序

        参数:
            query: 用户查询文本
            results: 待重排序的结果列表，每个结果包含answer字段
            top_k: 返回前k个最相关的结果

        返回:
            重排序后的结果列表，最多top_k个
        """
        # 如果重排序模型未加载或没有结果，直接返回前top_k个结果
        if reranker_model is None or reranker_tokenizer is None or not results:
            return results[:top_k]

        try:
            # 构建(查询, 文档)对列表，用于计算相关性分数
            pairs = [[query, r.get("answer", "")] for r in results]
            # 使用分词器将文本对转换为模型输入格式
            # padding=True: 自动填充到相同长度，truncation=True: 截断超长文本
            # return_tensors="pt": 返回PyTorch张量格式，max_length=512: 最大长度512
            features = reranker_tokenizer(pairs, padding=True, truncation=True,
                                          return_tensors="pt", max_length=512)
            # 将所有输入张量移动到指定设备（GPU或CPU）
            features = {k: v.to(self.device) for k, v in features.items()}

            with torch.no_grad():  # 禁用梯度计算，节省内存和计算资源
                # 前向传播：获取模型输出logits，通过sigmoid转换为0-1区间的概率分数
                # .view(-1)将输出展平为一维数组，.float()转换为浮点类型，.cpu()移回CPU，.numpy()转为NumPy数组
                scores = torch.sigmoid(reranker_model(**features).logits.view(-1).float()).cpu().numpy()

            # 为每个结果添加重排序分数，并覆盖原有的score字段
            for i, r in enumerate(results):
                r["rerank_score"] = float(scores[i])  # 添加重排序分数
                r["score"] = float(scores[i])  # 使用重排序分数替换原分数

            # 按重排序分数降序排序，返回前top_k个结果
            return sorted(results, key=lambda x: x.get("rerank_score", 0), reverse=True)[:top_k]
        except Exception as e:
            # 重排序失败时，返回原始结果的前top_k个（不进行重排序）
            return results[:top_k]
