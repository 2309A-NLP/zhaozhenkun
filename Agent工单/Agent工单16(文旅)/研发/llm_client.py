# -*- coding: utf-8 -*-
# 工单编号：人工智能CV-AIGC-16-【必选】文旅Agent任务工单-需求分析与功能设计V1.1-20260306
"""
llm_client.py - 大模型API调用模块
功能：封装Kimi/DeepSeek/千问的流式和非流式调用
支持SSE流式输出，用于前端实时展示AI回复
"""

import json  # 用于解析API返回的JSON数据
import httpx  # 异步HTTP客户端，支持流式请求


# ============================================================
# LLM配置 - 三个大模型的API地址和密钥
# ============================================================
LLM_CONFIGS = {
    # Kimi配置：长文本理解能力强，适合文旅知识问答
    "kimi": {
        "base_url": "https://api.moonshot.cn/v1",  # Kimi API地址
        "api_key": "sk-VflRlPiX20AKgbT1xAmvCOBj6JuUcRzUX1djZDKlA1GXgkgb",  # API密钥
        "model": "moonshot-v1-8k",  # 模型名称
    },
    # DeepSeek配置：性价比高，适合技术分析和备选
    "deepseek": {
        "base_url": "https://api.deepseek.com",  # DeepSeek API地址
        "api_key": "sk-70c456e35e914eb88fa233a04856bcf4",  # API密钥
        "model": "deepseek-chat",  # 模型名称
    },
    # 千问配置：文旅领域知识丰富，适合场景分析
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",  # 千问API地址
        "api_key": "sk-cb2873cdfdb543d1a8a05f3ffda4620c",  # API密钥
        "model": "qwen-plus",  # 模型名称
    },
}  # 三个大模型的完整配置字典


# ============================================================
# 流式LLM调用 - 返回SSE事件流，前端实时显示
# ============================================================
async def stream_llm(provider: str, messages: list, temperature: float = 0.7):
    """
    流式调用大模型API，逐字返回生成内容
    参数:
        provider: 模型提供者 (kimi/deepseek/qwen)
        messages: 对话消息列表 [{"role":"system","content":"..."}, ...]
        temperature: 生成温度，控制随机性 (0-1)
    Yields:
        SSE格式字符串: "data: {json}\n\n"
    """
    # 获取对应提供者的配置，默认使用kimi
    config = LLM_CONFIGS.get(provider, LLM_CONFIGS["kimi"])  # 字典取值，兜底kimi
    url = f"{config['base_url']}/chat/completions"  # 拼接API端点URL

    # 构建请求体
    payload = {
        "model": config["model"],  # 模型名称
        "messages": messages,  # 对话消息
        "temperature": temperature,  # 温度参数
        "stream": True,  # 启用流式输出
    }

    # 请求头
    headers = {
        "Content-Type": "application/json",  # JSON内容类型
        "Authorization": f"Bearer {config['api_key']}",  # Bearer认证
    }

    # 使用httpx异步流式请求
    async with httpx.AsyncClient(timeout=120.0) as client:  # 120秒超时
        async with client.stream("POST", url, json=payload, headers=headers) as response:  # 发起流式POST
            # 检查HTTP状态码
            if response.status_code != 200:  # 非200表示出错
                body = await response.aread()  # 读取错误响应体
                # 返回错误信息
                yield f"data: {json.dumps({'error': f'API调用失败({response.status_code}): {body.decode()[:200]}'})}\n\n"
                yield "data: [DONE]\n\n"  # 结束标记
                return  # 提前退出

            # 逐行读取SSE流
            async for line in response.aiter_lines():  # 异步迭代每一行
                if line.startswith("data: "):  # SSE数据行
                    data_str = line[6:]  # 去掉"data: "前缀
                    if data_str.strip() == "[DONE]":  # 流结束标记
                        yield "data: [DONE]\n\n"  # 转发结束标记
                        return  # 正常退出
                    try:
                        data = json.loads(data_str)  # 解析JSON
                        delta = data.get("choices", [{}])[0].get("delta", {})  # 提取增量内容
                        content = delta.get("content", "")  # 获取文本内容
                        if content:  # 有内容才发送
                            yield f"data: {json.dumps({'content': content})}\n\n"  # SSE格式输出
                    except json.JSONDecodeError:  # JSON解析失败则跳过
                        continue  # 忽略无效行


# ============================================================
# 非流式LLM调用 - 等待完整响应后返回
# ============================================================
async def call_llm(provider: str, messages: list, temperature: float = 0.7) -> str:
    """
    非流式调用大模型API，返回完整文本
    参数:
        provider: 模型提供者 (kimi/deepseek/qwen)
        messages: 对话消息列表
        temperature: 生成温度
    返回:
        完整的AI回复文本
    """
    # 获取配置
    config = LLM_CONFIGS.get(provider, LLM_CONFIGS["kimi"])  # 字典取值
    url = f"{config['base_url']}/chat/completions"  # API端点

    # 构建请求（stream=False）
    payload = {
        "model": config["model"],  # 模型名称
        "messages": messages,  # 对话消息
        "temperature": temperature,  # 温度参数
    }  # 不设置stream，默认非流式

    headers = {
        "Content-Type": "application/json",  # JSON内容类型
        "Authorization": f"Bearer {config['api_key']}",  # Bearer认证
    }

    # 发起请求
    async with httpx.AsyncClient(timeout=180.0) as client:  # 180秒超时（PPT生成需要更长时间）
        response = await client.post(url, json=payload, headers=headers)  # POST请求
        if response.status_code != 200:  # 请求失败
            return f"API调用失败({response.status_code}): {response.text[:300]}"  # 返回错误信息
        data = response.json()  # 解析响应
        # 提取回复内容
        return data.get("choices", [{}])[0].get("message", {}).get("content", "未获取到回复")  # 返回文本
