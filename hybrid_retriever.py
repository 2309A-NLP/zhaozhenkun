# -*- coding: utf-8 -*-
# 设置文件编码为UTF-8，以支持中文处理

import numpy as np  # 导入numpy库，用于高效的数值计算（如数组排序）
from typing import List, Dict  # 导入类型提示工具，用于指定函数参数和返回值的类型
from sklearn.feature_extraction.text import TfidfVectorizer  # 导入TF-IDF向量化器，用于将文本转换为TF-IDF特征矩阵
from sklearn.metrics.pairwise import cosine_similarity  # 导入余弦相似度计算函数，用于计算查询与文档的相似度
from utils import tokenize_text, generate_doc_id  # 从自定义工具模块中导入分词函数和文档ID生成函数

try:
    from rank_bm25 import BM25Okapi  # 尝试导入BM25算法实现（用于关键词检索）
except Exception:
    BM25Okapi = None  # 如果导入失败（例如未安装该库），则将BM25Okapi设为None，程序仍可运行其他部分


class HybridRetriever:
    """混合检索器 - 结合BM25、TF-IDF和倒排融合算法"""
    # 定义一个混合检索器类，融合多种检索方法并采用RRF算法融合结果

    def __init__(self):
        # 构造方法，初始化检索器的各项属性
        self.stopwords = {"的", "了", "和", "是", "在", "就", "都", "也", "很", "吗", "呢", "啊", "吧",
                          "我", "你", "他", "她", "它", "有", "与", "及", "要", "去", "还", "让", "被",
                          "把", "这", "那", "一个"}
        # 定义停用词集合，这些词在分词后会被过滤掉，因为它们通常不携带重要语义

        self.documents_metadata = []  # 存储文档元数据的列表（每个元素是一个字典，包含问题、答案、来源等）
        self.bm25_index = None  # 存放BM25索引对象，初始为None
        self.tfidf_vectorizer = None  # 存放TF-IDF向量化器对象，初始为None
        self.tfidf_matrix = None  # 存放TF-IDF特征矩阵，每一行对应一个文档
        self.weighted_corpus = []  # 存放加权后的语料文本（问题重复三次+答案），用于构建索引

    def _filter_tokens(self, text: str) -> List[str]:
        # 私有方法：对文本进行分词并过滤停用词及空字符串
        tokens = tokenize_text(text)  # 调用外部工具函数进行分词
        return [t for t in tokens if t not in self.stopwords and len(t.strip()) > 0]
        # 过滤掉停用词和空白词后返回有效词元列表

    def build_index(self, documents: List[Dict]) -> None:
        # 构建索引的方法，接收文档列表（每个文档是一个字典）
        self.documents_metadata = documents[:]  # 复制文档元数据，避免后续修改影响原始数据

        # 构建加权语料：将每个文档的问题重复3次（强化问题重要性）后拼接答案，然后去除首尾空白
        self.weighted_corpus = [
            (((doc.get("question", "") + " ") * 3) + doc.get("answer", "")).strip()
            for doc in documents
        ]

        # 如果BM25可用且加权语料非空，则构建BM25索引
        if BM25Okapi is not None and self.weighted_corpus:
            self.bm25_index = BM25Okapi([self._filter_tokens(text) for text in self.weighted_corpus])
            # 对加权语料中每个文本进行分词过滤，并用得到的词元列表初始化BM25索引

        # 构建TF-IDF索引
        if self.weighted_corpus:
            self.tfidf_vectorizer = TfidfVectorizer(
                tokenizer=self._filter_tokens,  # 使用自定义的分词+停用词过滤函数作为分词器
                lowercase=False,                # 不转换为小写（保留原样，因为中文不存在大小写问题）
                min_df=1,                       # 忽略出现次数小于1的词汇（即保留所有至少出现一次的词）
                max_df=0.95                     # 忽略在95%以上文档中都出现的词（过于常见的词）
            )
            self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(self.weighted_corpus)
            # 对加权语料进行拟合和转换，生成TF-IDF特征矩阵

    def bm25_search(self, query: str, top_k: int = 10) -> List[Dict]:
        # BM25检索方法，接收查询字符串和返回前top_k个结果
        if not self.bm25_index:  # 如果BM25索引不存在，直接返回空列表
            return []
        tokens = self._filter_tokens(query)  # 对查询进行分词并过滤停用词
        if not tokens:  # 如果分词后为空，则无法检索，返回空列表
            return []
        scores = self.bm25_index.get_scores(tokens)  # 使用BM25模型获取每个文档与查询的相关性得分
        results = []  # 初始化结果列表
        # 按得分降序排序，取前top_k个文档的索引
        for idx in np.argsort(scores)[::-1][:top_k]:
            if scores[idx] > 0:  # 只保留得分大于0的结果（有一定相关性）
                results.append({
                    **self.documents_metadata[idx],  # 摊开原始文档元数据
                    "bm25_score": float(scores[idx]),  # 添加BM25得分
                    "retrieval_method": "bm25"        # 标注检索方法
                })
        return results  # 返回结果列表

    def tfidf_search(self, query: str, top_k: int = 10) -> List[Dict]:
        # TF-IDF检索方法，接收查询字符串和返回前top_k个结果
        if self.tfidf_matrix is None or self.tfidf_vectorizer is None:
            return []  # 如果TF-IDF矩阵或向量化器未构建，则返回空列表
        # 将查询转换为TF-IDF向量，并计算与所有文档向量的余弦相似度
        scores = cosine_similarity(self.tfidf_vectorizer.transform([query]), self.tfidf_matrix)[0]
        results = []  # 初始化结果列表
        # 按相似度降序排序，取前top_k个文档的索引
        for idx in np.argsort(scores)[::-1][:top_k]:
            if scores[idx] > 0.03:  # 仅保留相似度大于0.03的结果（过滤低相关结果）
                results.append({
                    **self.documents_metadata[idx],  # 摊开原始文档元数据
                    "tfidf_score": float(scores[idx]),  # 添加TF-IDF相似度得分
                    "retrieval_method": "tfidf"         # 标注检索方法
                })
        return results  # 返回结果列表

    def reciprocal_rank_fusion(self, result_groups: Dict[str, List[Dict]], k: int = 60) -> List[Dict]:
        """
        倒数排名融合（RRF）方法，将多个检索结果列表融合为单一排序列表
        :param result_groups: 字典，键为检索方法名，值为对应的结果列表
        :param k: RRF算法中的常数，用于平滑排名倒数的权重（通常取60）
        :return: 融合后的排序结果列表
        """
        merged = {}  # 字典，用于根据文档唯一标识暂存融合得分和文档信息
        for method, docs in result_groups.items():  # 遍历每种检索方法及其结果列表
            for rank, doc in enumerate(docs):  # 遍历当前方法结果中的每个文档（rank从0开始）
                # 生成或获取文档的唯一标识（优先使用doc_id，否则基于内容生成）
                identity = doc.get("doc_id") or generate_doc_id(
                    doc.get("question", ""), doc.get("answer", ""), doc.get("source", "")
                )
                # 计算该文档在当前方法中的RRF得分：1/(k + rank + 1)  （rank+1是为了排名从1开始）
                score = 1.0 / (k + rank + 1)
                if identity not in merged:  # 如果该文档尚未在融合字典中记录过
                    merged[identity] = {"score": 0.0, "doc": dict(doc)}  # 初始化得分和文档副本
                merged[identity]["score"] += score  # 累加当前方法下的RRF得分
                # 记录该文档在当前检索方法下的排名（1-based）
                merged[identity]["doc"][f"{method}_rank"] = rank + 1

        fused = []  # 初始化最终融合结果列表
        # 按融合总得分降序排序，并构造最终结果
        for _, payload in sorted(merged.items(), key=lambda x: x[1]["score"], reverse=True):
            payload["doc"]["fusion_score"] = payload["score"]  # 添加融合得分字段
            payload["doc"]["retrieval_method"] = "rrf"        # 标注融合方法
            fused.append(payload["doc"])  # 将文档加入结果列表
        return fused  # 返回融合后的排序结果