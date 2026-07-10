# 这里定义 DeepSeek 客户端，负责调用大模型生成讲解内容。
import requests


class DeepSeekClient:
    """这里封装 DeepSeek 请求逻辑。"""

    def __init__(self, base_url: str, api_key: str, model: str):
        # 这里保存接口地址。
        self.base_url = base_url.rstrip("/")
        # 这里保存 API 密钥。
        self.api_key = api_key.strip()
        # 这里保存模型名。
        self.model = model

    def is_enabled(self) -> bool:
        # 这里判断是否真的配置了可用密钥。
        return bool(self.api_key)

    def build_prompt(self, record: dict, mode: str, language: str, query: str) -> str:
        # 这里准备模式映射。
        mode_name = {"guide": "导览讲解", "history": "历史文化解读", "story": "景点故事"}.get(mode, "导览讲解")
        # 这里返回给模型的完整提示词。
        return (
            f"你是文旅讲解助手。请基于以下景点资料，用{language}输出{mode_name}。"
            f"用户问题：{query}。景点名称：{record['name']}。"
            f"摘要：{record['summary']}。历史：{record['history']}。"
            f"导览：{record['guide']}。故事：{record['story']}。"
            "输出要自然、清晰、适合游客阅读，控制在180字以内。"
        )

    def generate(self, record: dict, mode: str, language: str, query: str) -> str:
        # 这里在未配置密钥时直接返回空字符串。
        if not self.is_enabled():
            return ""
        # 这里准备请求地址。
        url = f"{self.base_url}/chat/completions"
        # 这里准备请求头。
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        # 这里准备请求体。
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": self.build_prompt(record, mode, language, query)}],
            "temperature": 0.7,
        }
        try:
            # 这里发起网络请求。
            response = requests.post(url, headers=headers, json=payload, timeout=45)
            # 这里检查 HTTP 状态。
            response.raise_for_status()
            # 这里解析返回 JSON。
            data = response.json()
            # 这里提取模型内容。
            return data["choices"][0]["message"].get("content", "").strip()
        except Exception:
            # 这里失败时返回空字符串，让上层走模板兜底。
            return ""
