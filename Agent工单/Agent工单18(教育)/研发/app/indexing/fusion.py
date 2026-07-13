# -*- coding: utf-8 -*-  # 工单18：指定源码编码为 UTF-8。
"""fusion.py - 工单18智能助教的双路召回融合模块。"""  # 工单18：声明当前文件功能。

from __future__ import annotations  # 工单18：启用延迟类型注解。


def rrf_score(rank: int, k: int = 60) -> float:  # 工单18：计算倒数排名融合分数。
    return 1.0 / (k + rank)  # 工单18：返回 RRF 单项分值。


def fuse_ranked_items(lexical_items: list[dict], semantic_items: list[dict]) -> list[dict]:  # 工单18：融合两路排序结果。
    merged = {}  # 工单18：初始化融合结果字典。
    for rank, item in enumerate(lexical_items, start=1):  # 工单18：遍历稀疏召回结果。
        key = item["candidate_id"]  # 工单18：读取候选唯一键。
        merged[key] = {**item, "fusion_score": rrf_score(rank) + item.get("lexical_score", 0.0) * 0.03}  # 工单18：写入初始融合分。
    for rank, item in enumerate(semantic_items, start=1):  # 工单18：遍历语义召回结果。
        key = item["candidate_id"]  # 工单18：读取候选唯一键。
        current = merged.get(key, {**item, "fusion_score": 0.0})  # 工单18：读取现有候选或初始化候选。
        current.update(item)  # 工单18：合并最新候选字段。
        current["fusion_score"] += rrf_score(rank) + item.get("semantic_score", 0.0) * 0.7  # 工单18：叠加语义召回分。
        merged[key] = current  # 工单18：回写融合结果字典。
    return sorted(merged.values(), key=lambda item: item["fusion_score"], reverse=True)  # 工单18：按融合分降序返回结果。
