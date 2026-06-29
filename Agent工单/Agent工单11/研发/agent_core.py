# -*- coding: utf-8 -*-
"""
agent_core.py — 医疗挂号 Agent 核心引擎
--------------------------------------------------------------
功能: DeepSeek 意图识别→参数提取→工具路由→结果整合。
      支持多轮对话 session 管理。

核心能力:
  1. 意图分类: 挂号/查询号源/取消挂号/查询排班/历史查询/科室列表
  2. 参数提取: 患者/科室/医生/时间/职称 从NL中结构化提取
  3. 工具调用: 参数传给对应工具函数执行
  4. 多轮对话: 缺参数时追问, 上下文补全

工单编号: 人工智能NLP-Agent数字人项目-医疗智能体-挂号管理任务
"""
import json
import time
import logging
import requests
from datetime import date

import config
from tool_registry import TOOL_REGISTRY, call_tool, get_tool_descriptions

logger = logging.getLogger("agent.core")


def build_system_prompt() -> str:
    """构建医疗挂号 Agent 系统提示词。"""
    tool_desc = get_tool_descriptions()
    today_str = time.strftime("%Y-%m-%d")
    weekday_cn = ["周一","周二","周三","周四","周五","周六","周日"][date.today().weekday()]
    return f"""你是一个医疗挂号智能助手Agent。当前日期: {today_str} {weekday_cn}。

## 可用工具

{tool_desc}

## 重要上下文

- 当前用户: 张三(user_id=1), 有两个孩子: 大宝(儿子, 2018年生), 二宝(女儿, 2020年生)
- 用户可以为家人(大宝/二宝)挂号
- 科室: 内科, 外科, 儿科, 妇科, 眼科, 耳鼻喉科, 牙科, 皮肤科, 消化内科
- 医生职称: 主任医师/副主任医师(专家号), 主治医师(普通号)

## 时间解析规则

- "今天": {today_str}
- "明天/明日": 加1天
- "后天": 加2天
- "下周X/下星期X": 从今天起算下周
- "上周X/上星期X": 从今天起算上周
- "上午": 约8-12点, "下午": 约12-18点

## 输出格式(极其重要)

你必须只输出一个JSON对象，格式如下:
{{"intent": "工具名", "params": {{"key": "value"}}, "reason": "简短原因"}}

- 挂号意图: {{"intent": "挂号", "params": {{"patient_name": "大宝", "dep_name": "儿科", "target_date": "2026-06-26", "period": "下午", "title_filter": "专家"}}, "reason": "..."}}
- 查询号源: {{"intent": "查询号源", "params": {{"dep_name": "牙科"}}, "reason": "..."}}
- 取消挂号: {{"intent": "取消挂号", "params": {{"dep_name": "消化内科", "date_desc": "上周三", "title_filter": "普通"}}, "reason": "..."}}
- 查询排班: {{"intent": "查询排班", "params": {{"doctor_name": "张建国"}}, "reason": "..."}}
- 查询历史: {{"intent": "查询历史", "params": {{"dep_name": "眼科"}}, "reason": "..."}}
- 科室列表: {{"intent": "科室列表", "params": {{}}, "reason": "..."}}
- 复约意图: {{"intent": "复约", "params": {{"dep_name": "眼科", "title_filter": "专家"}}, "reason": "用户要再约之前看过的医生"}}
  注意！"我之前挂过XX的XX，帮我再约那个医生/专家的号"、"复约XX的号" → 必须用"复约"，不要用"查询历史"！
  复约会自动查历史找到上次的医生并挂号，不需要分两步。

参数说明:
- patient_name: 患者名(大宝/二宝/张三等), 不填默认张三自己
- dep_name: 科室名(儿科/牙科/皮肤科等)
- doctor_name: 医生姓名
- target_date: 日期YYYY-MM-DD格式
- period: "上午"或"下午"
- title_filter: "专家"或"普通"
- date_desc: 日期描述(上周三/明天等)
- user_id: 固定=1

只输出JSON，不要输出其他内容!"""


def recognize_intent(user_query: str, history: list | None = None) -> dict:
    """调用 DeepSeek 识别用户意图并提取结构化参数。

    返回: {"intent": str, "params": dict, "reason": str}
    """
    messages = [{"role": "system", "content": build_system_prompt()}]

    if history:
        for h in history[-config.MAX_HISTORY:]:
            messages.append({
                "role": h.get("role", "user"),
                "content": h.get("content", "")[:500]
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
        "temperature": 0.0,
        "max_tokens": 1024,
        "stream": False
    }

    for attempt in range(config.MAX_RETRIES):
        try:
            r = requests.post(url, headers=headers, json=payload,
                            timeout=config.API_TIMEOUT)
            if r.status_code == 200:
                body = r.json()
                msg = body["choices"][0]["message"]
                content = (msg.get("content") or "").strip()

                # 推理模型兜底
                if not content:
                    reasoning = msg.get("reasoning_content", "")
                    if reasoning:
                        paragraphs = reasoning.split("\n\n")
                        content = paragraphs[-1].strip() if paragraphs else reasoning.strip()

                if not content:
                    payload["max_tokens"] = 2048
                    continue

                # 解析JSON
                try:
                    if "```" in content:
                        content = content.split("```")[1]
                        if content.startswith("json"):
                            content = content[4:]
                    result = json.loads(content.strip())
                    return {
                        "intent": result.get("intent", "unknown"),
                        "params": result.get("params", {}),
                        "reason": result.get("reason", "")
                    }
                except json.JSONDecodeError:
                    for tool_name in TOOL_REGISTRY:
                        if tool_name in content:
                            return {"intent": tool_name, "params": {}, "reason": "从文本提取"}
                    return {"intent": "unknown", "params": {}, "reason": "无法解析JSON"}

            else:
                logger.warning("意图识别 HTTP %d: %s", r.status_code, r.text[:100])

        except Exception as e:
            logger.warning("意图识别重试 %d/%d: %s", attempt + 1, config.MAX_RETRIES, e)

        time.sleep((attempt + 1) * 0.5)

    return {"intent": "unknown", "params": {}, "reason": "API调用失败"}


def process_query(user_query: str, history: list | None = None) -> dict:
    """完整 Agent 流水线: 意图识别 → 工具调用 → 结果返回。

    返回: {"answer": str, "tool": str, "elapsed": float}
    """
    t0 = time.time()
    logger.info("📩 用户: %s", user_query[:120])

    # 步骤1: 意图识别
    intent_info = recognize_intent(user_query, history)
    intent = intent_info["intent"]
    params = intent_info["params"]
    reason = intent_info["reason"]
    logger.info("🎯 意图: %s | 原因: %s | 参数: %s", intent, reason, params)

    # 步骤2: 路由
    user_id = params.pop("user_id", config.DEFAULT_USER_ID)

    if intent in TOOL_REGISTRY:
        result = call_tool(intent, user_id=user_id, **params)
    elif intent == "unknown":
        # 通用对话回退
        answer = _general_chat(user_query, history)
        elapsed = time.time() - t0
        return {"answer": answer, "tool": "通用对话", "elapsed": round(elapsed, 2)}
    else:
        return {"answer": f"抱歉，无法识别您的意图({intent})。请尝试: 挂号/查询号源/取消挂号/查询排班/查询历史",
                "tool": "unknown", "elapsed": round(time.time() - t0, 2)}

    elapsed = time.time() - t0
    answer = result.get("result", "处理完成")

    logger.info("✅ %s 返回(%.2fs): %s", intent, elapsed, answer[:100])
    return {"answer": answer, "tool": intent,
            "elapsed": round(elapsed, 2),
            "data": result.get("data")}


def _general_chat(user_query: str, history: list | None = None) -> str:
    """通用对话 — 无工具匹配时用 DeepSeek 直接回答。"""
    messages = [{
        "role": "system",
        "content": (
            f"你是医疗挂号智能助手。当前日期: {time.strftime('%Y-%m-%d')}。"
            "用户是张三，有两个孩子大宝(儿子,8岁)和二宝(女儿,6岁)。"
            "回答要专业、简洁、有帮助。如果用户问非挂号相关的问题，礼貌引导。"
        )
    }]
    if history:
        for h in history[-config.MAX_HISTORY:]:
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")[:500]})
    messages.append({"role": "user", "content": user_query})

    url = f"{config.DEEPSEEK_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": config.DEEPSEEK_MODEL,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 1024,
        "stream": False
    }

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
        except Exception as e:
            logger.warning("通用对话重试 %d/%d: %s", attempt + 1, config.MAX_RETRIES, e)
        time.sleep((attempt + 1) * 0.5)

    return "抱歉，AI服务暂不可用，请稍后重试。"


# ============================================================
# 自测
# ============================================================
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S"
    )
    tests = [
        "帮我大宝挂一个今天下午2点儿科专家的号",
        "牙科最近的号哪天的？",
        "我之前挂过眼科的一个专家，帮我再约那个专家的号",
        "我明天上午9点想带二宝看皮肤科，还有号吗？",
        "取消我上周三挂的消化内科普通号",
        "帮我查下张建国医生下周的坐诊时间",
    ]
    for q in tests:
        print(f"\n{'=' * 60}")
        print(f"用户: {q}")
        result = process_query(q)
        print(f"工具: {result['tool']} | 耗时: {result['elapsed']}s")
        print(f"答案:\n{result['answer'][:500]}")
