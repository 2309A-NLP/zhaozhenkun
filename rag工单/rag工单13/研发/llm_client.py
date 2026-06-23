"""
llm_client.py - RAG工单13 LLM API调用模块
需求: 封装小米MiMo API的HTTP请求 — 工单"LLM生成"阶段（需降低API调用延迟）
功能: 1.统一调用接口 2.系统提示词支持 3.温度/max_tokens参数控制 4.异常处理
"""
import logging
import requests             # 需求：通过HTTP POST调用MiMo API（OpenAI兼容接口）
import json                 # 需求：解析API返回的JSON响应体
import 研发.config as config          # 需求：读取API_KEY、BASE_URL、LLM_MODEL等配置

logger = logging.getLogger(__name__)


def call_llm(prompt, system_prompt=None, temperature=None, max_tokens=None):
    """
    调用MiMo API获取AI回复——需求：LLM生成阶段的核心调用接口
    prompt: 用户问题/提示词
    system_prompt: 系统级指令（可选，控制回答风格）
    返回: AI生成的文本
    """
    temp = temperature if temperature is not None else config.LLM_TEMPERATURE
    max_tok = max_tokens if max_tokens is not None else config.LLM_MAX_TOKENS
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    payload = {
        "model": config.LLM_MODEL,           # 需求：使用mimo-v2.5-pro推理模型
        "messages": messages,                # 对话消息列表
        "temperature": temp,                 # 需求：控制生成随机性
        "max_tokens": max_tok                # 需求：控制生成长度（影响延迟）
    }
    headers = {
        "Authorization": f"Bearer {config.API_KEY}",  # 需求：Token Plan认证
        "Content-Type": "application/json"
    }
    try:
        resp = requests.post(
            f"{config.BASE_URL}/chat/completions",  # 需求：MiMo API端点
            headers=headers, json=payload,
            timeout=config.LLM_TIMEOUT               # 需求：超时控制
        )
        if resp.status_code != 200:
            raise Exception(f"HTTP {resp.status_code}: {resp.text[:200]}")
        result = resp.json()
        msg = result["choices"][0]["message"]
        # 需求：处理推理模型（content为空时fallback到reasoning_content）
        content = msg.get("content", "") or msg.get("reasoning_content", "") or ""
        return content.strip()
    except requests.exceptions.Timeout:
        raise Exception(f"API超时({config.LLM_TIMEOUT}秒)")
    except requests.exceptions.ConnectionError:
        raise Exception(f"连接失败: {config.BASE_URL}")
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise Exception(f"解析失败: {e}")


if __name__ == "__main__":
    """命令行测试——需求：验证API连通性"""
    print("🚀 测试MiMo API...")
    try:
        reply = call_llm("你好，用一句话介绍自己")
        print(f"✅ {reply[:100]}")
    except Exception as e:
        print(f"❌ {e}")
