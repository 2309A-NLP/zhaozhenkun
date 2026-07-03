"""
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
矢量存储模块 —— 支持多种嵌入模型后端
"""

import os  # 导入操作系统接口模块，用于环境变量设置
import logging  # 导入日志模块，用于记录运行状态
import threading  # 导入线程模块，用于写操作加锁保证线程安全
import numpy as np  # 导入numpy数值计算库，使用别名np，用于向量运算
from typing import List, Dict, Optional  # 导入类型提示：List（列表）、Dict（字典）、Optional（可选类型）
from pathlib import Path  # 导入Path用于文件系统路径操作

import chromadb  # 导入ChromaDB向量数据库客户端库
from chromadb.config import Settings  # 从ChromaDB导入Settings配置类

_log = logging.getLogger("medical_agent.rag.vector_store")  # 创建模块级日志记录器，标识为"medical_agent.rag.vector_store"

from config import CHROMA_DIR, CHROMA_COLLECTION_NAME, EMBEDDING_MODEL, RAG_TOP_K, RAG_SIMILARITY_THRESHOLD  # 从项目配置导入：ChromaDB持久化目录、集合名、嵌入模型名、检索top-K数量、相似度阈值


class Embedder:  # 定义嵌入模型封装类：自动选择可用后端（sentence-transformers或TF-IDF）
    """嵌入模型封装 —— 自动选择可用后端"""

    def __init__(self, model_name: str = None):  # 构造函数：model_name可选，不传则使用配置文件中的默认模型
        self.model_name = model_name or EMBEDDING_MODEL  # 设置模型名称：优先使用传入参数，否则使用配置默认值
        self._model = None  # 初始化模型实例为None（延迟加载）
        self._backend = None  # 初始化后端类型标识为None
        self._init_model()  # 调用模型初始化方法

    def _init_model(self):  # 私有方法：按优先级依次尝试多种后端初始化嵌入模型
        """尝试多种后端初始化嵌入模型"""
        # 方案1: 尝试通过 HF 镜像加载 sentence-transformers  # 注释：优先使用HuggingFace国内镜像加速下载
        try:  # 异常捕获：处理网络错误或包未安装
            os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"  # 设置HuggingFace镜像站点环境变量（国内加速下载）
            from sentence_transformers import SentenceTransformer  # 导入sentence-transformers库的SentenceTransformer类
            self._model = SentenceTransformer(self.model_name)  # 使用指定模型名创建SentenceTransformer实例（自动从镜像下载）
            self._backend = "sentence-transformers (HF Mirror)"  # 标记后端类型为使用HF镜像的sentence-transformers
            _log.info("嵌入模型已加载: %s via %s", self.model_name, self._backend)  # 记录成功日志：模型名和后端类型
            return  # 初始化成功直接返回
        except Exception as e:  # 捕获HF镜像加载失败异常
            _log.warning("HF Mirror 加载失败: %s", e)  # 记录警告日志

        # 方案2: 尝试本地缓存  # 注释：如果镜像下载失败，尝试使用已缓存到本地的模型
        try:  # 异常捕获
            from sentence_transformers import SentenceTransformer  # 重新导入SentenceTransformer（确保可用）
            cache_dir = os.path.expanduser("~/.cache/huggingface/hub")  # 构造HuggingFace缓存目录路径
            if os.path.exists(cache_dir):  # 检查本地缓存目录是否存在
                self._model = SentenceTransformer(  # 创建SentenceTransformer实例
                    self.model_name,  # 指定模型名称
                    cache_folder=cache_dir,  # 指定缓存目录路径
                    local_files_only=True,  # 设置仅使用本地文件（不联网下载）
                )
                self._backend = "sentence-transformers (本地缓存)"  # 标记后端为本地缓存模式
                _log.info("嵌入模型已加载: 本地缓存")  # 记录成功日志
                return  # 初始化成功返回
        except Exception:  # 捕获本地缓存加载失败异常
            pass  # 静默跳过，继续尝试下一种方案

        # 方案3: 使用 sklearn TF-IDF 作为后备  # 注释：最终兜底方案，使用轻量级TF-IDF（无需下载任何模型）
        try:  # 异常捕获
            from sklearn.feature_extraction.text import TfidfVectorizer  # 导入sklearn的TF-IDF向量化器
            self._model = TfidfVectorizer(max_features=384)  # 创建TF-IDF向量化器，限制最大特征数为384维（与常见嵌入维度一致）
            self._fitted = False  # 初始化拟合状态为False（首次使用前需要拟合）
            self._corpus = []  # 初始化语料库列表为空（用于收集文本后批量拟合）
            self._backend = "TF-IDF (sklearn)"  # 标记后端为TF-IDF
            _log.info("使用 TF-IDF 嵌入（无需下载模型）")  # 记录信息日志
            return  # 初始化成功返回
        except Exception as e:  # 捕获TF-IDF加载失败异常（sklearn也未安装）
            raise RuntimeError(f"无法初始化任何嵌入模型: {e}")  # 抛出运行时错误：所有后端均不可用

    def encode(self, texts: List[str]) -> np.ndarray:  # 文本编码方法：将文本列表编码为向量数组
        """编码文本为向量"""
        if self._backend and "TF-IDF" in self._backend:  # 如果当前后端是TF-IDF
            if not self._fitted:  # 如果TF-IDF模型尚未拟合
                self._model.fit(self._corpus + texts)  # 对语料库加当前文本进行拟合（合并保证词汇覆盖）
                self._fitted = True  # 标记已拟合
            vectors = self._model.transform(texts).toarray()  # 将文本转换为TF-IDF稀疏矩阵后转为密集数组
            # 如果特征维度不够384，补零；如果超过，截断  # 注释：统一向量维度到384
            if vectors.shape[1] < 384:  # 如果特征维度小于384
                padded = np.zeros((vectors.shape[0], 384))  # 创建全零矩阵，形状为(样本数, 384)
                padded[:, :vectors.shape[1]] = vectors  # 将原始向量填入前N列
                return padded  # 返回补零后的向量
            return vectors[:, :384]  # 特征维度超过384则截断到前384维
        else:  # 使用sentence-transformers后端
            return self._model.encode(texts)  # 直接调用SentenceTransformer的encode方法编码文本

    def add_to_corpus(self, texts: List[str]):  # 向TF-IDF语料库添加文本的方法（用于增量更新词汇表）
        """向 TF-IDF 语料库添加文本，并重新拟合模型保持嵌入空间一致"""
        if self._backend and "TF-IDF" in self._backend:  # 仅在使用TF-IDF后端时执行
            self._corpus.extend(texts)  # 将新文本追加到语料库列表
            # 扩展语料后需要重新拟合以确保词汇表包含所有文档  # 注释：重新拟合保证词汇表完整性
            from sklearn.feature_extraction.text import TfidfVectorizer  # 重新导入TfidfVectorizer用于创建新模型
            old_params = self._model.get_params()  # 获取旧模型的参数字典
            self._model = TfidfVectorizer(**{k: v for k, v in old_params.items()  # 使用旧参数创建新的TF-IDF向量化器（排除dtype和analyzer参数）
                                              if k not in ('dtype', 'analyzer')})  # 过滤掉dtype和analyzer参数（会导致重拟合问题）
            self._model.fit(self._corpus)  # 用完整的语料库重新拟合模型
            self._fitted = True  # 标记已拟合


class VectorStore:  # 定义向量存储类：基于ChromaDB的持久化向量数据库封装
    """ChromaDB 向量存储（异常安全——DB损坏时自动降级为空存储）"""

    def __init__(  # 构造函数
        self,  # 实例自身引用
        persist_dir: str = None,  # 持久化目录路径（可选，默认使用配置值）
        collection_name: str = None,  # 集合（collection）名称（可选，默认使用配置值）
    ):
        self.persist_dir = str(persist_dir or CHROMA_DIR)  # 设置持久化目录：优先参数值，否则使用配置
        self.collection_name = collection_name or CHROMA_COLLECTION_NAME  # 设置集合名称：优先参数值，否则使用配置
        self._ok = False  # 数据库就绪标志：初始化为False（数据库是否正常）
        self._write_lock = threading.Lock()  # 创建写操作互斥锁，保证多线程写入安全
        self._embedder = None  # 嵌入模型实例：延迟加载，后续按需初始化

        try:  # 异常捕获：处理数据库初始化失败
            self._client = chromadb.PersistentClient(  # 创建ChromaDB持久化客户端
                path=self.persist_dir,  # 指定数据库持久化目录
                settings=Settings(anonymized_telemetry=False),  # 禁用匿名遥测数据收集
            )
            self._embedder = Embedder()  # 创建嵌入模型实例
            self._collection = self._client.get_or_create_collection(  # 获取或创建集合（不存在则自动创建）
                name=self.collection_name,  # 指定集合名称
                metadata={"hnsw:space": "cosine", "description": "医学知识库"},  # 设置元数据：HNSW索引使用余弦距离，描述为医学知识库
            )
            self._ok = True  # 数据库初始化成功，设置就绪标志为True
        except Exception as e:  # 捕获初始化异常（可能是旧版本数据格式不兼容）
            _log.warning("ChromaDB 读取失败: %s — 尝试重建", e)  # 记录警告日志
            try:  # 自动恢复：删除旧集合后重建
                self._client.delete_collection(self.collection_name)  # 删除损坏的旧集合
                _log.info("已删除损坏的集合: %s", self.collection_name)  # 记录恢复日志
                self._collection = self._client.get_or_create_collection(  # 重新创建集合
                    name=self.collection_name,  # 使用相同的集合名称
                    metadata={"hnsw:space": "cosine", "description": "医学知识库"},  # 相同的元数据配置
                )
                self._ok = True  # 恢复成功，设置就绪标志
                _log.info("ChromaDB 自动恢复成功")  # 记录恢复成功日志
            except Exception as e2:  # 自动恢复也失败
                _log.error("ChromaDB 恢复失败: %s — RAG功能不可用", e2)  # 记录错误日志
                self._client = None  # 将客户端引用置None
                self._collection = None  # 将集合引用置None
                self._ok = False  # 确保就绪标志为False

    @property  # 声明为属性（property）装饰器，可以像属性一样访问
    def collection(self):  # 获取当前ChromaDB集合的属性方法
        return self._collection  # 返回集合对象引用

    def add_documents(self, documents, metadatas=None, ids=None):  # 添加文档到向量数据库：文档列表、元数据列表、ID列表
        if not self._ok or not documents: return 0  # 如果数据库不可用或文档为空则直接返回0（添加0条）
        try:  # 异常捕获
            if not self._embedder: return 0  # 如果嵌入模型未初始化则返回0
            self._embedder.add_to_corpus(documents)  # 将文档添加到嵌入模型的语料库中（TF-IDF后端需要）
            embeddings = self._embedder.encode(documents).tolist()  # 将文档编码为向量并转为Python列表格式
            if ids is None:  # 如果未提供文档ID
                import uuid; ids = [str(uuid.uuid4()) for _ in documents]  # 为每个文档生成UUID作为唯一标识符
            if metadatas is None: metadatas = [{} for _ in documents]  # 如果未提供元数据则为每个文档生成空字典
            BATCH_SIZE = 5000; total = 0  # 设置批量插入大小为5000条，初始化总计数器为0
            with self._write_lock:  # 获取写锁（线程安全）
                for i in range(0, len(documents), BATCH_SIZE):  # 按批次大小遍历文档列表
                    end = min(i+BATCH_SIZE, len(documents))  # 计算当前批次的结束位置（不超过列表长度）
                    self._collection.add(embeddings=embeddings[i:end], documents=documents[i:end],  # 批量添加：当前批次的嵌入向量和文档内容
                                         metadatas=metadatas[i:end], ids=ids[i:end])  # 批量添加：当前批次的元数据和ID
                    total += (end - i)  # 累加本批次添加的文档数
            return total  # 返回总共添加的文档数量
        except Exception as e:  # 捕获添加过程中的异常
            _log.error("添加文档失败: %s", e)  # 记录错误日志
            return 0  # 返回0表示添加失败

    def search(self, query, top_k=None, threshold=None):  # 向量相似度搜索：查询文本→top_k最相似文档
        if not self._ok or not self._collection or not self._embedder: return []  # 数据库、集合或嵌入模型任一不可用则返回空列表
        try:  # 异常捕获
            top_k = top_k or RAG_TOP_K  # 设置检索数量：优先传入值，否则使用配置文件默认值
            threshold = threshold or RAG_SIMILARITY_THRESHOLD  # 设置相似度阈值：优先传入值，否则使用配置
            qe = self._embedder.encode([query]).tolist()  # 将查询文本编码为向量并转为列表
            results = self._collection.query(query_embeddings=qe, n_results=top_k,  # 执行向量相似度查询：传入查询向量和返回数量
                                              include=["documents","metadatas","distances"])  # 指定返回字段：文档内容、元数据、距离
            if not results["ids"] or not results["ids"][0]: return []  # 如果查询无结果则返回空列表
            docs = []  # 初始化结果列表
            for i, did in enumerate(results["ids"][0]):  # 遍历查询结果的ID列表
                dist = results["distances"][0][i]; sim = 1.0 - dist  # 获取距离值并转换为相似度（cosine距离→相似度=1-距离）
                if sim >= threshold:  # 如果相似度达到阈值要求
                    docs.append({"id":did, "content":results["documents"][0][i],  # 添加到结果列表：文档ID和内容
                                 "score":round(sim,4),  # 相似度分数保留4位小数
                                 "metadata":results["metadatas"][0][i] if results["metadatas"] else {}})  # 元数据（如果存在）
            return docs  # 返回过滤后的相似文档列表
        except Exception as e:  # 捕获搜索异常
            _log.error("搜索失败: %s", e)  # 记录错误日志
            return []  # 返回空列表

    def count(self):  # 获取集合中文档总数的方法
        if not self._ok or not self._collection: return 0  # 数据库不可用则返回0
        try: return self._collection.count()  # 调用ChromaDB集合的count方法获取文档数
        except: return 0  # 异常时返回0

    def delete_all(self):  # 清空集合中所有文档的方法
        if not self._ok: return  # 数据库不可用则直接返回
        try:  # 异常捕获
            with self._write_lock:  # 获取写锁（线程安全）
                self._client.delete_collection(self.collection_name)  # 删除整个集合（清空所有数据）
                self._collection = self._client.get_or_create_collection(  # 重新创建同名空集合
                    name=self.collection_name, metadata={"hnsw:space":"cosine"})  # 指定集合名和余弦距离索引
        except Exception as e:  # 捕获清空异常
            _log.error("清空失败: %s", e)  # 记录错误日志

    def get_stats(self):  # 获取向量存储统计信息的方法
        return {"collection_name":self.collection_name, "document_count":self.count(),  # 返回集合名和文档总数
                "embedding_backend":self._embedder._backend if self._embedder else "N/A",  # 返回嵌入后端类型（嵌入模型未初始化则显示N/A）
                "persist_dir":self.persist_dir, "ok":self._ok}  # 返回持久化目录路径和数据库就绪状态


# 全局单例  # 注释：用于存储VectorStore的唯一实例
_vector_store: Optional[VectorStore] = None  # 全局VectorStore单例变量，类型标注为Optional[VectorStore]，初始为None


def get_vector_store() -> VectorStore:  # 获取向量存储单例的工厂函数
    """获取向量存储单例"""
    global _vector_store  # 声明使用全局变量_vector_store
    if _vector_store is None:  # 检查单例是否已创建
        _vector_store = VectorStore()  # 未创建则新建实例（懒加载模式）
    return _vector_store  # 返回向量存储单例
