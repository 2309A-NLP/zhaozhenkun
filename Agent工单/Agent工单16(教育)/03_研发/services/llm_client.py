# -*- coding: utf-8 -*-  # 指定源码使用 UTF-8 编码。
"""llm_client.py - 文本与多模态模型的统一调用模块。"""  # 说明当前文件职责。

import base64  # 导入 Base64 编码模块。
from pathlib import Path  # 导入路径处理工具。
import requests  # 导入 HTTP 请求模块。


class LLMClient:  # 定义统一模型客户端类。
    def __init__(self, settings: dict):  # 初始化模型客户端实例。
        self.settings = settings  # 保存应用配置对象。

    def get_status(self) -> dict:  # 返回当前模型可用状态摘要。
        return {  # 返回统一状态结构。
            "deepseek_text": "live" if self._is_text_ready("deepseek") else "demo",  # 返回 DeepSeek 文本模型状态。
            "deepseek_vision": "live" if self._is_vision_ready("deepseek") else "demo",  # 返回 DeepSeek 多模态模型状态。
            "qwen_text": "live" if self._is_text_ready("qwen") else "demo",  # 返回千问文本模型状态。
            "qwen_vision": "live" if self._is_vision_ready("qwen") else "demo",  # 返回千问多模态模型状态。
        }  # 完成状态构造。

    def chat_text(self, system_prompt: str, user_prompt: str, provider: str = "deepseek") -> str:  # 按指定服务商调用文本模型或返回演示结果。
        if not self._is_text_ready(provider):  # 当目标文本模型配置不完整时走演示模式。
            return self._demo_text_reply(system_prompt, user_prompt, provider)  # 返回演示模式的文案结果。
        payload = {  # 组装兼容 OpenAI 的请求体。
            "model": self._text_model(provider),  # 设置目标文本模型名称。
            "messages": [  # 写入消息数组。
                {"role": "system", "content": system_prompt},  # 写入系统提示词。
                {"role": "user", "content": user_prompt},  # 写入用户提示词。
            ],  # 完成消息数组定义。
            "temperature": 0.6,  # 设置生成温度。
        }  # 完成文本模型请求体定义。
        response = requests.post(self._chat_url(provider), json=payload, headers=self._headers(provider), timeout=60)  # 发起目标文本模型请求。
        response.raise_for_status()  # 当请求失败时抛出异常。
        data = response.json()  # 解析 JSON 响应内容。
        return data["choices"][0]["message"]["content"].strip()  # 返回模型生成文本。

    def chat_vision(self, system_prompt: str, user_prompt: str, image_path: str, provider: str = "qwen") -> str:  # 按指定服务商调用多模态模型或返回演示结果。
        if not self._is_vision_ready(provider):  # 当目标多模态模型配置不完整时走演示模式。
            return self._demo_vision_reply(user_prompt, image_path, provider)  # 返回演示模式的识别结果。
        content = [  # 构建兼容 OpenAI 的多模态消息内容。
            {"type": "text", "text": user_prompt},  # 写入文字描述部分。
            {"type": "image_url", "image_url": {"url": self._to_data_url(image_path)}},  # 写入图片数据 URL。
        ]  # 完成多模态消息体定义。
        payload = {  # 组装兼容 OpenAI 的多模态请求体。
            "model": self._vision_model(provider),  # 设置目标多模态模型名称。
            "messages": [  # 写入消息数组。
                {"role": "system", "content": system_prompt},  # 写入系统提示词。
                {"role": "user", "content": content},  # 写入多模态用户消息。
            ],  # 完成消息数组定义。
            "temperature": 0.3,  # 设置多模态生成温度。
        }  # 完成多模态请求体定义。
        response = requests.post(self._chat_url(provider), json=payload, headers=self._headers(provider), timeout=60)  # 发起目标多模态请求。
        response.raise_for_status()  # 当请求失败时抛出异常。
        data = response.json()  # 解析 JSON 响应内容。
        return data["choices"][0]["message"]["content"].strip()  # 返回模型生成文本。

    def _is_text_ready(self, provider: str) -> bool:  # 判断指定服务商的文本模型是否可用。
        return bool(self._api_key(provider) and self._text_model(provider))  # 返回文本模型配置完整性结果。

    def _is_vision_ready(self, provider: str) -> bool:  # 判断指定服务商的多模态模型是否可用。
        return bool(self._api_key(provider) and self._vision_model(provider))  # 返回多模态模型配置完整性结果。

    def _api_key(self, provider: str) -> str:  # 读取指定服务商的 API Key。
        if provider == "qwen":  # 当目标服务商为千问时返回千问密钥。
            return self.settings.get("DASHSCOPE_API_KEY", "")  # 返回千问 API Key。
        return self.settings.get("DEEPSEEK_API_KEY", "")  # 返回 DeepSeek API Key。

    def _chat_url(self, provider: str) -> str:  # 读取指定服务商的聊天接口地址。
        if provider == "qwen":  # 当目标服务商为千问时返回千问接口地址。
            return self.settings["DASHSCOPE_BASE_URL"].rstrip("/") + "/chat/completions"  # 返回千问兼容接口地址。
        return self.settings["DEEPSEEK_BASE_URL"].rstrip("/") + "/chat/completions"  # 返回 DeepSeek 接口地址。

    def _text_model(self, provider: str) -> str:  # 读取指定服务商的文本模型名称。
        if provider == "qwen":  # 当目标服务商为千问时优先读取千问文本模型名。
            return self.settings.get("DASHSCOPE_TEXT_MODEL") or self.settings.get("DASHSCOPE_VISION_MODEL", "")  # 返回千问文本模型或回退到多模态模型名。
        return self.settings.get("DEEPSEEK_MODEL", "")  # 返回 DeepSeek 文本模型名。

    def _vision_model(self, provider: str) -> str:  # 读取指定服务商的多模态模型名称。
        if provider == "qwen":  # 当目标服务商为千问时返回千问多模态模型名。
            return self.settings.get("DASHSCOPE_VISION_MODEL", "")  # 返回千问多模态模型名称。
        return self.settings.get("DEEPSEEK_VISION_MODEL", "")  # 返回 DeepSeek 多模态模型名称。

    def _headers(self, provider: str) -> dict:  # 构造指定服务商的通用请求头。
        return {  # 返回统一请求头结构。
            "Authorization": f"Bearer {self._api_key(provider)}",  # 写入目标服务商认证头。
            "Content-Type": "application/json",  # 声明请求体类型。
        }  # 完成请求头构造。

    def _to_data_url(self, image_path: str) -> str:  # 将图片文件编码为 data URL。
        suffix = Path(image_path).suffix.lower().replace(".", "") or "png"  # 读取图片后缀作为 MIME 子类型。
        raw = Path(image_path).read_bytes()  # 读取图片原始字节内容。
        encoded = base64.b64encode(raw).decode("utf-8")  # 将图片转为 Base64 字符串。
        return f"data:image/{suffix};base64,{encoded}"  # 返回完整的数据 URL 文本。

    def _demo_text_reply(self, system_prompt: str, user_prompt: str, provider: str) -> str:  # 构造演示模式下的文本回复。
        provider_name = "千问" if provider == "qwen" else "DeepSeek"  # 读取当前演示服务商中文名。
        return f"{provider_name} 演示模式已启用。\n\n" + user_prompt[:600] + "\n\n系统建议：请在 00_部署/.env 中配置模型参数后体验真实生成效果。"  # 返回演示回复文案。

    def _demo_vision_reply(self, user_prompt: str, image_path: str, provider: str) -> str:  # 构造演示模式下的多模态回复。
        name = Path(image_path).name  # 读取上传图片文件名。
        provider_name = "千问" if provider == "qwen" else "DeepSeek"  # 读取当前演示服务商中文名。
        return f"{provider_name} 演示模式已识别图片：{name}。\n任务目标：{user_prompt[:120]}\n建议：可启用对应多模态模型获得真实图像理解结果。"  # 返回演示识别结果。
