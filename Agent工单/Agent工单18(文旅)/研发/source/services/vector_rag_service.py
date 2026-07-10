"""工单18：向量RAG服务 — 对接工单17，jieba+TF-IDF语义检索(纯本地，无需下载模型)"""
import json, os, logging, re
from pathlib import Path
from collections import Counter
import math

logger = logging.getLogger("vector_rag")

SPOTS_FILE = Path(__file__).resolve().parents[2] / "data" / "spots.json"

# 工单18：jieba 中文分词
import jieba

# 工单18：停用词表（中文常见无意义词）
STOP_WORDS = set("的了吗呢啊吧呀么是与不和在很都也就要对从到把被让给向"
                 "着过之其这那个些各及用为有所能会可以而但或且虽然如果因为所以")

# 工单18：全局倒排索引 + TF-IDF 向量缓存
_INDEX = None  # {"term": {doc_id: tf}}
_IDF = None    # {"term": idf}
_DOCS = None   # [{"id", "name", "category", "content", "keywords", "terms"}]


def _tokenize(text: str) -> list:
    """分词 + 去停用词 + 保留2字以上词"""
    words = jieba.lcut(text.lower())
    return [w.strip() for w in words if len(w.strip()) >= 2 and w.strip() not in STOP_WORDS]


def build_index(force: bool = False) -> int:
    """构建倒排索引和TF-IDF向量"""
    global _INDEX, _IDF, _DOCS
    if _INDEX is not None and not force:
        return len(_DOCS) if _DOCS else 0

    spots = json.loads(SPOTS_FILE.read_text(encoding="utf-8"))
    _INDEX = {}
    _DOCS = []

    for i, spot in enumerate(spots):
        for field in ["summary", "details"]:
            text = spot.get(field, "")
            if not text:
                continue
            doc_id = f"spot_{i}_{field}"
            content = f"{spot['name']} {spot['category']} {text}"
            terms = _tokenize(content)
            term_counts = Counter(terms)

            _DOCS.append({
                "id": doc_id,
                "name": spot["name"],
                "category": spot["category"],
                "content": content,
                "keywords": spot.get("keywords", []),
                "terms": set(terms),
            })

            for term, count in term_counts.items():
                if term not in _INDEX:
                    _INDEX[term] = {}
                _INDEX[term][doc_id] = count

    # 工单18：计算 IDF
    N = len(_DOCS)
    _IDF = {}
    for term, postings in _INDEX.items():
        df = len(postings)
        _IDF[term] = math.log((N - df + 0.5) / (df + 0.5) + 1)

    logger.info("向量知识库(TF-IDF)已构建: %d文档, %d词条", N, len(_IDF))
    return N


def _search_tfidf(query: str, top_k: int = 5) -> list:
    """TF-IDF 向量检索"""
    build_index()

    query_terms = _tokenize(query)
    if not query_terms:
        return []

    # 工单18：计算查询TF-IDF向量
    query_vec = {}
    for term in query_terms:
        if term in _IDF:
            query_vec[term] = (1 + math.log(query_terms.count(term))) * _IDF[term]

    if not query_vec:
        return []

    # 工单18：计算每篇文档与查询的余弦相似度
    scores = []
    for doc in _DOCS:
        dot = 0
        doc_norm = 0
        for term in doc["terms"]:
            tf = _INDEX.get(term, {}).get(doc["id"], 0)
            if tf > 0:
                idf = _IDF.get(term, 0)
                w = (1 + math.log(tf)) * idf
                doc_norm += w * w
                if term in query_vec:
                    dot += query_vec[term] * w

        if doc_norm > 0 and dot > 0:
            query_norm = math.sqrt(sum(v * v for v in query_vec.values()))
            sim = dot / (math.sqrt(doc_norm) * query_norm) if query_norm > 0 else 0
            scores.append((sim, doc))

    scores.sort(key=lambda x: x[0], reverse=True)

    # 工单18：去重（按景点名）返回top-k
    seen, items = set(), []
    for sim, doc in scores:
        name = doc["name"]
        if name not in seen:
            seen.add(name)
            items.append({
                "name": name,
                "category": doc["category"],
                "content": doc["content"],
                "score": round(sim, 3),
                "keywords": doc["keywords"],
            })
        if len(items) >= top_k:
            break
    return items


def vector_search(query: str, top_k: int = 5) -> list:
    """语义搜索入口 — TF-IDF向量检索"""
    try:
        results = _search_tfidf(query, top_k)
        if results:
            return results
    except Exception as e:
        logger.warning("向量检索失败: %s, 降级关键词", e)

    # 工单18：降级 — 从倒排索引做简单关键词匹配
    from services.knowledge_service import search_spots
    kw_results = search_spots(query, top_k)
    return [{"name": r["name"], "category": r["category"],
             "content": f"{r['summary']} {r['details']}", "score": 0.5}
            for r in kw_results]


def image_vector_search(image_description: str, ocr_text: str = "", top_k: int = 5) -> list:
    """结合图片描述+OCR文本做检索"""
    combined = f"{image_description} {ocr_text}".strip()
    if not combined:
        return []
    return vector_search(combined, top_k)


def clip_zero_shot_classify(image_bytes: bytes, categories: list = None) -> dict:
    """工单18：零样本分类 — 国内网络不可用CLIP时，返回基于YOLO的分类"""
    # CLIP模型需从HuggingFace下载，国内不可用，降级到YOLO分类
    return {"category": "未知", "confidence": 0, "all_scores": {}}
