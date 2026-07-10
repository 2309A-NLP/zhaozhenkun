# -*- coding: utf-8 -*-  # 指定源码编码。
# 工单编号：人工智能CV-AIGC-19-文旅Agent任务工单-创意策划与内容生成V1.1-20260306  # 标记工单来源。
"""knowledge_service.py - 文旅知识库加载与轻量检索模块。"""  # 说明当前文件职责。

import json  # 导入 JSON 处理模块。
import re  # 导入正则模块。
from pathlib import Path  # 导入路径模块。


class TourismKnowledgeService:  # 定义文旅知识服务类。
    def __init__(self, data_path: str):  # 初始化知识服务。
        self.data_path = Path(data_path)  # 保存知识库路径对象。
        self.records = self._load_records()  # 加载知识记录。

    def _load_records(self) -> list:  # 从 JSON 文件加载记录。
        if not self.data_path.exists():  # 当知识库文件不存在时返回空列表。
            return []  # 返回空记录集。
        with self.data_path.open("r", encoding="utf-8") as file:  # 打开知识库文件。
            return json.load(file)  # 读取并返回 JSON 数据。

    def _normalize(self, text: str) -> str:  # 规范化输入文本。
        return re.sub(r"\s+", " ", str(text or "").strip().lower())  # 合并多余空白并转小写。

    def _score(self, query: str, record: dict) -> int:  # 计算简单匹配分数。
        target = " ".join(  # 拼接记录中的关键字段。
            [  # 构造字段列表。
                record.get("name", ""),  # 读取名称字段。
                record.get("city", ""),  # 读取城市字段。
                record.get("region", ""),  # 读取地区字段。
                record.get("best_time", ""),  # 读取最佳时间字段。
                record.get("best_for", ""),  # 读取适合人群字段。
                " ".join(record.get("tags", [])),  # 读取标签字段。
            ]  # 字段列表结束。
        )  # 完成目标文本拼接。
        normalized_target = self._normalize(target)  # 规范化目标文本。
        score = 0  # 初始化匹配分数。
        for token in self._normalize(query).split(" "):  # 遍历查询词元。
            if token and token in normalized_target:  # 当词元命中记录文本时加分。
                score += 1  # 累加命中次数。
        return score  # 返回最终得分。

    def search(self, query: str, top_k: int = 3) -> list:  # 执行知识检索。
        scored = []  # 初始化带分数的结果列表。
        for record in self.records:  # 遍历所有知识记录。
            score = self._score(query, record)  # 计算当前记录得分。
            if score > 0:  # 当记录命中查询时保留结果。
                scored.append((score, record))  # 追加得分与记录。
        scored.sort(key=lambda item: item[0], reverse=True)  # 按得分从高到低排序。
        return [self._format_item(record, score) for score, record in scored[:top_k]]  # 返回格式化后的前几条结果。

    def _format_item(self, record: dict, score: int) -> str:  # 格式化单条知识结果。
        return f"{record.get('name', '未知景点')}（{record.get('city', '未知城市')}·{record.get('region', '未知地区')}）：{record.get('summary', '')}；历史亮点：{record.get('history', '')}；适合人群：{record.get('best_for', '')}；标签：{'、'.join(record.get('tags', []))}；匹配分：{score}"  # 生成展示文本。


_service_cache = {}  # 缓存知识服务实例。


def load_knowledge_service(data_path: str) -> TourismKnowledgeService:  # 读取或创建知识服务实例。
    if data_path not in _service_cache:  # 当缓存中不存在该路径实例时创建新对象。
        _service_cache[data_path] = TourismKnowledgeService(data_path)  # 写入缓存。
    return _service_cache[data_path]  # 返回知识服务实例。


def list_regions_and_spots(data_path: str) -> dict:  # 返回按地区分组的景点信息。
    service = load_knowledge_service(data_path)  # 读取知识服务实例。
    grouped = {}  # 初始化分组结果。
    for record in service.records:  # 遍历所有景点记录。
        region = str(record.get("region", "其他地区")).strip() or "其他地区"  # 读取地区字段。
        grouped.setdefault(region, [])  # 初始化地区分组。
        grouped[region].append(record)  # 追加景点记录。
    return {"regions": sorted(grouped.keys()), "spots": grouped}  # 返回地区与景点映射。
