# 这里定义通用大模型客户端，兼容 DeepSeek 与千问接口。
import base64
import mimetypes

import requests


class LlmClient:
    """这里封装兼容 OpenAI 风格接口的模型调用。"""

    def __init__(self, base_url: str, api_key: str, model: str, provider_name: str):
        # 这里保存接口地址。
        self.base_url = base_url.rstrip("/")
        # 这里保存 API 密钥。
        self.api_key = api_key.strip()
        # 这里保存模型名。
        self.model = model
        # 这里保存提供方名称。
        self.provider_name = provider_name

    def is_enabled(self) -> bool:
        # 这里判断当前客户端是否可用。
        return bool(self.api_key)

    def build_text_prompt(self, record: dict, mode: str, language: str, query: str) -> str:
        # 这里准备模式文本。
        mode_name = {"guide": "导览讲解", "history": "历史文化解读", "story": "景点故事"}.get(mode, "导览讲解")
        # 这里返回文本提示词。
        return (
            f"你是文旅讲解助手。请基于以下景点资料，用{language}输出{mode_name}。"
            f"用户问题：{query}。景点名称：{record['name']}。"
            f"摘要：{record['summary']}。历史：{record['history']}。导览：{record['guide']}。故事：{record['story']}。"
            "输出要自然、清晰、适合游客阅读，控制在180字以内。"
        )

    def request_chat(self, messages: list) -> str:
        # 这里在未配置密钥时直接返回空字符串。
        if not self.is_enabled():
            return ""
        # 这里准备请求地址。
        url = f"{self.base_url}/chat/completions"
        # 这里准备请求头。
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        # 这里准备请求体。
        payload = {"model": self.model, "messages": messages, "temperature": 0.7}
        try:
            # 这里发起网络请求。
            response = requests.post(url, headers=headers, json=payload, timeout=45)
            # 这里检查状态码。
            response.raise_for_status()
            # 这里解析 JSON。
            data = response.json()
            # 这里提取文本内容。
            return data["choices"][0]["message"].get("content", "").strip()
        except Exception:
            # 这里失败时返回空字符串，让上层兜底。
            return ""

    def generate_text(self, record: dict, mode: str, language: str, query: str) -> str:
        # 这里构建文本消息。
        messages = [{"role": "user", "content": self.build_text_prompt(record, mode, language, query)}]
        # 这里发起文本请求。
        return self.request_chat(messages)

    def encode_image_to_data_url(self, image_bytes: bytes, filename: str) -> str:
        # 这里推断 MIME 类型。
        mime_type = mimetypes.guess_type(filename)[0] or "image/png"
        # 这里编码图片为 base64。
        encoded = base64.b64encode(image_bytes).decode("utf-8")
        # 这里返回 data url。
        return f"data:{mime_type};base64,{encoded}"

    def build_multimodal_prompt(self, query: str, image_hint: str, image_data_url: str) -> list:
        # 这里构造兼容多模态的消息体。
        content = [{"type": "text", "text": f"请根据图片和文旅问题，输出景点识别、文化解读、导览建议。用户问题：{query or '请识别这张图片中的景点并讲解'}。补充线索：{image_hint or '无'}。"}]
        # 这里在有图片时追加图片内容。
        if image_data_url:
            content.append({"type": "image_url", "image_url": {"url": image_data_url}})
        return [{"role": "user", "content": content}]

    def generate_multimodal(self, query: str, image_hint: str, image_bytes: bytes = b"", filename: str = "upload.png") -> str:
        # 这里准备图片 data url。
        image_data_url = self.encode_image_to_data_url(image_bytes, filename) if image_bytes else ""
        # 这里构建多模态消息。
        messages = self.build_multimodal_prompt(query, image_hint, image_data_url)
        # 这里发起多模态请求。
        return self.request_chat(messages)
