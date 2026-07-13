# -*- coding: utf-8 -*-  # 工单18：指定源码编码为 UTF-8。
"""llm_client.py - 工单18智能助教的双模型文本与视觉接入模块。"""  # 工单18：声明当前文件功能。

from __future__ import annotations  # 工单18：启用延迟类型注解。

import base64  # 工单18：导入 Base64 编码模块。
import mimetypes  # 工单18：导入文件类型推断模块。

import requests  # 工单18：导入 HTTP 请求库。

from app.config import get_provider_config  # 工单18：导入模型配置读取函数。


class LlmClient:  # 工单18：定义统一大模型调用客户端。
    def _endpoint(self, provider: str) -> tuple[dict, str, dict]:  # 工单18：构造服务商配置、请求地址与请求头。
        config = get_provider_config(provider)  # 工单18：读取指定服务商配置。
        endpoint = config["base_url"].rstrip("/") + "/chat/completions"  # 工单18：拼接 OpenAI 兼容聊天接口地址。
        headers = {"Authorization": f"Bearer {config['api_key']}", "Content-Type": "application/json"}  # 工单18：构造统一请求头。
        return config, endpoint, headers  # 工单18：返回配置、地址与请求头。

    def _post(self, provider: str, payload: dict) -> dict:  # 工单18：执行统一的远端模型请求。
        config, endpoint, headers = self._endpoint(provider)  # 工单18：获取请求所需配置。
        response = requests.post(endpoint, json=payload, headers=headers, timeout=60)  # 工单18：调用远端大模型服务。
        response.raise_for_status()  # 工单18：若响应异常则直接抛出错误。
        data = response.json()  # 工单18：解析响应 JSON 内容。
        message = data["choices"][0]["message"]["content"]  # 工单18：提取主回答文本。
        return {"provider": provider, "model": config["model"], "answer": message}  # 工单18：返回统一结构结果。

    def chat(self, provider: str, system_prompt: str, user_prompt: str) -> dict:  # 工单18：定义通用聊天调用方法。
        config = get_provider_config(provider)  # 工单18：加载服务商配置。
        payload = {"model": config["model"], "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "temperature": 0.4}  # 工单18：构造兼容聊天请求体。
        return self._post(provider, payload)  # 工单18：执行文本聊天请求。

    def chat_vision(self, provider: str, system_prompt: str, user_prompt: str, file_name: str, file_bytes: bytes) -> dict:  # 工单18：定义通用视觉聊天调用方法。
        config = get_provider_config(provider)  # 工单18：加载服务商配置。
        mime_type = mimetypes.guess_type(file_name)[0] or "image/png"  # 工单18：根据文件名推断图片类型。
        image_base64 = base64.b64encode(file_bytes).decode("utf-8")  # 工单18：将图片内容编码为 Base64 文本。
        image_url = f"data:{mime_type};base64,{image_base64}"  # 工单18：拼接 data URL 图片内容。
        payload = {  # 工单18：构造视觉模型兼容请求体。
            "model": config["model"],  # 工单18：指定模型名称。
            "messages": [  # 工单18：组织系统消息与图文用户消息。
                {"role": "system", "content": system_prompt},  # 工单18：放入系统提示词。
                {"role": "user", "content": [{"type": "text", "text": user_prompt}, {"type": "image_url", "image_url": {"url": image_url}}]},  # 工单18：放入图文复合消息。
            ],  # 工单18：结束消息数组构造。
            "temperature": 0.2,  # 工单18：将视觉理解温度设置得更稳定。
        }  # 工单18：结束视觉请求体构造。
        return self._post(provider, payload)  # 工单18：执行视觉聊天请求。


llm_client = LlmClient()  # 工单18：创建全局模型客户端实例。
