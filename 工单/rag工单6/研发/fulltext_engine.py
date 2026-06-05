"""
fulltext_engine.py - RAG工单6 全文检索引擎模块
需求: 全文检索 — BM25关键词匹配
功能: 基于倒排索引+BM25算法的全文检索：中文滑动窗口分词、TF-IDF加权、分数排序
"""

import logging, json, os, math, re
from collections import defaultdict

# 导入配置
from config import FULLTEXT_TOP_K, OUTPUT_DIR, LOG_FMT, LOG_DATEFMT

# 设置日志
logging.basicConfig(format=LOG_FMT, datefmt=LOG_DATEFMT, level=logging.INFO)
logger = logging.getLogger("fulltext_engine")


class FullTextEngine:
    """
    全文检索引擎（BM25算法）
    基于倒排索引实现关键词检索，支持多字段匹配
    """
    def __init__(self):
        """初始化全文检索引擎"""
        self.chunks = []           # 所有文本块
        self.inverted_index = {}   # 倒排索引 {词: [块索引, ...]}
        self.doc_lengths = []      # 每块的长度（词数）
        self.avg_doc_length = 0    # 平均块长度
        self.total_docs = 0        # 总文档数
        self._built = False        # 索引是否已构建

    def build(self, chunks):
        """
        构建BM25索引
        参数:
            chunks: text_chunker生成的文本块列表
        """
        logger.info("构建BM25全文索引...")
        self.chunks = chunks
        self.total_docs = len(chunks)

        # 构建倒排索引 {词: {块索引: 词频}}
        term_freq = defaultdict(lambda: defaultdict(int))
        self.doc_lengths = []

        for chunk in chunks:
            text = chunk["content"]
            idx = chunk["index"]

            # 提取所有词（使用_tokenize方法）
            words = self._tokenize(text)
            self.doc_lengths.append(len(words))

            # 统计每个词在当前块中的出现次数
            for word in words:
                word = word.lower()
                term_freq[word][idx] += 1

        # 计算平均块长度
        self.avg_doc_length = sum(self.doc_lengths) / max(self.total_docs, 1)

        # 将词频转换为倒排索引格式 {词: [块索引1, ...]}
        self.inverted_index = {}
        for word, doc_dict in term_freq.items():
            self.inverted_index[word] = list(doc_dict.keys())

        self._built = True
        logger.info(f"BM25索引构建完成! {len(self.inverted_index)}个词, {self.total_docs}个文档")

    def _tokenize(self, text):
        """
        将文本分词，支持中文分词（2-4字滑动窗口）
        返回小写词列表
        """
        words = []
        # 提取英文词
        for w in re.findall(r'[a-zA-Z]{2,}', text):
            words.append(w.lower())
        # 提取中文词（滑动窗口2-4字）
        chinese_chars = re.findall(r'[\u4e00-\u9fff]+', text)
        for chunk in chinese_chars:
            if len(chunk) <= 4:
                words.append(chunk)
            else:
                # 对长中文串使用滑动窗口
                for length in [4, 3, 2]:
                    for i in range(len(chunk) - length + 1):
                        words.append(chunk[i:i+length])
                    if len(chunk) <= 4:
                        break
        return list(set(words))  # 去重

    def _bm25_score(self, query_words, doc_idx, k1=1.5, b=0.75):
        """
        计算BM25相关性分数
        参数:
            query_words: 查询词列表
            doc_idx: 文档索引
            k1, b: BM25参数
        返回:
            float: BM25分数
        """
        score = 0.0
        doc_len = self.doc_lengths[doc_idx]

        for word in query_words:
            # 如果词不在倒排索引中，跳过
            if word not in self.inverted_index:
                continue

            # 包含该词的文档数
            df = len(self.inverted_index[word])
            if df == 0:
                continue

            # IDF（逆文档频率）
            idf = math.log((self.total_docs - df + 0.5) / (df + 0.5) + 1.0)

            # 计算词在文档中的频率
            tf = 0
            text = self.chunks[doc_idx]["content"].lower()
            tf = len(re.findall(re.escape(word), text))

            # BM25公式
            score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / self.avg_doc_length))

        return score

    def search(self, query, top_k=None):
        """
        全文检索（BM25算法）
        参数:
            query: 查询文本
            top_k: 返回最多的结果数
        返回:
            list: [{content, page_num, source_pdf, bm25_score}, ...]
        """
        if not self._built:
            logger.error("索引未构建，请先调用build()")
            return []

        top_k = top_k or FULLTEXT_TOP_K
        query_words = self._tokenize(query)

        if not query_words:
            logger.warning("查询词为空")
            return []

        # 找出包含至少一个查询词的候选文档
        candidate_docs = set()
        for word in query_words:
            if word in self.inverted_index:
                candidate_docs.update(self.inverted_index[word])

        # 计算每个候选文档的BM25分数
        scores = []
        for doc_idx in candidate_docs:
            score = self._bm25_score(query_words, doc_idx)
            if score > 0:
                chunk = self.chunks[doc_idx]
                scores.append({
                    "content": chunk["content"],
                    "page_num": chunk["page_num"],
                    "source_pdf": chunk["source_pdf"],
                    "chunk_index": chunk["index"],
                    "bm25_score": round(score, 4),
                })

        # 按BM25分数降序排列
        scores.sort(key=lambda x: x["bm25_score"], reverse=True)
        result = scores[:top_k]

        logger.info(f"全文检索完成! 找到{len(result)}条结果")
        return result

    def save_index(self):
        """保存索引到文件"""
        path = os.path.join(OUTPUT_DIR, "fulltext_index.json")
        data = {
            "total_docs": self.total_docs,
            "avg_doc_length": self.avg_doc_length,
            "inverted_index_size": len(self.inverted_index),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"全索引信息已保存: {path}")


if __name__ == "__main__":
    """单独测试全文检索"""
    engine = FullTextEngine()
    test_chunks = [
        {"content": "武汉兴图新科注册资本为5,520万元", "index": 0, "page_num": 52, "source_pdf": "1.pdf"},
        {"content": "武汉力源信息发行股数1,670万股", "index": 1, "page_num": 24, "source_pdf": "2.pdf"},
    ]
    engine.build(test_chunks)
    results = engine.search("注册资本")
    for r in results:
        print(f"BM25: {r['bm25_score']} | {r['content'][:40]}")
