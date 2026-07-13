# -*- coding: utf-8 -*-  # 工单18：指定源码编码为 UTF-8。
"""lexical_index.py - 工单18智能助教的稀疏关键词召回模块。"""  # 工单18：声明当前文件功能。

from __future__ import annotations  # 工单18：启用延迟类型注解。


def query_terms(query: str) -> list[str]:  # 工单18：将查询转为关键词列表。
    normalized = query.strip().lower()  # 工单18：标准化查询文本。
    words = [term.strip().lower() for term in query.replace("，", " ").replace(",", " ").replace("。", " ").replace("？", " ").split() if term.strip()]  # 工单18：提取词级检索项。
    if normalized and len(words) <= 1:  # 工单18：为中文短句补充字符级与双字级检索项。
        words.extend([normalized[index:index + 2] for index in range(max(len(normalized) - 1, 0))])  # 工单18：追加双字片段。
        words.extend([char for char in normalized if not char.isspace()])  # 工单18：追加单字片段。
    return [item for item in dict.fromkeys(words) if item]  # 工单18：返回去重去空后的词项列表。


def lexical_score(query: str, text: str) -> float:  # 工单18：计算稀疏关键词相关度。
    terms = query_terms(query)  # 工单18：获取查询词项列表。
    if not terms:  # 工单18：对空查询直接返回零分。
        return 0.0  # 工单18：结束空查询评分。
    lower_text = text.lower()  # 工单18：将待检索文本转为小写。
    score = 0.0  # 工单18：初始化分数。
    for term in terms:  # 工单18：遍历全部检索词项。
        count = lower_text.count(term)  # 工单18：统计词项命中次数。
        score += count * 2 + (0.5 if term in lower_text else 0.0)  # 工单18：叠加词项得分。
    return score  # 工单18：返回稀疏检索得分。
