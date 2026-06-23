"""
query_enhancer.py - RAG工单13 查询处理与增强模块
需求: 工单要求分析"查询处理与增强"阶段的运行时间 — 对用户Query进行预处理/扩展
功能: 1.Query清洗(去冗余词) 2.关键词提取 3.Query扩展(同义改写) 4.全程计时
"""
import logging
import re
import time

logger = logging.getLogger(__name__)


# 中文停用词/冗余词（口语化表达）
_REDUNDANT_PATTERNS = [
    r"请问一下[，,]?\s*",
    r"我想问[一下]?[，,]?\s*",
    r"帮我看看[，,]?\s*",
    r"能不能[，,]?\s*",
    r"可以[，,]?\s*",
    r"那个[，,]?\s*",
    r"就是说[，,]?\s*",
    r"请告诉我[，,]?\s*",
    r"麻烦[你您][，,]?\s*",
]


def clean_query(query: str) -> str:
    """需求：查询清洗——去冗余口语化表达，保留核心问题"""
    cleaned = query.strip()
    for pattern in _REDUNDANT_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    # 去多余空格
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def extract_keywords(query: str, top_n: int = 5) -> list:
    """需求：关键词提取——从Query中提取关键主题词"""
    # 简单实现：按常见分隔符提取长词
    words = re.split(r"[，,。！？\s、；：\"\"''（）()\[\]【】]", query)
    # 过滤短词和纯标点
    keywords = []
    for w in words:
        w = w.strip()
        if len(w) >= 2 and not re.match(r"^[的了是这在就和都也还很把被让要去让与及吗呢啊吧哦嗯]+$", w):
            keywords.append(w)
    # 按长度降序（长词通常更有信息量）
    keywords.sort(key=len, reverse=True)
    return keywords[:top_n]


def enhance_query(query: str) -> dict:
    """
    需求：查询处理与增强阶段 — 完整处理流程（带计时）
    返回: {cleaned_query, keywords, original_query, processing_time}
    """
    t0 = time.time()

    # Step 1: 清洗
    cleaned = clean_query(query)

    # Step 2: 提取关键词
    keywords = extract_keywords(cleaned)

    # Step 3: 判断是否需要扩展（短问题可能缺少上下文）
    needs_expansion = len(cleaned) < 10
    expanded_query = cleaned
    if needs_expansion and keywords:
        # 简单扩展：用关键词补充上下文
        expanded_query = f"{cleaned}（相关主题：{'、'.join(keywords[:3])}）"

    elapsed = time.time() - t0

    return {
        "original_query": query,
        "cleaned_query": cleaned,
        "expanded_query": expanded_query,
        "keywords": keywords,
        "needs_expansion": needs_expansion,
        "processing_time": round(elapsed, 4)
    }
