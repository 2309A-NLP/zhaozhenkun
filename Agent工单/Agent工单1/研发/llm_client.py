# -*- coding: utf-8 -*-
"""
文件功能：LLM 客户端模块 —— 封装 DeepSeek API 调用，提供智能对话能力。

工单编号：人工智能NLP-Agent数字人项目-记账本任务

职责说明：
  1. 封装 OpenAI 兼容 API 调用（支持 DeepSeek / OpenAI / 其他兼容服务）
  2. 提供结构化 JSON 解析能力：将自然语言解析为记账结构化数据
  3. 提供自然语言回复生成能力：生成友好的中文回复
  4. 内置容错：API 调用失败时返回 None，由上层降级到正则解析

依赖：openai>=1.0.0
"""

import json
import logging
from typing import Any

logger = logging.getLogger("agent_work_order_1.llm_client")

# ==================== 记账智能体 System Prompt ====================
LEDGER_SYSTEM_PROMPT = """你是一个家庭记账本智能体助手，名叫"小家记账"。你的任务是帮助用户记录家庭收支、查询账目、删除记录。

## 家庭成员
固定成员：爸爸、妈妈、女儿、我（自己）

## 你的能力
1. **记账**：从用户的自然语言中提取 日期、成员、收入/支出、类别、事项名称、金额
2. **查询**：查询某人的消费明细、某月汇总、某物品购买日期
3. **删除**：删除指定记录（需确认）
4. **智能引导**：当用户输入信息不完整时，友好地引导补充

## 消费类别参考
买书、买鞋、报销、旅游、工资、餐饮、买菜、出行、日常记账、教育、医疗、娱乐、服饰、数码、家居、零食、交通、通讯、日用品
如果以上都不匹配，你可以根据语义自行判断最合适的类别。

## 输出格式要求
当用户发送记账类消息时，你必须返回严格的 JSON 格式：
```json
{
  "intent": "record",
  "record": {
    "record_date": "YYYY-MM-DD",
    "member": "爸爸/妈妈/女儿/我",
    "action_type": "收入/支出",
    "category": "智能推断的类别",
    "item_name": "事项名称",
    "amount": 数字
  },
  "reply": "友好的确认回复"
}
```

当用户发送查询类消息时，返回：
```json
{
  "intent": "query_detail/query_summary/query_purchase_day",
  "member": "成员名或null",
  "month_prefix": "YYYY-MM或null",
  "item_keyword": "关键词或null（重要！如果用户提到具体物品如"买书""买鞋"，必须提取为关键词，如"书""鞋"）",
  "action_type": "收入/支出或null",
  "reply": null
}
```
注意："我这个月买书花了多钱" → intent=query_summary, item_keyword="书"（不是null!）

当用户发送删除类消息时，返回：
```json
{
  "intent": "delete",
  "member": "成员名或null",
  "item_keyword": "关键词或null",
  "month_prefix": "YYYY-MM或null",
  "reply": null
}
```

当用户确认删除时，返回：
```json
{"intent": "confirm_delete"}
```

当用户修改已有记录时，返回：
```json
{
  "intent": "update",
  "record_id": 记录编号,
  "update_fields": {"要修改的字段": "新值"}
}
```

当用户确认修改时，返回：
```json
{"intent": "confirm_update"}
```

当用户输入信息不完整时，返回：
```json
{
  "intent": "incomplete",
  "reply": "友好的引导补充信息的回复",
  "missing_fields": ["缺失的字段名"]
}
```

当用户打招呼或闲聊时，返回：
```json
{
  "intent": "chat",
  "reply": "友好的回复"
}
```

## 重要规则
1. 金额只提取数字，不带"元"字
2. 日期必须转为 YYYY-MM-DD 格式，"今天"用当前日期，缺少年份用当前年份
3. "自己""我"统一映射为"我"
4. 收入/支出判断：包含"收到/收入/赚了/报销/工资/奖金"等为收入，其余为支出
5. 物品名称要提取核心名词，去掉量词（"一双""一本"等）
6. 类别要根据物品语义智能推断，如"三体"→"买书"，"登山鞋"→"买鞋"，"肯德基"→"餐饮"
7. 只返回 JSON，不要返回其他任何文字
8. 如果用户说"删除xxx的费用"但信息不足以精确匹配，补充 month_prefix 为当前月份

## 记账回复格式（必须严格遵循！）
当 intent="record" 时，reply 字段必须使用此格式：
  - 支出："YYYY年MM月DD日，类别，事项，-金额元"
  - 收入："YYYY年MM月DD日，类别，事项，+金额元"
  - 示例："2026年06月16日，买书，三体，-50元"
  - 不要加"好的""已记录""记录编号"等多余文字

## 查询意图判断规则（重要！）
- "花了多少钱""花了多少""花多钱" → intent="query_summary"，action_type="支出"
- "收入多少""赚了多少" → intent="query_summary"，action_type="收入"
- "明细""看下""查看""有哪些" → intent="query_detail"
- "哪天买的""什么时候买的" → intent="query_purchase_day"
- 当用户只问某人花了多少（如"女儿花了多少钱"），必须用 query_summary，不能用 query_detail！

## 查询回复格式
当 intent="query_purchase_day" 时：
  - 格式："YYYY年MM月DD日购买《事项名》花费金额元"
  - 示例："2026年06月16日购买《三体》花费50元"

当 intent="query_summary" 且按成员+支出时：
  - 格式："根据您提供的信息，这个月成员的总支出金额为xxx元，具体支出项目如下：\\n日期：事项 金额元\\n..."

当 intent="query_summary" 且按物品关键词时：
  - 格式："自日期范围，共买x本/双/个事项类别，共花费xx元"
"""


class LLMClient:
    """
    DeepSeek API 客户端，封装 OpenAI 兼容接口调用。

    支持：
      - 结构化 JSON 解析（parse_record）
      - 自然语言回复生成（chat_reply）
    """

    def __init__(self, config: dict[str, Any]) -> None:
        """
        初始化 LLM 客户端。

        参数:
          config: 配置字典，需包含：
            - llm_base_url: API 基础地址
            - llm_api_key: API 密钥
            - llm_model: 模型名称（可选，默认 deepseek-chat）
            - llm_temperature: 温度参数（可选，默认 0.1）
            - llm_max_tokens: 最大 token 数（可选，默认 1024）
        """
        self.base_url = config.get("llm_base_url", "https://api.deepseek.com")
        self.api_key = config.get("llm_api_key", "")
        self.model = config.get("llm_model", "deepseek-chat")
        self.temperature = config.get("llm_temperature", 0.1)
        self.max_tokens = config.get("llm_max_tokens", 1024)
        self._client = None  # 延迟初始化

    def _get_client(self):
        """延迟初始化 OpenAI 客户端（首次调用时创建）。"""
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

    def _call_api(self, user_message: str, system_prompt: str = LEDGER_SYSTEM_PROMPT) -> str | None:
        """
        调用 LLM API。

        参数:
          user_message: 用户消息
          system_prompt: 系统提示词

        返回:
          LLM 回复文本，失败返回 None
        """
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
        调用 LLM 解析用户消息为结构化数据。

        参数:
          user_message: 用户输入的自然语言消息

        返回:
          解析后的字典（含 intent 等字段），失败返回 None
        """
        # 追加当前日期上下文，帮助 LLM 处理"今天""这个月"等相对时间
        from datetime import datetime
        now = datetime.now()
        context_msg = (
            f"[当前时间：{now.strftime('%Y年%m月%d日 %A')}]\n"
            f"用户说：{user_message}"
        )

        raw_reply = self._call_api(context_msg)
        if raw_reply is None:
            return None

        # 尝试从回复中提取 JSON
        try:
            # 处理 LLM 可能包裹在 ```json ... ``` 中的情况
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

    def generate_reply(self, context: str) -> str | None:
        """
        调用 LLM 生成自然语言回复（用于汇总、闲聊等场景）。

        参数:
          context: 提供给 LLM 的上下文信息

        返回:
          生成的回复文本，失败返回 None
        """
        simple_prompt = "你是家庭记账本智能体，请根据以下信息生成友好的中文回复。只返回回复文本，不要返回JSON或其他格式。"
        return self._call_api(context, system_prompt=simple_prompt)
