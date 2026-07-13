"""该文件用于接入真实联网搜索接口并整理公开搜索结果。"""

# 导入正则模块，用于清理搜索摘要中的 HTML 标记。
import re

# 导入公共 HTTP 客户端，便于访问外部搜索接口。
from development.services.http_client import HttpJsonClient


# 定义联网搜索服务，用于对接 DuckDuckGo 与维基搜索接口。
class SearchService:
    # 初始化搜索服务，并注入底层 HTTP 客户端。
    def __init__(self, http_client: HttpJsonClient | None = None) -> None:
        # 保存 HTTP 客户端对象，便于复用连接。
        self.http_client = http_client or HttpJsonClient()

    # 执行公开搜索并返回格式化结果文本。
    def search(self, query: str, limit: int = 3) -> str:
        # 先尝试使用 DuckDuckGo 即时答案接口。
        results = self._search_duckduckgo(query, limit)
        # 若结果不足，则继续回退到维基搜索接口。
        if not results:
            results = self._search_wikipedia(query, limit)
        # 若仍无结果，则返回明确提示文本。
        if not results:
            return "未检索到公开搜索结果，请尝试补充更明确的关键词。"
        # 将结果列表格式化为多行文本。
        return "\n".join(f"{index + 1}. {item}" for index, item in enumerate(results))

    # 调用 DuckDuckGo 即时答案接口获取摘要类结果。
    def _search_duckduckgo(self, query: str, limit: int) -> list[str]:
        # 尝试访问真实联网搜索接口。
        try:
            # 请求 DuckDuckGo 即时答案 JSON 数据。
            data = self.http_client.get_json(
                "https://api.duckduckgo.com/",
                {
                    "q": query,
                    "format": "json",
                    "no_redirect": 1,
                    "no_html": 1,
                    "skip_disambig": 1,
                },
            )
        # 若网络异常，则直接回退为空结果。
        except Exception:
            return []
        # 准备承载搜索结果的文本列表。
        results: list[str] = []
        # 提取摘要文本与来源链接。
        abstract_text = str(data.get("AbstractText", "")).strip()
        # 提取摘要来源链接。
        abstract_url = str(data.get("AbstractURL", "")).strip()
        # 若摘要非空，则优先加入结果列表。
        if abstract_text:
            results.append(f"{abstract_text} 来源：{abstract_url or 'DuckDuckGo'}")
        # 遍历关联主题，提取更多公开结果。
        for item in self._flatten_related_topics(data.get("RelatedTopics", [])):
            # 提取条目文本。
            text = str(item.get("Text", "")).strip()
            # 提取条目链接。
            first_url = str(item.get("FirstURL", "")).strip()
            # 仅在文本存在时写入结果。
            if text:
                results.append(f"{text} 来源：{first_url or 'DuckDuckGo'}")
            # 当结果达到上限后停止遍历。
            if len(results) >= limit:
                break
        # 返回截断后的结果列表。
        return results[:limit]

    # 调用中文维基搜索接口获取更稳定的文本结果。
    def _search_wikipedia(self, query: str, limit: int) -> list[str]:
        # 尝试访问真实联网维基搜索接口。
        try:
            # 请求维基搜索结果 JSON 数据。
            data = self.http_client.get_json(
                "https://zh.wikipedia.org/w/api.php",
                {
                    "action": "query",
                    "list": "search",
                    "format": "json",
                    "utf8": 1,
                    "srlimit": limit,
                    "srsearch": query,
                },
            )
        # 若网络异常，则直接返回空结果。
        except Exception:
            return []
        # 读取搜索结果数组。
        items = data.get("query", {}).get("search", [])
        # 准备格式化后的结果容器。
        results: list[str] = []
        # 遍历搜索结果并提取标题与摘要。
        for item in items:
            # 提取搜索标题文本。
            title = str(item.get("title", "")).strip()
            # 清理摘要中的 HTML 标签。
            snippet = self._strip_html(str(item.get("snippet", "")).strip())
            # 在标题存在时写入结果。
            if title:
                results.append(f"{title}：{snippet} 来源：https://zh.wikipedia.org/wiki/{title}")
        # 返回整理后的结果列表。
        return results[:limit]

    # 展平 DuckDuckGo 返回的关联主题嵌套结构。
    def _flatten_related_topics(self, items: list[object]) -> list[dict[str, object]]:
        # 准备展平后的条目列表。
        flattened: list[dict[str, object]] = []
        # 遍历原始条目结构。
        for item in items:
            # 若当前项本身就是结果条目，则直接写入列表。
            if isinstance(item, dict) and "Text" in item:
                flattened.append(item)
            # 若当前项包含子主题数组，则递归拉平子条目。
            if isinstance(item, dict) and "Topics" in item:
                flattened.extend(self._flatten_related_topics(item["Topics"]))
        # 返回展平后的结果列表。
        return flattened

    # 清理搜索摘要中的 HTML 标签与多余空白。
    def _strip_html(self, text: str) -> str:
        # 删除 HTML 标签，保留纯文本内容。
        cleaned = re.sub(r"<[^>]+>", "", text)
        # 返回压缩空白后的文本结果。
        return re.sub(r"\s+", " ", cleaned).strip()
