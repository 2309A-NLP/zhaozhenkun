"""文件功能：封装 DeepSeek 文本模型与 Qwen 多模态模型的统一调用。"""

from __future__ import annotations  # 启用延后类型注解支持。

import base64  # 生成图片的 Base64 数据。
import mimetypes  # 推断图片的 MIME 类型。
from pathlib import Path  # 处理本地文件路径。
from typing import Any  # 描述通用返回数据。

from openai import OpenAI  # 导入 OpenAI 兼容客户端。

from 设计.architecture import AppSettings  # 导入应用配置类型。


class ModelClient:  # 定义统一模型客户端。
    def __init__(self, settings: AppSettings) -> None:  # 初始化模型客户端。
        self.settings = settings  # 保存全局配置。
        self._deepseek = None  # 延迟初始化 DeepSeek 客户端。
        self._qwen = None  # 延迟初始化 Qwen 客户端。

    def _deepseek_client(self) -> OpenAI:  # 获取 DeepSeek 客户端实例。
        if self._deepseek is None:  # 如果客户端尚未初始化。
            self._deepseek = OpenAI(api_key=self.settings.deepseek_api_key, base_url=self.settings.deepseek_base_url)  # 创建兼容客户端。
        return self._deepseek  # 返回 DeepSeek 客户端。

    def _qwen_client(self) -> OpenAI:  # 获取 Qwen 客户端实例。
        if self._qwen is None:  # 如果客户端尚未初始化。
            self._qwen = OpenAI(api_key=self.settings.qwen_api_key, base_url=self.settings.qwen_base_url)  # 创建兼容客户端。
        return self._qwen  # 返回 Qwen 客户端。

    def _content_to_text(self, content: Any) -> str:  # 把模型响应内容统一转成文本。
        if isinstance(content, str):  # 如果内容本身就是字符串。
            return content  # 直接返回字符串内容。
        if isinstance(content, list):  # 如果内容是分段列表。
            parts: list[str] = []  # 初始化文本片段列表。
            for item in content:  # 遍历分段内容。
                if isinstance(item, dict) and item.get("type") == "text":  # 如果是文本片段。
                    parts.append(str(item.get("text", "")))  # 追加文本内容。
            return "\n".join(parts).strip()  # 返回拼接后的文本。
        return str(content or "")  # 兜底转换为字符串。

    def generate_text(self, system_prompt: str, user_prompt: str) -> str:  # 调用 DeepSeek 生成文本回答。
        if self.settings.use_mock_response or not self.settings.has_deepseek_credentials:  # 如果启用模拟或缺少凭证。
            return f"【模拟回答】{user_prompt.strip()[:240]}"  # 返回本地模拟结果。
        response = self._deepseek_client().chat.completions.create(  # 发起聊天补全请求。
            model=self.settings.deepseek_model,  # 指定 DeepSeek 模型名。
            messages=[  # 传入标准消息列表。
                {"role": "system", "content": system_prompt},  # 传入系统提示词。
                {"role": "user", "content": user_prompt},  # 传入用户提示词。
            ],  # 结束消息列表。
            temperature=0.3,  # 控制回答稳定性。
            timeout=self.settings.request_timeout,  # 设置请求超时时间。
        )  # 完成接口调用。
        return self._content_to_text(response.choices[0].message.content).strip()  # 返回整理后的模型结果。

    def _image_to_data_url(self, image_path: Path) -> str:  # 把图片转成 data URL。
        mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"  # 推断图片 MIME 类型。
        encoded = base64.b64encode(image_path.read_bytes()).decode("utf-8")  # 读取并编码图片字节。
        return f"data:{mime_type};base64,{encoded}"  # 返回可直接发送给模型的 data URL。

    def analyze_image(self, question: str, image_path: Path, visual_prompt: str) -> str:  # 调用 Qwen 做图像理解。
        if self.settings.use_mock_response or not self.settings.has_qwen_credentials:  # 如果启用模拟或缺少凭证。
            return f"【模拟图像分析】图片文件为 {image_path.name}，问题为：{question.strip()}。"  # 返回本地图像分析结果。
        response = self._qwen_client().chat.completions.create(  # 发起多模态补全请求。
            model=self.settings.qwen_model,  # 指定 Qwen 模型名。
            messages=[  # 构造多模态消息列表。
                {"role": "system", "content": "你是一名严谨的视觉分析助手。"},  # 提供系统角色说明。
                {  # 构造包含文本和图像的用户消息。
                    "role": "user",  # 指定消息角色。
                    "content": [  # 传入多模态内容列表。
                        {"type": "text", "text": visual_prompt},  # 传入文本问题。
                        {"type": "image_url", "image_url": {"url": self._image_to_data_url(image_path)}},  # 传入图片内容。
                    ],  # 结束多模态内容列表。
                },  # 结束用户消息对象。
            ],  # 结束消息列表。
            temperature=0.2,  # 使用偏稳健的采样参数。
            timeout=self.settings.request_timeout,  # 设置请求超时时间。
        )  # 完成接口调用。
        return self._content_to_text(response.choices[0].message.content).strip()  # 返回整理后的分析结果。
