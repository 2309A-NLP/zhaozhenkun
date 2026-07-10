"""工单18：知识库检索服务，负责从本地文旅知识库中召回相关景点与说明。"""
# 工单18：导入JSON模块，用于读取本地知识库数据文件。
import json
# 工单18：导入路径工具，便于找到研发目录中的数据文件。
from pathlib import Path

# 工单18：定位景点知识库文件路径。
DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "spots.json"

# 工单18：加载完整景点列表，供接口和检索功能复用。
def load_spots() -> list:
    # 工单18：读取JSON文本并反序列化为Python列表。
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))

# 工单18：根据问题关键词做轻量召回，返回最相关的知识条目。
def search_spots(query: str, limit: int = 3) -> list:
    # 工单18：把查询内容转成小写，便于做不区分大小写的匹配。
    text = (query or "").lower()
    # 工单18：准备候选结果列表，用于记录每条知识的匹配分数。
    scored_items = []
    # 工单18：遍历知识库里的每个景点，计算匹配度。
    for item in load_spots():
        # 工单18：把名称、类别、关键词和简介拼在一起做统一匹配。
        haystack = " ".join([item["name"], item["category"], item["summary"], item["details"], " ".join(item["keywords"])]).lower()
        # 工单18：根据命中关键词数量做一个简单分数。
        score = sum(1 for part in text.split() if part and part in haystack)
        # 工单18：如果中文没有空格，再补一个整体包含判断避免漏召回。
        if text and text in haystack:
            score += 2
        # 工单18：只有分数大于0的结果才加入候选池。
        if score > 0:
            scored_items.append((score, item))
    # 工单18：按分数从高到低排序后截取前limit条。
    scored_items.sort(key=lambda pair: pair[0], reverse=True)
    # 工单18：如果一条都没命中，就兜底返回前limit条景点数据。
    return [item for _, item in scored_items[:limit]] or load_spots()[:limit]
