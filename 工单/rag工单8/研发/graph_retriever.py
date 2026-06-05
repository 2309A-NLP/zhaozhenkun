"""
graph_retriever.py - RAG工单8 混合检索（向量+图谱）模块
工单编号: 人工智能NLP-RAG-基于Graph RAG 实现金融问答
功能: 使用DeepSeek从查询中提取金融实体，通过知识图谱
      扩展关联文档，与向量检索结果融合排序返回
"""

import logging, json, re, time
from collections import defaultdict
from config import MIMO_API_KEY, MIMO_BASE_URL, MIMO_ENTITY_MODEL, \
    TOP_K, GRAPH_EXPAND_K, FINAL_TOP_K, OUTPUT_DIR, LOG_FMT, LOG_DATEFMT

logging.basicConfig(format=LOG_FMT, datefmt=LOG_DATEFMT, level=logging.INFO)
logger = logging.getLogger("graph_retriever")

# DeepSeek实体提取缓存
_query_cache = {}


def extract_query_entities(query):
    """
    从用户查询中提取金融实体名称
    Args:
        query: 用户问题字符串
    Returns:
        list: 实体名称列表
    """
    if query in _query_cache:
        return _query_cache[query]
    prompt = f"""从以下金融问答问题中提取核心实体名称(公司名、人名、产品名、指标名)。
返回JSON格式: {{"entities": ["实体1", "实体2", ...]}}
只返回实体名，不要解释。

问题: {query}"""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=MIMO_API_KEY, base_url=MIMO_BASE_URL)
        resp = client.chat.completions.create(
            model=MIMO_ENTITY_MODEL, messages=[{"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=200)
        msg = resp.choices[0].message
        result = (msg.content or msg.reasoning_content or "").strip()
        if '{' in result:
            try:
                result = result[result.index('{'):result.rindex('}') + 1]
                data = json.loads(result)
                entities = data.get("entities", [])
            except Exception:
                entities = []
        else:
            entities = []
    except Exception as e:
        logger.warning(f"查询实体提取失败: {e}")
        entities = []
    _query_cache[query] = entities
    return entities


class GraphRetriever:
    """向量+图谱混合检索器"""

    def __init__(self, graph_builder=None):
        self.graph_builder = graph_builder
        self.chunk_store = []  # 所有chunks引用
        self._milvus_mgr = None

    def set_chunks(self, chunks):
        """设置chunk存储"""
        self.chunk_store = chunks if chunks else []

    def _get_milvus_manager(self):
        """延迟获取Milvus管理器"""
        if self._milvus_mgr is None:
            from milvus_handler import MilvusManager
            self._milvus_mgr = MilvusManager()
            self._milvus_mgr.connect()
        return self._milvus_mgr

    def retrieve_vector_only(self, query_vector, top_k=TOP_K):
        """
        纯向量检索（作为baseline对比）
        Args:
            query_vector: 查询向量
            top_k: 返回条数
        Returns:
            list: [{"text", "score", "source_pdf", "page_num"}]
        """
        from pymilvus import Collection
        mgr = self._get_milvus_manager()
        col = Collection(mgr.collection_name)
        col.load()
        qv = [query_vector.tolist()] if hasattr(query_vector, 'tolist') else [query_vector]
        results = col.search(
            data=qv, anns_field="embedding",
            param={"metric_type": "IP", "params": {"nprobe": 10}},
            limit=top_k, output_fields=["text", "source_pdf", "page_num"],
        )
        items = []
        for hits_row in results:
            for hit in hits_row:
                items.append({
                    "text": hit.entity.get("text", ""),
                    "score": hit.score,
                    "source_pdf": hit.entity.get("source_pdf", ""),
                    "page_num": hit.entity.get("page_num", 0),
                })
        return items

    def _get_chunks_by_entities(self, entities, expand_k=GRAPH_EXPAND_K):
        """
        通过实体查询获取图谱扩展的chunks
        先找实体直接关联的chunk，再通过图谱扩展找更多chunk
        """
        if not self.graph_builder or not self.graph_builder._built:
            return []
        chunk_indices = set()
        for entity in entities:
            # 直接关联的chunk
            if entity in self.graph_builder.entity_to_chunks:
                chunk_indices.update(self.graph_builder.entity_to_chunks[entity])
            # BFS扩展关联实体
            related = self.graph_builder.get_related_entities(entity, max_hops=2)
            for rel_entity in related[1:]:  # 跳过自身
                if rel_entity in self.graph_builder.entity_to_chunks:
                    chunk_indices.update(self.graph_builder.entity_to_chunks[rel_entity])
        # 限制扩展数量
        chunk_indices = list(chunk_indices)[:expand_k * 3]
        # 从chunk_store中查找
        store_map = {c["index"]: c for c in self.chunk_store}
        chunks = [store_map[idx] for idx in chunk_indices if idx in store_map]
        return chunks

    def retrieve(self, query_vector, query_text, use_graph=True, top_k=TOP_K):
        """
        混合检索：向量检索 + 图谱扩展
        Args:
            query_vector: 查询向量
            query_text: 查询文本（用于实体提取）
            use_graph: 是否启用图谱扩展
            top_k: Top-K数量
        Returns:
            list: [{"text", "score", "source_pdf", "page_num", "source"}]
        """
        # 1. 纯向量检索
        vector_hits = self.retrieve_vector_only(query_vector, top_k)
        retrieved = []
        seen_texts = set()
        for hit in vector_hits:
            if hit["text"] not in seen_texts:
                retrieved.append({**hit, "source": "vector"})
                seen_texts.add(hit["text"])

        # 2. 图谱扩展
        if use_graph and self.graph_builder and self.graph_builder._built:
            entities = extract_query_entities(query_text)
            if entities:
                logger.info(f"查询实体: {entities}")
                graph_chunks = self._get_chunks_by_entities(entities)
                for chunk in graph_chunks:
                    if chunk["content"] not in seen_texts:
                        retrieved.append({
                            "text": chunk["content"],
                            "score": 0.5,  # 图谱匹配基础分
                            "source_pdf": chunk.get("source_pdf", ""),
                            "page_num": chunk.get("page_num", 0),
                            "source": "graph",
                        })
                        seen_texts.add(chunk["content"])

        # 3. 排序取Top
        retrieved.sort(key=lambda x: x.get("score", 0), reverse=True)
        return retrieved[:FINAL_TOP_K]

    def close(self):
        """释放Milvus连接"""
        if self._milvus_mgr:
            try:
                self._milvus_mgr.close()
            except Exception:
                pass


if __name__ == "__main__":
    """单独测试检索功能"""
    from embedder import BgeM3Embedder
    embedder = BgeM3Embedder()
    q_vec = embedder.encode_query("平安银行2019年盈利增长因素")["dense_vecs"][0]
    retriever = GraphRetriever()
    results = retriever.retrieve(q_vec, "平安银行2019年盈利增长因素", use_graph=False)
    print(f"纯向量检索结果: {len(results)}条")
    for r in results[:3]:
        print(f"  score={r['score']:.4f} | {r['text'][:60]}...")
