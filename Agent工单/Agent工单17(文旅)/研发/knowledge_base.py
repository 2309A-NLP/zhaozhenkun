import json
import math
import re
from pathlib import Path

import numpy as np


class TourismKnowledgeBase:
    """工单17：多模态文旅知识库，负责加载、向量化、检索。"""

    def __init__(self, data_path: str):
        self.data_path = Path(data_path)
        self.records = self._load_records()
        self.vectors = self._build_vectors()

    def _load_records(self):
        with self.data_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").strip().lower())

    def _tokenize(self, text: str):
        text = self._normalize_text(text)
        chinese_parts = re.findall(r"[\u4e00-\u9fff]{1}", text)
        latin_parts = re.findall(r"[a-zA-Z0-9]+", text)
        return chinese_parts + latin_parts

    def _record_text(self, record: dict) -> str:
        parts = [
            record.get("name", ""),
            record.get("city", ""),
            record.get("category", ""),
            record.get("summary", ""),
            record.get("history", ""),
            record.get("guide", ""),
            record.get("story", ""),
            " ".join(record.get("tags", [])),
            " ".join(record.get("image_keywords", [])),
            " ".join(record.get("video_keywords", [])),
            " ".join(record.get("audio_keywords", [])),
        ]
        return " ".join(parts)

    def _text_to_vector(self, text: str) -> np.ndarray:
        vector = np.zeros(128, dtype=np.float32)
        for token in self._tokenize(text):
            idx = hash(token) % 128
            vector[idx] += 1.0
        norm = np.linalg.norm(vector)
        return vector if norm == 0 else vector / norm

    def _build_vectors(self):
        return [self._text_to_vector(self._record_text(record)) for record in self.records]

    def search(self, query: str, top_k: int = 3):
        query_vector = self._text_to_vector(query)
        scored = []
        for record, vector in zip(self.records, self.vectors):
            score = float(np.dot(query_vector, vector))
            scored.append({"record": record, "score": round(score, 4)})
        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:top_k]

    def multimodal_search(self, hints: str, top_k: int = 3):
        return self.search(hints, top_k=top_k)

    def build_answer(self, item: dict, mode: str = "guide", language: str = "zh"):
        record = item["record"]
        if language == "en":
            return {
                "spot_name": record["language_variants"].get("en", record["name"]),
                "summary": record["summary"],
                "guide_text": f"Recommended visit: {record['guide']}",
                "history_text": f"Historical context: {record['history']}",
                "story_text": f"Cultural story: {record['story']}",
                "multimodal": {
                    "images": record.get("image_keywords", []),
                    "videos": record.get("video_keywords", []),
                    "audios": record.get("audio_keywords", []),
                    "subtitle": "English subtitles supported"
                }
            }
        mode_map = {
            "guide": record["guide"],
            "history": record["history"],
            "story": record["story"]
        }
        return {
            "景点名称": record["name"],
            "城市": record["city"],
            "检索得分": item["score"],
            "摘要": record["summary"],
            "生成内容": mode_map.get(mode, record["guide"]),
            "延展解读": f"推荐标签：{'、'.join(record.get('tags', []))}。结合游客输入，可继续生成讲解词、活动介绍和历史文化解读。",
            "多模态输出": {
                "图片推荐": record.get("image_keywords", []),
                "视频推荐": record.get("video_keywords", []),
                "音频推荐": record.get("audio_keywords", []),
                "字幕支持": "支持中文字幕与无障碍辅助"
            }
        }
