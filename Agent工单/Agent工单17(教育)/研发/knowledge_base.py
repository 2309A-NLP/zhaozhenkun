import hashlib
import json
import os
import uuid
from typing import Dict, List, Optional

import numpy as np

try:
    import faiss
except ImportError:
    faiss = None

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from config import get_data_dirs, get_settings


class InMemoryIndex:
    def __init__(self, dimension: int):
        self.dimension = dimension
        self._vectors = np.empty((0, dimension), dtype=np.float32)

    @property
    def ntotal(self) -> int:
        return int(self._vectors.shape[0])

    def add(self, vector: np.ndarray) -> None:
        vector = np.asarray(vector, dtype=np.float32)
        if vector.ndim == 1:
            vector = vector.reshape(1, -1)
        self._vectors = np.vstack([self._vectors, vector])

    def search(self, query_vector: np.ndarray, top_k: int):
        query_vector = np.asarray(query_vector, dtype=np.float32)
        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)
        if self.ntotal == 0:
            return np.empty((1, 0), dtype=np.float32), np.empty((1, 0), dtype=np.int64)
        distances = np.sum((self._vectors - query_vector[0]) ** 2, axis=1)
        order = np.argsort(distances)[:top_k]
        return distances[order].reshape(1, -1).astype(np.float32), order.reshape(1, -1).astype(np.int64)

    def reconstruct(self, index: int):
        return self._vectors[index]

    def reset(self) -> None:
        self._vectors = np.empty((0, self.dimension), dtype=np.float32)


class KnowledgeBaseService:
    def __init__(self):
        self.settings = get_settings()
        get_data_dirs()
        self.client = None
        if OpenAI and self.settings.QWEN_API_KEY:
            self.client = OpenAI(
                api_key=self.settings.QWEN_API_KEY,
                base_url=self.settings.QWEN_BASE_URL,
                timeout=10.0,
            )
        self.embedding_model = "text-embedding-v3"
        self.dimension = self.settings.EMBEDDING_DIMENSION
        self.index_path = os.path.join(self.settings.FAISS_INDEX_PATH, "knowledge_index.faiss")
        self.metadata_path = os.path.join(self.settings.FAISS_INDEX_PATH, "metadata.json")
        self.index = None
        self.metadata = []
        self._load_or_create_index()

    def _new_index(self):
        return faiss.IndexFlatL2(self.dimension) if faiss else InMemoryIndex(self.dimension)

    def _load_or_create_index(self) -> None:
        if faiss and os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
            try:
                self.index = faiss.read_index(self.index_path)
                with open(self.metadata_path, "r", encoding="utf-8") as file:
                    self.metadata = json.load(file)
                print(f"知识库已加载：{self.index.ntotal} 条记录")
                return
            except Exception as error:
                print(f"知识库加载失败：{error}")
                print("将删除旧索引文件并重建...")
                for path in [self.index_path, self.metadata_path]:
                    try:
                        os.remove(path)
                    except OSError:
                        pass
        try:
            self.index = self._new_index()
        except Exception as error:
            print(f"FAISS索引创建失败：{error}")
            print("降级使用内存索引（InMemoryIndex），数据不会持久化到磁盘")
            self.index = InMemoryIndex(self.dimension)
        self.metadata = []
        self._save_index()
        print("知识库已初始化（空）")

    def _save_index(self) -> None:
        if faiss and not isinstance(self.index, InMemoryIndex):
            try:
                faiss.write_index(self.index, self.index_path)
            except Exception as error:
                print(f"FAISS索引写入失败：{error}")
                print("索引将仅保存在内存中，重启后需重建知识库")
        with open(self.metadata_path, "w", encoding="utf-8") as file:
            json.dump(self.metadata, file, ensure_ascii=False, indent=2)

    def _get_embedding(self, text: str) -> List[float]:
        if self.client is None:
            return self._mock_embedding(text)
        try:
            response = self.client.embeddings.create(model=self.embedding_model, input=text[:8000])
            return response.data[0].embedding
        except Exception as error:
            print(f"嵌入API调用失败({self.embedding_model})：{error}，使用本地模拟嵌入")
            return self._mock_embedding(text)

    def _mock_embedding(self, text: str) -> List[float]:
        seed = int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big") % (2 ** 31)
        np.random.seed(seed)
        vector = np.random.randn(self.dimension).astype(np.float32)
        vector = vector / np.linalg.norm(vector)
        return vector.tolist()

    def _split_text(self, text: str) -> List[str]:
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + self.settings.CHUNK_SIZE, len(text))
            chunks.append(text[start:end])
            start += self.settings.CHUNK_SIZE - self.settings.CHUNK_OVERLAP
        return chunks

    def add_document(self, title: str, content: str, resource_type: str,
                     tags: Optional[List[str]] = None, source_url: Optional[str] = None) -> str:
        resource_id = str(uuid.uuid4())
        for index, chunk in enumerate(self._split_text(content)):
            if len(chunk.strip()) < 10:
                continue
            self.index.add(np.array([self._get_embedding(chunk)], dtype=np.float32))
            self.metadata.append({
                "resource_id": resource_id,
                "title": title,
                "chunk_index": index,
                "content": chunk,
                "resource_type": resource_type,
                "tags": tags or [],
                "source_url": source_url or "",
            })
        self._save_index()
        return resource_id

    def search(self, query: str, top_k: int = 5,
               resource_types: Optional[List[str]] = None) -> List[Dict]:
        if self.index.ntotal == 0:
            return []
        query_vector = np.array([self._get_embedding(query)], dtype=np.float32)
        search_k = min(top_k * 3, self.index.ntotal) if resource_types else min(top_k, self.index.ntotal)
        distances, indices = self.index.search(query_vector, search_k)
        results = []
        for distance, index in zip(distances[0], indices[0]):
            if index < 0 or index >= len(self.metadata):
                continue
            meta = self.metadata[index]
            if resource_types and meta["resource_type"] not in resource_types:
                continue
            results.append({
                "resource_id": meta["resource_id"],
                "title": meta["title"],
                "content": meta["content"],
                "resource_type": meta["resource_type"],
                "relevance_score": round(1.0 / (1.0 + float(distance)), 4),
                "source_url": meta.get("source_url", ""),
                "tags": meta.get("tags", []),
            })
            if len(results) >= top_k:
                break
        return results

    def get_rag_context(self, query: str, top_k: int = 3) -> str:
        results = self.search(query, top_k=top_k)
        if not results:
            return ""
        context = "\n\n".join(
            f"【参考资料{i + 1}】标题：{item['title']}\n{item['content']}"
            for i, item in enumerate(results)
        )
        return f"\n\n--- 以下为知识库检索的参考资料 ---\n{context}\n--- 参考资料结束 ---\n"

    def delete_resource(self, resource_id: str) -> bool:
        keep_pairs = [
            (index, meta) for index, meta in enumerate(self.metadata)
            if meta["resource_id"] != resource_id
        ]
        if len(keep_pairs) == len(self.metadata):
            return False
        remaining_vectors = [self.index.reconstruct(index) for index, _ in keep_pairs]
        self.index.reset()
        if remaining_vectors:
            self.index.add(np.array(remaining_vectors, dtype=np.float32))
        self.metadata = [meta for _, meta in keep_pairs]
        self._save_index()
        return True

    def get_statistics(self) -> Dict:
        resource_ids = {meta["resource_id"] for meta in self.metadata}
        return {
            "total_vectors": self.index.ntotal,
            "total_documents": len(resource_ids),
            "total_chunks": len(self.metadata),
            "vector_dimension": self.dimension,
        }

    def init_demo_knowledge(self) -> None:
        if self.index.ntotal > 0:
            return
        demo_docs = [
            {
                "title": "Python程序设计基础-第3章 函数与模块",
                "content": "函数是组织好的、可重复使用的代码块。在Python中定义函数使用def关键字。函数可以接收参数并通过return语句返回值。模块是包含函数和变量的Python文件。使用import语句可以导入模块。常用的内置模块有math、random、datetime等。教学重点：理解函数的定义与调用，掌握参数传递方式。教学难点：作用域和闭包概念。",
                "type": "textbook",
            },
            {
                "title": "机器学习导论-第5章 决策树与随机森林",
                "content": "决策树是一种基本的分类与回归方法。它基于特征对实例进行分类的过程。信息增益是决策树特征选择的重要指标。随机森林通过集成多个决策树来提高性能。随机森林使用Bagging集成学习方式，随机选择样本和特征来构建每棵树。教学重点：理解决策树的分裂准则。教学难点：过拟合与剪枝策略。",
                "type": "textbook",
            },
            {
                "title": "深度学习-第7章 卷积神经网络CNN",
                "content": "卷积神经网络(CNN)是深度学习中最具代表性的网络结构之一。CNN的核心组件包括卷积层(Convolution)、池化层(Pooling)和全连接层。卷积操作通过滤波器在输入数据上滑动来提取特征。池化用于降低特征维度。经典CNN架构包括LeNet-5、AlexNet、VGGNet、ResNet等。教学重点：理解卷积运算原理。教学难点：反向传播在CNN中的实现。",
                "type": "textbook",
            },
            {
                "title": "人工智能导论-第1章 人工智能概述",
                "content": "人工智能(Artificial Intelligence)是计算机科学的重要分支。AI研究如何使计算机模拟人类智能行为，包括学习、推理、感知和决策。人工智能的发展经历了三次浪潮：推理期(1956-1970)、知识期(1970-1990)、学习期(1990至今)。机器学习是AI的核心，包括监督学习、无监督学习和强化学习三大范式。教学重点：理解AI的定义与发展历程。教学难点：强AI与弱AI的哲学思辨。",
                "type": "textbook",
            },
        ]
        for doc in demo_docs:
            self.add_document(doc["title"], doc["content"], doc["type"], tags=["人工智能", "计算机"])
        print(f"演示知识库已初始化，共加载 {len(demo_docs)} 份文档")


knowledge_base_service = KnowledgeBaseService()
