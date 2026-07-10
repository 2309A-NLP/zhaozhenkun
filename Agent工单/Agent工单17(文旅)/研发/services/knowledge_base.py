# 这里负责文旅知识库的加载、向量化与检索。
import json
import re

import numpy as np

from services.vector_index import SimpleVectorIndex


class TourismKnowledgeBase:
    """这里封装文旅知识库。"""

    def __init__(self, data_path: str):
        # 这里保存数据文件路径。
        self.data_path = data_path
        # 这里加载所有景点记录。
        self.records = self._load_records()
        # 这里初始化向量索引。
        self.index = SimpleVectorIndex()
        # 这里提前构建向量，提升查询速度。
        self.vectors = self._build_vectors()

    def _load_records(self):
        # 这里读取 JSON 文件。
        with open(self.data_path, "r", encoding="utf-8") as file:
            return json.load(file)

    def _normalize_text(self, text: str) -> str:
        # 这里做基础清洗。
        return re.sub(r"\s+", " ", (text or "").strip().lower())

    def _tokenize(self, text: str):
        # 这里把中英文拆成可比对 token。
        text = self._normalize_text(text)
        chinese_parts = re.findall(r"[\u4e00-\u9fff]{1}", text)
        latin_parts = re.findall(r"[a-zA-Z0-9]+", text)
        return chinese_parts + latin_parts

    def _record_text(self, record: dict) -> str:
        # 这里把多字段拼成检索文本。
        parts = [record.get("name", ""), record.get("city", ""), record.get("category", "")]
        parts += [record.get("summary", ""), record.get("history", ""), record.get("guide", "")]
        parts += [record.get("story", ""), " ".join(record.get("tags", []))]
        parts += [" ".join(record.get("image_keywords", [])), " ".join(record.get("video_keywords", []))]
        parts += [" ".join(record.get("audio_keywords", []))]
        return " ".join(parts)

    def _text_to_vector(self, text: str) -> np.ndarray:
        # 这里建立轻量词袋向量。
        vector = np.zeros(128, dtype=np.float32)
        for token in self._tokenize(text):
            vector[hash(token) % 128] += 1.0
        norm = np.linalg.norm(vector)
        return vector if norm == 0 else vector / norm

    def _build_vectors(self):
        # 这里为所有记录建立向量。
        vectors = [self._text_to_vector(self._record_text(record)) for record in self.records]
        # 这里同步重建索引。
        self.index.rebuild(vectors)
        return vectors

    def search(self, query: str, top_k: int = 3):
        # 这里执行文本检索。
        query_vector = self._text_to_vector(query)
        top_items = self.index.search(query_vector, top_k=top_k)
        return [{"record": self.records[idx], "score": score} for idx, score in top_items]

    def multimodal_search(self, hints: str, top_k: int = 3):
        # 这里复用文本检索来模拟图片/视频线索检索。
        return self.search(hints, top_k=top_k)

    def build_template_answer(self, item: dict, mode: str = "guide", language: str = "zh"):
        # 这里提取当前命中的景点记录。
        record = item["record"]
        # 这里处理英文输出模板。
        if language == "en":
            return {"spot_name": record["language_variants"].get("en", record["name"]), "summary": record["summary"], "guide_text": f"Recommended visit: {record['guide']}", "history_text": f"Historical context: {record['history']}", "story_text": f"Cultural story: {record['story']}"}
        # 这里准备中文模式映射。
        mode_map = {"guide": record["guide"], "history": record["history"], "story": record["story"]}
        # 这里返回中文结构化结果。
        return {"景点名称": record["name"], "城市": record["city"], "检索得分": item["score"], "摘要": record["summary"], "生成内容": mode_map.get(mode, record["guide"]), "延展解读": f"推荐标签：{'、'.join(record.get('tags', []))}。结合游客输入，可继续生成讲解词、活动介绍和历史文化解读。"}
