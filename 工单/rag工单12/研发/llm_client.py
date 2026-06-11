"""
LLM API 调用模块
功能：封装对小米 MiMo Token Plan API 的 chat/completions HTTP 请求
完成：提供 call_llm() 和 call_llm_json() 两个函数，含超时、重试和 JSON 解析
"""
import logging

logger = logging.getLogger(__name__)
import sys, os
# 将项目根目录加入路径，支持从任意子目录导入其他模块
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _sub in ["设计", "研发", "测试", "部署"]:
    _p = os.path.join(_root, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import requests  # HTTP 请求
import json      # JSON 解析

import config    # API 密钥、URL、模型等


def call_llm(
    prompt: str,
    system_prompt: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None
) -> str:
    """
    调用小米 MiMo API 获取 AI 回复文本
    参数：
        prompt: 用户消息
        system_prompt: 系统提示词（可选）
        temperature: 温度（默认 config.LLM_TEMPERATURE）
        max_tokens: 最大生成长度（默认 config.LLM_MAX_TOKENS）
    返回：
        AI 回复文本
    """
    temp = temperature if temperature is not None else config.LLM_TEMPERATURE
    max_tok = max_tokens if max_tokens is not None else config.LLM_MAX_TOKENS

    # 构造消息列表
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    # 请求体
    payload = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "temperature": temp,
        "max_tokens": max_tok
    }

    # 请求头
    headers = {
        "Authorization": f"Bearer {config.API_KEY}",
        "Content-Type": "application/json"
    }

    # 发送请求（带3次重试）
    import time as _time


    for _attempt in range(3):
        try:
            resp = requests.post(
                f"{config.BASE_URL}/chat/completions",
                headers=headers, json=payload,
                timeout=config.LLM_TIMEOUT
            )
            if resp.status_code == 429:
                _time.sleep(5 * (_attempt + 1))
                continue
            if resp.status_code != 200:
                raise Exception(f"HTTP {resp.status_code}: {resp.text[:300]}")
            result = resp.json()
            msg = result["choices"][0]["message"]
            content = msg.get("content") or msg.get("reasoning_content") or "无响应"
            return content.strip()
        except requests.exceptions.Timeout:
            if _attempt < 2:
                _time.sleep(3)
                continue
            raise Exception(f"请求超时 ({config.LLM_TIMEOUT}s)")
        except requests.exceptions.ConnectionError:
            if _attempt < 2:
                _time.sleep(5 * (_attempt + 1))
                continue
            raise Exception(f"连接失败: {config.BASE_URL}")
    raise Exception("重试3次均失败")


def call_llm_json(
    prompt: str,
    system_prompt: str | None = None,
    temperature: float | None = None
) -> dict:
    """
    调用 LLM 并解析返回的 JSON
    参数：同 call_llm
    返回：解析后的 Python dict
    """
    # 强制要求 JSON 输出
    json_system = (system_prompt or "") + (
        "\n\n你必须以 JSON 格式返回结果，不要包含其他文字。"
    )
    text = call_llm(prompt, json_system, temperature)

    # 提取 JSON
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        return json.loads(text[start:end])
    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        return json.loads(text[start:end])
    raise ValueError(f"未找到 JSON: {text[:200]}")


if __name__ == "__main__":
    """测试 API 连通性"""
    print("🚀 测试小米 MiMo API...")
    try:
        reply = call_llm("你好，用一句话介绍自己")
        print(f"✅ {reply[:200]}")
    except Exception as e:
        print(f"❌ {e}")
