#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
研发 — DeepSeek LLM 客户端模块
==============================================================================
功能: 封装对 DeepSeek API 的调用，提供统一的 chat 接口。
      支持多轮对话、系统提示词、温度控制等参数。
      兼容 OpenAI 兼容的 API 格式。
说明: 本模块是 Agent 与 LLM 之间的桥梁，负责所有 LLM 通信。
==============================================================================
"""
import json  # JSON 序列化/反序列化
import time  # 时间相关，用于重试延迟
from typing import Dict, List, Optional, Any  # 类型注解

import requests  # HTTP 请求库

from .config import (  # 从配置模块导入
    DEEPSEEK_API_KEY,  # API 密钥
    DEEPSEEK_BASE_URL,  # API 地址
    DEEPSEEK_MODEL,  # 模型名称
    LLM_TEMPERATURE,  # 温度参数
    LLM_MAX_TOKENS,  # 最大 token 数
    REQUEST_TIMEOUT,  # 请求超时
)


class DeepSeekClient:  # DeepSeek API 客户端类
    """DeepSeek API 客户端，封装 LLM 调用逻辑。"""

    def __init__(  # 初始化方法
        self,  # 实例自身
        api_key: str = None,  # API 密钥（可选，默认从配置读取）
        base_url: str = None,  # API 地址（可选）
        model: str = None,  # 模型名称（可选）
    ):
        """初始化 DeepSeek 客户端，设置 API 参数。"""
        self.api_key = api_key or DEEPSEEK_API_KEY  # 使用传入或默认的 API Key
        self.base_url = (base_url or DEEPSEEK_BASE_URL).rstrip("/")  # 去除末尾斜杠
        self.model = model or DEEPSEEK_MODEL  # 使用传入或默认的模型
        self.endpoint = f"{self.base_url}/v1/chat/completions"  # 构建完整 API 端点
        self.headers = {  # HTTP 请求头
            "Authorization": f"Bearer {self.api_key}",  # Bearer 认证
            "Content-Type": "application/json",  # JSON 内容类型
        }

    def chat(  # 核心对话方法
        self,  # 实例自身
        messages: List[Dict[str, str]],  # 消息列表 [{"role":"system/user/assistant","content":"..."}]
        temperature: float = None,  # 温度参数（可选）
        max_tokens: int = None,  # 最大 token 数（可选）
    ) -> str:  # 返回 LLM 的文本回复
        """发送多轮对话请求到 DeepSeek API，返回回复文本。"""
        temp = temperature if temperature is not None else LLM_TEMPERATURE  # 设置温度
        max_tok = max_tokens if max_tokens is not None else LLM_MAX_TOKENS  # 设置最大 token

        payload = {  # 构建 API 请求体
            "model": self.model,  # 模型名称
            "messages": messages,  # 对话消息列表
            "temperature": temp,  # 温度参数
            "max_tokens": max_tok,  # 最大 token
        }

        # 请求重试逻辑，最多 3 次
        for attempt in range(3):  # 重试循环
            try:  # 尝试发送请求
                response = requests.post(  # POST 请求
                    self.endpoint,  # API 端点
                    headers=self.headers,  # 请求头
                    json=payload,  # JSON 请求体
                    timeout=REQUEST_TIMEOUT,  # 超时设置
                )
                response.raise_for_status()  # 检查 HTTP 错误
                data = response.json()  # 解析 JSON 响应
                # 提取回复内容
                content = data["choices"][0]["message"]["content"]  # 获取回复文本
                return content  # 返回回复

            except requests.exceptions.Timeout:  # 超时异常
                if attempt < 2:  # 还有重试机会
                    time.sleep(2 ** attempt)  # 指数退避延迟
                    continue  # 继续重试
                raise ConnectionError("DeepSeek API 请求超时")  # 重试耗尽，抛异常

            except requests.exceptions.ConnectionError:  # 连接异常
                if attempt < 2:  # 还有重试机会
                    time.sleep(2 ** attempt)  # 指数退避延迟
                    continue  # 继续重试
                raise ConnectionError("无法连接到 DeepSeek API")  # 重试耗尽

            except requests.exceptions.HTTPError as e:  # HTTP 错误
                err_msg = f"DeepSeek API 返回错误: {e.response.status_code}"  # 错误信息
                raise ValueError(err_msg)  # 直接抛异常，不重试

            except (KeyError, IndexError) as e:  # 响应解析错误
                raise ValueError(f"无法解析 API 响应: {e}")  # 抛异常

        return ""  # 理论上不会执行到这里（保底返回）

    def chat_with_retry(  # 带重试和回退的对话方法
        self,  # 实例自身
        messages: List[Dict[str, str]],  # 消息列表
        temperature: float = None,  # 温度参数
        max_tokens: int = None,  # 最大 token
    ) -> str:  # 返回回复文本
        """调用 LLM，在失败时尝试降低温度重试。"""
        try:  # 首次尝试
            return self.chat(messages, temperature=temperature, max_tokens=max_tokens)  # 正常调用
        except Exception as e:  # 首次调用失败
            # 降低温度到 0.1 重试（更确定性的输出）
            try:  # 第二次尝试
                return self.chat(messages, temperature=0.1, max_tokens=max_tokens)  # 低温度重试
            except Exception:  # 第二次也失败
                raise e  # 抛出原始异常


# ============================================================
# 模块自检
# ============================================================
if __name__ == "__main__":  # 模块自检入口
    print("=" * 50)  # 分隔线
    print("  DeepSeek LLM 客户端 — 自检")  # 标题
    print("=" * 50)  # 分隔线

    client = DeepSeekClient()  # 创建客户端实例
    print(f"  模型: {client.model}")  # 打印模型名称
    print(f"  端点: {client.endpoint}")  # 打印 API 端点

    # 发送测试消息
    test_messages = [  # 测试对话
        {"role": "system", "content": "你是一个助手，用一句话回答。"},  # 系统提示
        {"role": "user", "content": "你好，请用中文说你是谁。"},  # 用户问题
    ]

    try:  # 尝试调用 API
        reply = client.chat(test_messages, temperature=0.1, max_tokens=100)  # 调用
        print(f"  测试连通: OK")  # 连通成功
        print(f"  回复: {reply}")  # 打印回复
    except Exception as e:  # 调用失败
        print(f"  测试连通: 失败 - {e}")  # 打印错误信息
