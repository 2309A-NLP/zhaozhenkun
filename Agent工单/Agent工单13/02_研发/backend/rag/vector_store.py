"""
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
矢量存储模块 —— 支持多种嵌入模型后端
"""

import os
import logging
import threading
import numpy as np
from typing import List, Dict, Optional
from pathlib import Path

import chromadb
from chromadb.config import Settings

_log = logging.getLogger("medical_agent.rag.vector_store")

from config import CHROMA_DIR, CHROMA_COLLECTION_NAME, EMBEDDING_MODEL, RAG_TOP_K, RAG_SIMILARITY_THRESHOLD


class Embedder:
    """嵌入模型封装 —— 自动选择可用后端"""

    def __init__(self, model_name: str = None):
        self.model_name = model_name or EMBEDDING_MODEL
        self._model = None
        self._backend = None
        self._init_model()

    def _init_model(self):
        """尝试多种后端初始化嵌入模型"""
        # 方案1: 尝试通过 HF 镜像加载 sentence-transformers
        try:
            os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
            self._backend = "sentence-transformers (HF Mirror)"
            _log.info("嵌入模型已加载: %s via %s", self.model_name, self._backend)
            return
        except Exception as e:
            _log.warning("HF Mirror 加载失败: %s", e)

        # 方案2: 尝试本地缓存
        try:
            from sentence_transformers import SentenceTransformer
            cache_dir = os.path.expanduser("~/.cache/huggingface/hub")
            if os.path.exists(cache_dir):
                self._model = SentenceTransformer(
                    self.model_name,
                    cache_folder=cache_dir,
                    local_files_only=True,
                )
                self._backend = "sentence-transformers (本地缓存)"
                _log.info("嵌入模型已加载: 本地缓存")
                return
        except Exception:
            pass

        # 方案3: 使用 sklearn TF-IDF 作为后备
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            self._model = TfidfVectorizer(max_features=384)
            self._fitted = False
            self._corpus = []
            self._backend = "TF-IDF (sklearn)"
            _log.info("使用 TF-IDF 嵌入（无需下载模型）")
            return
        except Exception as e:
            raise RuntimeError(f"无法初始化任何嵌入模型: {e}")

    def encode(self, texts: List[str]) -> np.ndarray:
        """编码文本为向量"""
        if self._backend and "TF-IDF" in self._backend:
            if not self._fitted:
                self._model.fit(self._corpus + texts)
                self._fitted = True
            vectors = self._model.transform(texts).toarray()
            # 如果特征维度不够384，补零；如果超过，截断
            if vectors.shape[1] < 384:
                padded = np.zeros((vectors.shape[0], 384))
                padded[:, :vectors.shape[1]] = vectors
                return padded
            return vectors[:, :384]
        else:
            return self._model.encode(texts)

    def add_to_corpus(self, texts: List[str]):
        """向 TF-IDF 语料库添加文本，并重新拟合模型保持嵌入空间一致"""
        if self._backend and "TF-IDF" in self._backend:
            self._corpus.extend(texts)
            # 扩展语料后需要重新拟合以确保词汇表包含所有文档
            from sklearn.feature_extraction.text import TfidfVectorizer
            old_params = self._model.get_params()
            self._model = TfidfVectorizer(**{k: v for k, v in old_params.items()
                                              if k not in ('dtype', 'analyzer')})
            self._model.fit(self._corpus)
            self._fitted = True


class VectorStore:
    """ChromaDB 向量存储（异常安全——DB损坏时自动降级为空存储）"""

    def __init__(
        self,
        persist_dir: str = None,
        collection_name: str = None,
    ):
        self.persist_dir = str(persist_dir or CHROMA_DIR)
        self.collection_name = collection_name or CHROMA_COLLECTION_NAME
        self._ok = False  # 数据库是否正常
        self._write_lock = threading.Lock()
        self._embedder = None  # 延迟加载

        try:
            self._client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=Settings(anonymized_telemetry=False),
            )
            self._embedder = Embedder()
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine", "description": "医学知识库"},
            )
            self._ok = True
        except Exception as e:
            _log.error("ChromaDB 初始化失败: %s — RAG功能暂不可用", e)
            self._client = None
            self._collection = None
            self._ok = False

    @property
    def collection(self):
        return self._collection

    def add_documents(self, documents, metadatas=None, ids=None):
        if not self._ok or not documents: return 0
        try:
            if not self._embedder: return 0
            self._embedder.add_to_corpus(documents)
            embeddings = self._embedder.encode(documents).tolist()
            if ids is None:
                import uuid; ids = [str(uuid.uuid4()) for _ in documents]
            if metadatas is None: metadatas = [{} for _ in documents]
            BATCH_SIZE = 5000; total = 0
            with self._write_lock:
                for i in range(0, len(documents), BATCH_SIZE):
                    end = min(i+BATCH_SIZE, len(documents))
                    self._collection.add(embeddings=embeddings[i:end], documents=documents[i:end],
                                         metadatas=metadatas[i:end], ids=ids[i:end])
                    total += (end - i)
            return total
        except Exception as e:
            _log.error("添加文档失败: %s", e)
            return 0

    def search(self, query, top_k=None, threshold=None):
        if not self._ok or not self._collection or not self._embedder: return []
        try:
            top_k = top_k or RAG_TOP_K
            threshold = threshold or RAG_SIMILARITY_THRESHOLD
            qe = self._embedder.encode([query]).tolist()
            results = self._collection.query(query_embeddings=qe, n_results=top_k,
                                              include=["documents","metadatas","distances"])
            if not results["ids"] or not results["ids"][0]: return []
            docs = []
            for i, did in enumerate(results["ids"][0]):
                dist = results["distances"][0][i]; sim = 1.0 - dist
                if sim >= threshold:
                    docs.append({"id":did, "content":results["documents"][0][i],
                                 "score":round(sim,4),
                                 "metadata":results["metadatas"][0][i] if results["metadatas"] else {}})
            return docs
        except Exception as e:
            _log.error("搜索失败: %s", e)
            return []

    def count(self):
        if not self._ok or not self._collection: return 0
        try: return self._collection.count()
        except: return 0

    def delete_all(self):
        if not self._ok: return
        try:
            with self._write_lock:
                self._client.delete_collection(self.collection_name)
                self._collection = self._client.get_or_create_collection(
                    name=self.collection_name, metadata={"hnsw:space":"cosine"})
        except Exception as e:
            _log.error("清空失败: %s", e)

    def get_stats(self):
        return {"collection_name":self.collection_name, "document_count":self.count(),
                "embedding_backend":self._embedder._backend if self._embedder else "N/A",
                "persist_dir":self.persist_dir, "ok":self._ok}


# 全局单例
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """获取向量存储单例"""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
