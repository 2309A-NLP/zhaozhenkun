# -*- coding: utf-8 -*-
"""
agent_core.py — Agent 核心引擎
--------------------------------------------------------------
功能: DeepSeek 意图识别 → 工具路由 → 结果整合 → 多轮对话。
      使用 LLM 自主选择工具（Function Calling 思想），支持:
      - 5 工具分类: 记账本/日程提醒/文生图/基金问答/招股书RAG
      - 多轮对话 session 管理
      - 推理模型兼容（reasoning_content 兜底）

工单编号: 人工智能NLP-Agent数字人项目-智能体任务
所属目录: 研发
"""
import json                              # JSON 解析（LLM 返回的工具选择）
import time                              # 计时
import logging                           # 日志
import requests                          # HTTP 请求（DeepSeek API）

import config                            # 全局配置
from tool_registry import (               # 工具注册表
    TOOL_REGISTRY, call_tool, get_tool_descriptions
)

logger = logging.getLogger("agent.core")  # 核心引擎日志器


def build_system_prompt() -> str:
    """构建 Agent 系统提示词（含工具描述 + 路由规则）。

    返回:
        str: 完整的系统提示词
    """
    tool_desc = get_tool_descriptions()   # 获取所有工具的描述文本
    return f"""你是一个智能助手Agent，能够根据用户需求自动选择合适的工具来回答问题。

## 可用工具

{tool_desc}

## 工作流程

1. 分析用户输入，识别意图
2. 选择最合适的工具
3. 如果用户问题涉及多个方面，可以建议调用多个工具
4. 如果不确定用哪个工具，优先考虑最匹配的

## 输出格式（极其重要）

你必须只输出一个JSON对象，格式如下：
{{"tool": "工具名", "reason": "选择原因(简短)", "query": "传给工具的精简查询"}}

工具名必须是以下之一: {', '.join(TOOL_REGISTRY.keys())}

如果无法匹配任何工具，输出: {{"tool": "unknown", "reason": "无法识别意图", "query": "原问题"}}

不要输出任何其他内容，只输出JSON。"""


def recognize_intent(user_query: str, history: list | None = None) -> tuple:
    """调用 DeepSeek 识别用户意图，返回工具名 + 查询文本 + 原因。

    参数:
        user_query: 用户输入的原始查询
        history: 对话历史（可选，用于多轮上下文理解）
    返回:
        (tool_name: str, query: str, reason: str)
    """
    messages = [{"role": "system", "content": build_system_prompt()}]  # 系统提示词

    # 添加上下文历史（最近 N 条消息）
    if history:
        for h in history[-config.MAX_HISTORY:]:
            messages.append({
                "role": h.get("role", "user"),
                "content": h.get("content", "")
            })

    messages.append({"role": "user", "content": user_query})  # 当前用户问题

    # 构造 API 请求
    url = f"{config.DEEPSEEK_BASE_URL}/chat/completions"       # API 端点
    headers = {
        "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": config.DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0.0,           # 零温度确保稳定输出
        "max_tokens": 1024,           # 推理模型需要足够 token 预算
        "stream": False               # 非流式，一次返回完整结果
    }

    # 重试循环（指数退避）
    for attempt in range(config.MAX_RETRIES):
        try:
            r = requests.post(
                url, headers=headers, json=payload,
                timeout=config.API_TIMEOUT
            )
            if r.status_code == 200:                         # HTTP 成功
                body = r.json()
                msg = body["choices"][0]["message"]
                content = (msg.get("content") or "").strip()

                # ★ 推理模型兜底: content 为空时从 reasoning_content 提取
                if not content:
                    reasoning = msg.get("reasoning_content", "")
                    if reasoning:
                        logger.warning(
                            "意图识别: content为空，从reasoning提取(%d字)",
                            len(reasoning)
                        )
                        paragraphs = reasoning.split("\n\n")
                        content = paragraphs[-1].strip() if paragraphs else reasoning.strip()

                # reasoning_content 也为空 → max_tokens 不够，加大重试
                if not content:
                    logger.warning("意图识别: 空响应，加大max_tokens重试")
                    payload["max_tokens"] = 2048
                    continue

                # 解析 JSON 响应（含 markdown 代码块处理）
                try:
                    # 处理可能的 ```json ... ``` 包裹
                    if "```" in content:
                        content = content.split("```")[1]    # 取第一个代码块内容
                        if content.startswith("json"):
                            content = content[4:]             # 去掉 "json" 标记
                    result = json.loads(content.strip())     # 解析 JSON
                    return (
                        result.get("tool", "unknown"),
                        result.get("query", user_query),
                        result.get("reason", "")
                    )
                except json.JSONDecodeError:
                    # 降级: 从文本中直接匹配工具名
                    for tool_name in TOOL_REGISTRY:
                        if tool_name in content:
                            return tool_name, user_query, "从文本中提取"
                    return "unknown", user_query, "无法解析JSON"

            else:
                logger.warning("意图识别 HTTP %d: %s",
                               r.status_code, r.text[:100])

        except Exception as e:
            logger.warning("意图识别重试 %d/%d: %s",
                           attempt + 1, config.MAX_RETRIES, e)

        time.sleep((attempt + 1) * 1)  # 指数退避等待: 1s, 2s

    # 所有重试均失败
    logger.error("意图识别: 所有%d次重试均失败", config.MAX_RETRIES)
    return "unknown", user_query, "API调用失败"


def process_query(user_query: str, history: list | None = None,
                  pre_recognized_tool: str | None = None) -> dict:
    """完整的 Agent 流水线: 意图识别 → 调用工具 → 返回结果。

    参数:
        user_query: 用户原始查询
        history: 对话历史
        pre_recognized_tool: 外部已识别的工具名（避免重复 API 调用）
    返回:
        {"answer": str, "tool": str, "elapsed": float}
    """
    t0 = time.time()                                          # 开始计时
    logger.info("📩 用户: %s", user_query[:100])

    # 步骤1: 意图识别（优先使用外部传入的结果，避免重复 API 调用）
    if pre_recognized_tool and pre_recognized_tool in TOOL_REGISTRY:
        tool_name, tool_query, reason = pre_recognized_tool, user_query, "外部预判"
    else:
        tool_name, tool_query, reason = recognize_intent(user_query, history)
    logger.info("🎯 意图: %s | 原因: %s", tool_name, reason)

    # 步骤2: 路由决策 — 无匹配工具时使用通用对话
    if tool_name == "unknown" or tool_name not in TOOL_REGISTRY:
        answer = _general_chat(user_query, history)           # 通用 LLM 回答
        elapsed = time.time() - t0
        logger.info("⚠ 未匹配工具，通用回答(%.1fs)", elapsed)
        return {"answer": answer, "tool": "通用对话", "elapsed": round(elapsed, 2)}

    # 步骤3: 调用工具
    result = call_tool(tool_name, tool_query)
    elapsed = time.time() - t0
    logger.info("✅ %s 返回(%.1fs): %s",
                 tool_name, elapsed, str(result.get('result', ''))[:100])

    # 步骤4: 格式化答案
    if result["success"]:
        answer = result['result']                             # 工具已返回自然语言答案
    else:
        answer = f"⚠️ {result['result']}\n\n请尝试换个问法。"    # 错误信息

    # ★ 防兜底: 确保 answer 永远不为空（前端依赖此字段显示文本）
    if not answer or not answer.strip():
        logger.warning("工具 %s 返回空答案，使用兜底文本", tool_name)
        answer = f"已处理您关于「{user_query[:50]}」的请求，但工具未能返回有效结果。请换个问法试试。"

    return {"answer": answer, "tool": result["tool"],
            "elapsed": round(elapsed, 2)}


def _general_chat(user_query: str, history: list | None = None) -> str:
    """通用对话 — 无工具匹配时用 DeepSeek 直接回答。

    参数:
        user_query: 用户查询
        history: 对话历史
    返回:
        str: AI 生成的回复文本
    """
    # 系统提示词: 要求信息丰富、完整、肯定
    messages = [{
        "role": "system",
        "content": (
            "你是专业的AI智能助手。对用户问题给出肯定、直接、完整的回答。"
            "不要说你不知道或查不到——用你的知识给出最好的答案。"
            "回答要信息丰富，包含具体数据和细节，至少2-3句话。"
        )
    }]
    if history:
        for h in history[-config.MAX_HISTORY:]:
            messages.append({
                "role": h.get("role", "user"),
                "content": h.get("content", "")
            })
    messages.append({"role": "user", "content": user_query})

    url = f"{config.DEEPSEEK_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": config.DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0.3,          # 略高温度增加回答多样性
        "max_tokens": 2048,
        "stream": False
    }

    last_error = None
    for attempt in range(config.MAX_RETRIES):
        try:
            r = requests.post(
                url, headers=headers, json=payload,
                timeout=config.API_TIMEOUT
            )
            if r.status_code == 200:
                msg = r.json()["choices"][0]["message"]
                content = (msg.get("content") or "").strip()
                # 推理模型兜底: content 为空时提取 reasoning_content
                if not content:
                    reasoning = msg.get("reasoning_content", "")
                    if reasoning:
                        paragraphs = reasoning.split("\n\n")
                        content = paragraphs[-1].strip() if paragraphs else reasoning.strip()
                if content:
                    return content
                else:
                    logger.warning("通用对话: content和reasoning均为空")
            else:
                last_error = f"HTTP {r.status_code}"
        except Exception as e:
            last_error = str(e)[:80]
            logger.warning("通用对话重试 %d/%d: %s", attempt + 1, config.MAX_RETRIES, last_error)
        time.sleep((attempt + 1) * 1)  # 指数退避

    # ★ 所有重试失败 → 返回明确的兜底文本（确保前端始终有内容显示）
    logger.error("通用对话: 所有重试失败 (最后错误: %s)", last_error or "未知")
    return (
        "抱歉，AI服务暂时无法响应（已重试多次）。\n\n"
        "💡 建议：\n"
        "1. 稍后重试\n"
        "2. 检查 DeepSeek API 密钥是否有效\n"
        "3. 确认网络连接正常\n"
        f"4. 如持续无法使用，可检查日志: agent.log"
    )


# ============================================================
# 自测（直接运行此文件时触发）
# ============================================================
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )
    tests = [
        "帮我记录一下今天花了50块钱买午饭",
        "提醒我明天下午3点开会",
        "生成一张关于未来城市的图片",
        "查询景顺长城基金的最新净值",
        "湖南长远锂科股份有限公司的发起人有哪些",
        "今天天气怎么样",  # 无工具匹配 → 通用对话
    ]
    for q in tests:
        print(f"\n{'=' * 50}")
        print(f"用户: {q}")
        result = process_query(q)
        print(f"工具: {result['tool']} | 耗时: {result['elapsed']}s")
        print(f"答案: {result['answer'][:200]}")
