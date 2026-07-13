# -*- coding: utf-8 -*-  # 指定源码使用 UTF-8 编码。
"""knowledge_service.py - 教育知识库加载与轻量检索模块。"""  # 说明当前文件职责。

from pathlib import Path  # 导入路径处理工具。
import json  # 导入 JSON 处理模块。
import re  # 导入正则处理模块。


class EducationKnowledgeService:  # 定义教育知识服务类。
    def __init__(self, data_path: str):  # 初始化知识服务实例。
        self.data_path = Path(data_path)  # 保存知识库文件路径。
        self.records = self._load_records()  # 读取全部知识记录。

    def _load_records(self) -> list:  # 加载知识库 JSON 文件。
        if not self.data_path.exists():  # 当知识库文件不存在时返回空列表。
            return []  # 返回空记录集合。
        return json.loads(self.data_path.read_text(encoding="utf-8"))  # 读取并解析 JSON 内容。

    def _normalize(self, text: str) -> str:  # 规范化待匹配文本内容。
        return re.sub(r"\s+", " ", str(text or "").strip().lower())  # 合并空白并转为小写文本。

    def _score(self, query: str, record: dict) -> int:  # 为单条记录计算匹配分数。
        target = " ".join([  # 拼接参与匹配的目标文本。
            record.get("course", ""),  # 读取课程字段。
            record.get("topic", ""),  # 读取主题字段。
            record.get("summary", ""),  # 读取摘要字段。
            record.get("scenario", ""),  # 读取场景字段。
            " ".join(record.get("keywords", [])),  # 拼接关键词列表。
            " ".join(record.get("tips", [])),  # 拼接教学建议列表。
        ])  # 完成目标文本拼接。
        normalized_target = self._normalize(target)  # 规范化目标文本。
        score = 0  # 初始化当前记录得分。
        for token in self._normalize(query).split(" "):  # 遍历查询分词。
            if token and token in normalized_target:  # 当词元命中目标文本时累加得分。
                score += 1  # 为命中词元增加得分。
        return score  # 返回当前记录最终得分。

    def search(self, query: str, course: str = "", top_k: int = 4) -> list:  # 执行知识检索并返回命中结果。
        scored = []  # 初始化命中结果列表。
        for record in self.records:  # 遍历全部知识记录。
            if course and record.get("course") != course:  # 当指定课程且记录课程不匹配时跳过。
                continue  # 继续处理下一条记录。
            score = self._score(query, record)  # 计算当前记录匹配分数。
            if score > 0:  # 仅保留命中的知识记录。
                scored.append((score, record))  # 追加得分与原始记录。
        scored.sort(key=lambda item: item[0], reverse=True)  # 按分数从高到低排序。
        return [self._format_item(record, score) for score, record in scored[:top_k]]  # 返回前几条格式化结果。

    def _format_item(self, record: dict, score: int) -> dict:  # 格式化单条知识结果。
        return {  # 返回结构化知识片段。
            "course": record.get("course", "未知课程"),  # 返回课程名称。
            "topic": record.get("topic", "未知主题"),  # 返回主题名称。
            "summary": record.get("summary", ""),  # 返回主题摘要。
            "scenario": record.get("scenario", ""),  # 返回适用场景。
            "tips": record.get("tips", []),  # 返回教学建议列表。
            "score": score,  # 返回匹配得分。
        }  # 完成知识片段格式化。

    def list_courses(self) -> list:  # 返回知识库中的课程列表。
        return sorted({record.get("course", "") for record in self.records if record.get("course")})  # 去重并排序课程名。
