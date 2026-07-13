# -*- coding: utf-8 -*-  # 工单18：指定源码编码为 UTF-8。
"""semantic_index.py - 工单18智能助教的轻量语义召回模块。"""  # 工单18：声明当前文件功能。

from __future__ import annotations  # 工单18：启用延迟类型注解。

from collections import Counter  # 工单18：导入计数器工具。
import math  # 工单18：导入数学计算模块。


def _char_ngrams(text: str, n: int = 2) -> Counter:  # 工单18：构造字符 n-gram 计数向量。
    normalized = "".join(char.lower() for char in text if not char.isspace())  # 工单18：清洗空白并统一大小写。
    if len(normalized) < n:  # 工单18：为过短文本直接返回单字符向量。
        return Counter(normalized)  # 工单18：返回字符计数结果。
    return Counter(normalized[index:index + n] for index in range(len(normalized) - n + 1))  # 工单18：返回 n-gram 向量。


def cosine_similarity(query: str, text: str) -> float:  # 工单18：计算字符 n-gram 余弦相似度。
    query_vec = _char_ngrams(query)  # 工单18：构造查询向量。
    text_vec = _char_ngrams(text)  # 工单18：构造文本向量。
    if not query_vec or not text_vec:  # 工单18：若任一向量为空则返回零分。
        return 0.0  # 工单18：结束空向量计算。
    dot = sum(query_vec[key] * text_vec.get(key, 0) for key in query_vec)  # 工单18：计算向量点积。
    query_norm = math.sqrt(sum(value * value for value in query_vec.values()))  # 工单18：计算查询向量范数。
    text_norm = math.sqrt(sum(value * value for value in text_vec.values()))  # 工单18：计算文本向量范数。
    if not query_norm or not text_norm:  # 工单18：处理零范数边界场景。
        return 0.0  # 工单18：返回零分。
    return dot / (query_norm * text_norm)  # 工单18：返回余弦相似度。
