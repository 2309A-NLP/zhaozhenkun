# -*- coding: utf-8 -*-
"""
agent_core.py — Agent核心引擎
功能：DeepSeek意图识别 → 工具路由 → 结果整合 → 多轮对话
      使用Function Calling模式让LLM自主选择工具
工单编号：人工智能NLP-Agent数字人项目-智能体任务
"""

import json, time, logging, requests  # 标准库
import config  # 配置
from tools import TOOL_REGISTRY, call_tool, get_tool_descriptions  # 工具集

logger = logging.getLogger("agent.core")  # 核心日志器


def build_system_prompt():
    """构建Agent的系统提示词（含工具描述+路由规则）"""
    tool_desc = get_tool_descriptions()  # 获取工具描述
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


def recognize_intent(user_query, history=None):
    """调用DeepSeek识别用户意图，返回工具名+查询文本"""
    messages = [{"role": "system", "content": build_system_prompt()}]  # 系统提示
    # 添加历史对话（最近N条）
    if history:  # 有历史
        for h in history[-config.MAX_HISTORY:]:  # 最近N条
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})  # 添加
    messages.append({"role": "user", "content": user_query})  # 用户问题

    url = f"{config.DEEPSEEK_BASE_URL}/chat/completions"  # API端点
    headers = {"Authorization": f"Bearer {config.DEEPSEEK_API_KEY}", "Content-Type": "application/json"}  # 请求头
    payload = {"model": config.DEEPSEEK_MODEL, "messages": messages, "temperature": 0.0,
               "max_tokens": 1024, "stream": False}  # 请求体（推理模型需更大token预算）

    for attempt in range(config.MAX_RETRIES):  # 重试
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=config.API_TIMEOUT)  # 请求
            if r.status_code == 200:  # 成功
                body = r.json()
                msg = body["choices"][0]["message"]
                content = (msg.get("content") or "").strip()
                # 推理模型兜底：content为空时从reasoning_content提取
                if not content:
                    reasoning = msg.get("reasoning_content", "")
                    if reasoning:
                        logger.warning("意图识别: content为空，从reasoning提取(%d字)", len(reasoning))
                        paragraphs = reasoning.split("\n\n")
                        content = paragraphs[-1].strip() if paragraphs else reasoning.strip()
                if not content:
                    # max_tokens不够，加大后重试
                    logger.warning("意图识别: 空响应，加大max_tokens重试")
                    payload["max_tokens"] = 2048
                    continue
                # 解析JSON响应
                try:
                    # 处理可能的markdown包裹
                    if "```" in content:  # 有代码块
                        content = content.split("```")[1]  # 取第一个代码块
                        if content.startswith("json"): content = content[4:]  # 去json标记
                    result = json.loads(content.strip())  # 解析JSON
                    return result.get("tool", "unknown"), result.get("query", user_query), result.get("reason", "")  # 返回
                except json.JSONDecodeError:  # JSON解析失败
                    # 降级：从文本中提取工具名
                    for tool_name in TOOL_REGISTRY:  # 遍历工具
                        if tool_name in content:  # 工具名出现
                            return tool_name, user_query, "从文本中提取"  # 返回
                    return "unknown", user_query, "无法解析"  # 失败
            else:
                logger.warning("意图识别HTTP %d: %s", r.status_code, r.text[:100])
        except Exception as e:  # 请求失败
            logger.warning("意图识别重试%d: %s", attempt + 1, e)  # 日志
            time.sleep((attempt + 1) * 1)  # 等待
    return "unknown", user_query, "API调用失败"  # 最终失败


def process_query(user_query, history=None, pre_recognized_tool=None):
    """完整的Agent流水线：意图识别→调用工具→返回结果
    pre_recognized_tool: 如果外部已识别意图，可传入避免重复API调用"""
    t0 = time.time()  # 计时
    logger.info("📩 用户: %s", user_query[:100])  # 日志

    # 第一步：意图识别（优先使用外部传入的结果）
    if pre_recognized_tool and pre_recognized_tool in TOOL_REGISTRY:
        tool_name, tool_query, reason = pre_recognized_tool, user_query, "外部预判"
    else:
        tool_name, tool_query, reason = recognize_intent(user_query, history)  # 识别
    logger.info("🎯 意图: %s | 原因: %s", tool_name, reason)  # 日志

    # 第二步：路由到工具
    if tool_name == "unknown" or tool_name not in TOOL_REGISTRY:  # 无法识别
        # 用通用DeepSeek回答
        answer = _general_chat(user_query, history)  # 通用对话
        elapsed = time.time() - t0  # 耗时
        logger.info("⚠ 未匹配工具，通用回答(%.1fs)", elapsed)  # 日志
        return {"answer": answer, "tool": "通用对话", "elapsed": round(elapsed, 2)}  # 返回

    # 第三步：调用工具
    result = call_tool(tool_name, tool_query)  # 调用
    elapsed = time.time() - t0  # 耗时
    logger.info("✅ %s 返回(%.1fs): %s", tool_name, elapsed, str(result.get('result', ''))[:100])  # 日志

    # 第四步：格式化答案
    if result["success"]:  # 成功
        answer = result['result']  # 工具已返回自然语言答案，直接使用
    else:  # 失败
        answer = f"⚠️ {result['result']}\n\n请尝试换个问法。"  # 错误信息

    return {"answer": answer, "tool": result["tool"], "elapsed": round(elapsed, 2)}  # 返回


def _general_chat(user_query, history=None):
    """通用对话（无工具匹配时用DeepSeek直接回答）"""
    messages = [{"role": "system", "content": "你是专业的AI智能助手。对用户问题给出肯定、直接、完整的回答。不要说你不知道或查不到——用你的知识给出最好的答案。回答要信息丰富，包含具体数据和细节，至少2-3句话。"}]
    if history:
        for h in history[-config.MAX_HISTORY:]:
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    messages.append({"role": "user", "content": user_query})
    url = f"{config.DEEPSEEK_BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {config.DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": config.DEEPSEEK_MODEL, "messages": messages, "temperature": 0.3, "max_tokens": 2048, "stream": False}
    for attempt in range(config.MAX_RETRIES):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=config.API_TIMEOUT)
            if r.status_code == 200:
                msg = r.json()["choices"][0]["message"]
                content = (msg.get("content") or "").strip()
                if not content:
                    reasoning = msg.get("reasoning_content", "")
                    if reasoning:
                        paragraphs = reasoning.split("\n\n")
                        content = paragraphs[-1].strip() if paragraphs else reasoning.strip()
                if content:
                    return content
        except Exception:
            pass
        time.sleep((attempt + 1) * 1)
    return "抱歉，AI服务暂不可用，请稍后重试。"


# ============================================================
# 测试
# ============================================================
if __name__ == "__main__":  # 直接运行
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")  # 日志
    tests = [  # 测试用例
        "帮我记录一下今天花了50块钱买午饭",
        "提醒我明天下午3点开会",
        "生成一张关于未来城市的图片",
        "查询景顺长城基金的最新净值",
        "湖南长远锂科股份有限公司的发起人有哪些",
        "今天天气怎么样"  # 无工具匹配
    ]
    for q in tests:  # 遍历
        print(f"\n{'='*50}")  # 分隔
        print(f"用户: {q}")  # 问题
        result = process_query(q)  # 处理
        print(f"工具: {result['tool']} | 耗时: {result['elapsed']}s")  # 结果
        print(f"答案: {result['answer'][:200]}")  # 答案
