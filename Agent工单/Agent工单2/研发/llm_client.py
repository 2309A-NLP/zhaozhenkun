# -*- coding: utf-8 -*-
"""
文件功能：LLM 客户端模块 —— 封装 DeepSeek API 调用，提供智能日程解析能力。

职责说明：
  1. 封装 OpenAI 兼容 API 调用（支持 DeepSeek / OpenAI / 其他兼容服务）
  2. 提供结构化 JSON 解析能力：将自然语言解析为日程操作结构化数据
  3. 内置容错：API 调用失败时返回 None，由上层降级到正则解析

依赖：openai>=1.0.0
"""

import json
import logging
from typing import Any

logger = logging.getLogger("agent_work_order_2.llm_client")

# ==================== 日程提醒智能体 System Prompt ====================
SCHEDULE_SYSTEM_PROMPT = """你是一个日程提醒智能体助手，帮助用户管理日常日程。你的任务是理解用户的自然语言输入，解析为结构化的日程操作指令。

## 你的能力
1. **添加日程**：从用户的自然语言中提取 时间、日期、事项内容、重复规则
2. **查询日程**：查询今天/明天/全部的日程安排
3. **删除日程**：按编号或关键词删除指定日程
4. **修改日程**：修改已有日程的时间/日期/内容/重复规则

## 输出格式要求

### 添加日程
当用户说添加/记录日程时，返回：
```json
{
  "intent": "add",
  "schedule": {
    "schedule_time": "HH:MM",
    "schedule_date": "YYYY-MM-DD",
    "content": "事项内容",
    "repeat_rule": "none/daily/weekly/monthly",
    "repeat_detail": ""
  }
}
```
- schedule_time：24小时制，如 "17:00"、"08:30"
- schedule_date：YYYY-MM-DD 格式，"今天"用当前日期，"明天"=当前日期+1天，"后天"=当前日期+2天，"周X"=本周对应的日期，缺少年份用当前年份，缺少日期用今天
- content：纯事项描述，去掉时间词、日期词，保留核心事项
- repeat_rule：none=不重复，daily=每天，weekly=每周，monthly=每月
- repeat_detail：weekly 时填星期几英文（Monday/Tuesday/...），monthly 时填几号（1-31），否则留空

### 查询日程
当用户问"有什么日程""今天的安排""日程列表"等时，返回：
```json
{
  "intent": "query",
  "schedule_date": "YYYY-MM-DD 或 null"
}
```
- 问"今天"→当天日期，"明天"→明天日期，"全部/所有"→null

### 删除日程
当用户说删除/取消日程时，返回：
```json
{
  "intent": "delete",
  "schedule_id": 编号 或 null,
  "keyword": "关键词 或 null"
}
```
- 有编号如"删除日程3"→schedule_id=3
- 无编号如"删除开会的日程"→keyword="开会"

### 确认删除
当用户说"确认删除""确认""好的"（且前面刚提过删除）时，返回：
```json
{"intent": "confirm_delete"}
```

### 修改日程
当用户说修改/更新/改日程时，返回：
```json
{
  "intent": "update",
  "schedule_id": 编号,
  "update_fields": {"要修改的字段": "新值"}
}
```
- 字段名：schedule_time / schedule_date / content / repeat_rule / repeat_detail
- 例："修改日程1时间改为下午3点" → schedule_id=1, update_fields={"schedule_time": "15:00"}

### 确认修改
当用户说"确认修改"时，返回：
```json
{"intent": "confirm_update"}
```

### 无法理解
当用户输入无法解析时，返回：
```json
{
  "intent": "invalid",
  "reply": "友好的引导提示"
}
```

## 重要规则
1. 时间统一为24小时制 HH:MM，"下午5点"→"17:00"，"上午9点"→"09:00"，"早上8点"→"08:00"
2. 日期统一为 YYYY-MM-DD，使用当前时间上下文推断相对日期
3. 事项内容要提取核心描述，去掉"提醒我""帮我把""日程""添加"等元词
4. "每天早上8点"→repeat_rule="daily"；"每周一上午9点"→repeat_rule="weekly",repeat_detail="Monday"；"每月5号下午2点"→repeat_rule="monthly",repeat_detail="5"
5. 只返回 JSON，不要返回其他任何文字
"""


class LLMClient:
    """
    DeepSeek API 客户端，封装 OpenAI 兼容接口调用。

    支持：
      - 结构化 JSON 解析（parse_message）
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self.base_url = config.get("llm_base_url", "https://api.deepseek.com")
        self.api_key = config.get("llm_api_key", "")
        self.model = config.get("llm_model", "deepseek-chat")
        self.temperature = config.get("llm_temperature", 0.1)
        self.max_tokens = config.get("llm_max_tokens", 1024)
        self._client = None

    def _get_client(self):
        """延迟初始化 OpenAI 客户端。"""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    base_url=self.base_url,
                    api_key=self.api_key,
                )
                logger.info("LLM 客户端初始化成功：model=%s, base_url=%s", self.model, self.base_url)
            except ImportError:
                logger.error("未安装 openai 库，请执行: pip install openai")
                return None
            except Exception as e:
                logger.error("LLM 客户端初始化失败：%s", e)
                return None
        return self._client

    def _call_api(self, user_message: str, system_prompt: str = SCHEDULE_SYSTEM_PROMPT) -> str | None:
        """调用 LLM API，返回回复文本。失败返回 None。"""
        client = self._get_client()
        if client is None:
            return None

        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            content = response.choices[0].message.content
            reply = content.strip() if content else ""
            logger.info("LLM 回复成功，长度=%d", len(reply))
            return reply
        except Exception as e:
            logger.error("LLM API 调用失败：%s", e)
            return None

    def parse_message(self, user_message: str) -> dict[str, Any] | None:
        """
        调用 LLM 解析用户消息为日程操作结构化数据。

        返回:
          解析后的字典（含 intent 等字段），失败返回 None
        """
        from datetime import datetime
        now = datetime.now()
        context_msg = (
            f"[当前时间：{now.strftime('%Y年%m月%d日 %A %H:%M')}]\n"
            f"用户说：{user_message}"
        )

        raw_reply = self._call_api(context_msg)
        if raw_reply is None:
            return None

        try:
            json_str = raw_reply
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()

            result = json.loads(json_str)
            logger.info("LLM 解析成功：%s", result.get("intent"))
            return result
        except json.JSONDecodeError as e:
            logger.warning("LLM 返回非 JSON 格式：%s, 原始回复：%s", e, raw_reply[:200])
            return None
