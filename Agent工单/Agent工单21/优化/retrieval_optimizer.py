"""文件功能：根据关键词重叠和摘要长度，对知识素材进行轻量召回排序。"""

from __future__ import annotations  # 启用延后类型注解支持。

import re  # 使用正则切分文本词项。
from typing import Any  # 描述通用记录类型。


class RetrievalOptimizer:  # 定义知识召回优化器。
    def _tokenize(self, text: str) -> list[str]:  # 对文本做轻量分词。
        return [token for token in re.split(r"[^\w一-鿿]+", text.lower()) if token]  # 返回词项列表。

    def score_asset(self, question: str, asset: dict[str, Any]) -> float:  # 计算单个素材得分。
        question_tokens = set(self._tokenize(question))  # 计算问题词项集合。
        content = f"{asset.get('name', '')} {asset.get('summary', '')} {asset.get('content_text', '')}"  # 拼接待比较文本。
        asset_tokens = self._tokenize(content)  # 计算素材词项列表。
        overlap = sum(1 for token in asset_tokens if token in question_tokens)  # 统计词项重叠数量。
        density = min(len(asset.get("content_text", "")) / 500.0, 2.0)  # 计算内容信息密度加成。
        return overlap * 2.0 + density  # 返回综合得分。

    def select_assets(self, question: str, assets: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:  # 选出最相关素材。
        ranked = sorted(assets, key=lambda item: self.score_asset(question, item), reverse=True)  # 按分数排序素材。
        return ranked[:limit] if ranked else []  # 返回限制数量的结果。
