#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
02_研发 — DeepSeek LLM 客户端
==============================================================================
封装对 DeepSeek API 的调用，提供统一的信息提取、摘要生成接口。
模型: deepseek-v4-flash
API 地址: https://api.deepseek.com
==============================================================================
"""

import json  # JSON 解析，用于处理 LLM 返回的结构化数据
import os  # 环境变量读取
from typing import Optional, Dict, Any, List  # 类型注解

import requests  # HTTP 请求库，调用 DeepSeek API

from runtime_env import load_local_env  # 加载项目本地运行配置

load_local_env()


# ============================================================
# 配置常量
# ============================================================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")  # API密钥
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")  # API地址
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")  # 模型名称


class DeepSeekClient:
    """DeepSeek API 客户端封装。"""

    def __init__(self, api_key: str = None, base_url: str = None, model: str = None):
        self.api_key = api_key or DEEPSEEK_API_KEY
        self.base_url = (base_url or DEEPSEEK_BASE_URL).rstrip("/")
        self.model = model or DEEPSEEK_MODEL
        self.endpoint = f"{self.base_url}/v1/chat/completions"

        if not self.api_key:
            raise ValueError("未配置 DEEPSEEK_API_KEY，请先设置环境变量后再启动服务")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _call_api(self, messages: List[Dict], temperature: float = 0.1,
                  max_tokens: int = 2000) -> Dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            response = requests.post(
                self.endpoint,
                headers=self.headers,
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            raise ConnectionError(f"DeepSeek API 请求超时: {self.endpoint}")
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"无法连接到 DeepSeek API: {self.endpoint}")
        except requests.exceptions.HTTPError as e:
            raise ValueError(f"DeepSeek API 返回错误: {e.response.status_code} - {e.response.text}")

    def _parse_json_response(self, response: Dict) -> str:
        try:
            return response["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise ValueError(f"无法解析 API 响应: {response}, 错误: {e}")

    def extract(self, system_prompt: str, conversation: str,
                temperature: float = 0.1) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": conversation},
        ]
        response = self._call_api(messages, temperature=temperature)
        return self._parse_json_response(response)

    def summarize(self, system_prompt: str, history: str, conversation: str,
                  temperature: float = 0.3) -> str:
        user_message = f"""## 历史记忆上下文
{history}

## 本次对话
{conversation}"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        response = self._call_api(messages, temperature=temperature)
        return self._parse_json_response(response)

    def retrieve_analyze(self, system_prompt: str, query: str,
                         temperature: float = 0.0) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]
        response = self._call_api(messages, temperature=temperature)
        return self._parse_json_response(response)

    def chat(self, messages: List[Dict], temperature: float = 0.7,
             max_tokens: int = 2000) -> str:
        response = self._call_api(messages, temperature=temperature,
                                  max_tokens=max_tokens)
        return self._parse_json_response(response)


# ============================================================
# 模块自检
# ============================================================
if __name__ == "__main__":
    try:
        client = DeepSeekClient()
        print(f"DeepSeek 客户端已初始化:")
        print(f"  模型: {client.model}")
        print(f"  端点: {client.endpoint}")

        test_messages = [
            {"role": "system", "content": "你是一个助手，用一句话回答。"},
            {"role": "user", "content": "你好，请用中文说你是谁。"},
        ]
        reply = client.chat(test_messages, temperature=0.1, max_tokens=100)
        print(f"  测试连通: OK")
        print(f"  回复: {reply}")
    except Exception as e:
        print(f"  测试连通: 失败 - {e}")
