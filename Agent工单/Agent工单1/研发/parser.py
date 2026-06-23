# -*- coding: utf-8 -*-
"""
文件功能：自然语言解析模块 —— 将用户的自然语言消息解析为结构化的记账操作指令。

工单编号：人工智能NLP-Agent数字人项目-记账本任务

职责说明：
  1. 优先使用 LLM（DeepSeek）进行智能意图识别和信息提取
  2. LLM 不可用时，自动降级为正则+关键词规则解析
  3. 支持模糊、口语化、生活化的表达方式（LLM 模式下）
  4. 智能分类：根据物品语义自动推断消费类别

意图类型：
  - record: 记账（如"今天女儿买了登山鞋499元"）
  - query_detail: 查询明细（如"看下这个月花钱明细"）
  - query_summary: 查询汇总（如"这个月女儿花了多少钱"）
  - query_purchase_day: 查询购买日期（如"我哪天买的三体"）
  - delete: 删除记录（如"删除女儿登山鞋的费用"）
  - confirm_delete: 确认删除（如"确认删除"）
  - incomplete: 信息不完整，需引导补充
  - chat: 闲聊/打招呼
"""

# ---------- 标准库导入 ----------
import calendar
import json
import logging
import re
from datetime import datetime
from typing import Any

# ---------- 项目内部导入 ----------
from 研发.llm_client import LLMClient

# 获取当前模块的 logger
logger = logging.getLogger("agent_work_order_1.parser")

# ---------- 家庭成员别名映射 ----------
MEMBER_ALIASES = {
    "爸爸": "爸爸", "父亲": "爸爸", "爸": "爸爸", "老爸": "爸爸",
    "妈妈": "妈妈", "母亲": "妈妈", "妈": "妈妈", "老妈": "妈妈",
    "女儿": "女儿", "闺女": "女儿", "丫头": "女儿", "孩子": "女儿",
    "我": "我", "自己": "我", "本人": "我",
}

# ---------- 消费类别关键词映射（正则降级时使用） ----------
CATEGORY_KEYWORDS = {
    "书": "买书", "鞋": "买鞋", "报销": "报销", "旅游": "旅游",
    "工资": "工资", "饭": "餐饮", "菜": "买菜", "车": "出行",
    "衣": "服饰", "药": "医疗", "课": "教育", "票": "出行",
    "电影": "娱乐", "手机": "数码", "油": "出行", "咖啡": "餐饮",
    "零食": "零食", "快递": "日用品", "水电": "家居", "房租": "家居",
}

# ---------- 收入关键词 ----------
INCOME_KEYWORDS = ["收到", "收入", "赚了", "报销", "工资", "奖金", "红包", "退款", "利息"]


class MessageParser:
    """
    自然语言解析器。

    工作模式：
      1. 优先调用 LLM 进行智能解析（支持口语化、模糊表达）
      2. LLM 返回无效结果时，自动降级为正则规则解析
    """

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        """
        初始化解析器。

        参数:
          llm_client: LLM 客户端实例（可选，为 None 时仅使用正则解析）
        """
        self.now = datetime.now()
        self.llm = llm_client

    def parse(self, message: str) -> dict[str, Any]:
        """
        统一意图识别入口。

        参数:
          message: 用户输入的自然语言消息

        返回:
          包含 intent 和对应字段的字典
        """
        text = message.strip()
        logger.info("开始解析消息：%s", text)

        # 空消息检查
        if not text:
            logger.warning("收到空消息")
            return {"intent": "invalid", "reply": "请输入账目信息，我来帮你记录~"}

        # 删除确认匹配（优先级最高）
        if text in {"确认修改", "确认更新"}:
            logger.info("识别到修改确认意图")
            return {"intent": "confirm_update"}

        if text in {"确认删除", "确认", "是", "好的", "删吧", "删"}:
            logger.info("识别到删除确认意图")
            return {"intent": "confirm_delete"}

        # ====== 优先使用 LLM 解析 ======
        if self.llm:
            llm_result = self._try_llm_parse(text)
            if llm_result:
                logger.info("LLM 解析成功：%s", llm_result.get("intent"))
                return llm_result
            logger.warning("LLM 解析失败，降级为正则解析")

        # ====== 降级：正则+关键词规则解析 ======
        return self._regex_parse(text)

    def _try_llm_parse(self, text: str) -> dict[str, Any] | None:
        """
        尝试使用 LLM 解析用户消息。

        返回:
          解析后的字典，失败返回 None
        """
        try:
            result = self.llm.parse_message(text)  # type: ignore[union-attr]
            if result is None:
                return None

            intent = result.get("intent", "")

            # ---- 记账意图：补充处理 ----
            if intent == "record" and "record" in result:
                record = result["record"]
                # 确保金额为浮点数
                if "amount" in record:
                    record["amount"] = float(record["amount"])
                # 如果 LLM 没给 reply，生成一个
                if not result.get("reply"):
                    symbol = "+" if record.get("action_type") == "收入" else "-"
                    result["reply"] = (
                        f"已记录：{record.get('record_date', '?')}，{record.get('member', '?')}，"
                        f"{record.get('category', '?')}，{record.get('item_name', '?')}，"
                        f"{symbol}{record.get('amount', 0):.0f}元"
                    )
                return result

            # ---- 修改/更新意图：直接返回 ----
            if intent in ("update", "confirm_update"):
                return result

            # ---- 查询/删除意图：直接返回 ----
            if intent in ("query_detail", "query_summary", "query_purchase_day", "delete"):
                # 确保 month_prefix 存在
                if intent in ("query_detail", "query_summary") and not result.get("month_prefix"):
                    result["month_prefix"] = self.now.strftime("%Y-%m")
                # LLM 未设 item_keyword 时，用正则兜底提取
                if intent in ("query_summary", "query_purchase_day", "delete") and not result.get("item_keyword"):
                    kw = self._extract_item_keyword(text)
                    if kw:
                        result["item_keyword"] = kw
                return result

            # ---- 信息不完整 ----
            if intent == "incomplete":
                return {
                    "intent": "invalid",
                    "reply": result.get("reply", "您的输入信息不完整，请补充后再试~"),
                }

            # ---- 闲聊/打招呼 ----
            if intent == "chat":
                return {
                    "intent": "invalid",
                    "reply": result.get("reply", "你好！我是小家记账，请告诉我你的账目需求~"),
                }

            logger.warning("LLM 返回未知意图：%s", intent)
            return None

        except Exception as e:
            logger.error("LLM 解析异常：%s", e)
            return None

    def _regex_parse(self, text: str) -> dict[str, Any]:
        """
        正则+关键词规则解析（LLM 降级方案）。

        参数:
          text: 用户输入文本

        返回:
          解析后的字典
        """
        # 修改意图
        if any(word in text for word in ["修改记录", "更新记录", "修改账目", "改记录"]) or            re.search(r"(修改|更新|更改|改成|改为).*\d+", text):
            result = self._parse_update(text)
            logger.info("正则识别到修改意图：%s", result)
            return result

        # 删除意图
        if any(word in text for word in ["删除", "删掉", "移除"]):
            result = self._parse_delete(text)
            logger.info("正则识别到删除意图：%s", result)
            return result

        # 查询意图
        if any(word in text for word in ["明细", "花了多少", "收入多少", "共花", "共收入", "哪天买的", "看下", "查看"]):
            result = self._parse_query(text)
            logger.info("正则识别到查询意图：%s", result)
            return result

        # 默认：尝试记账
        result = self._parse_record(text)
        logger.info("正则识别到记账意图：%s", result)
        return result

    def _parse_record(self, text: str) -> dict[str, Any]:
        """解析记账语句。"""
        amount_match = re.search(r"(\d+(?:\.\d+)?)\s*元", text)
        if not amount_match:
            return {"intent": "invalid", "reply": "我没看到金额，请按\"谁做什么花了多少钱\"的格式再说一次~"}

        member = self._extract_member(text)
        if not member:
            return {"intent": "invalid", "reply": "我没看清是谁的账，请补充是爸爸、妈妈、女儿还是您自己？"}

        record_date = self._extract_date(text)
        if not record_date:
            return {"intent": "invalid", "reply": "我没看清日期，请补充具体日期，比如\"7月5日\"或\"今天\"~"}

        action_type = "收入" if any(word in text for word in INCOME_KEYWORDS) else "支出"
        item_name = self._extract_item_name(text)
        category = self._extract_category(text, item_name)
        amount = float(amount_match.group(1))

        return {
            "intent": "record",
            "record": {
                "record_date": record_date,
                "member": member,
                "action_type": action_type,
                "category": category,
                "item_name": item_name,
                "amount": amount,
            },
        }

    def _parse_query(self, text: str) -> dict[str, Any]:
        """解析查询语句。"""
        member = self._extract_member(text)
        month_prefix = self._extract_month_prefix(text)
        item_keyword = self._extract_item_keyword(text)

        # 只有纯成员汇总查询（无具体物品）才清除 item_keyword
        # "女儿花了多少钱" → 成员汇总；"买书花了多钱" → 关键词汇总
        if any(word in text for word in ["花了多少", "收入多少", "共花", "共收入"]):
            # 如果文本中有具体物品（买X），保留关键词
            if not re.search(r"买[了过]?\S", text):
                item_keyword = None

        action_type = None
        if "收入" in text or "报销" in text:
            action_type = "收入"
        if any(word in text for word in ["花", "支出", "买", "费用"]):
            action_type = "支出"

        if "哪天买的" in text:
            return {"intent": "query_purchase_day", "member": member, "item_keyword": item_keyword}

        if any(word in text for word in ["明细", "看下", "查看"]):
            return {"intent": "query_detail", "member": member, "month_prefix": month_prefix, "action_type": action_type}

        return {"intent": "query_summary", "member": member, "month_prefix": month_prefix, "item_keyword": item_keyword, "action_type": action_type}

    def _parse_update(self, text: str) -> dict[str, Any]:
        """解析修改语句。"""
        # 提取记录编号
        id_match = re.search(r"(\d+)", text)
        record_id = int(id_match.group(1)) if id_match else None

        update_fields = {}

        # 提取金额
        amount_match = re.search(r"(\d+(?:\.\d+)?)\s*元", text)
        if amount_match:
            update_fields["amount"] = float(amount_match.group(1))

        # 提取成员
        member = self._extract_member(text)
        if member:
            update_fields["member"] = member

        # 提取日期
        date = self._extract_date(text)
        if date:
            update_fields["record_date"] = date

        # 提取事项
        if "事项" in text or "内容" in text or "改为" in text or "改成" in text:
            # Try to extract what comes after 改为/改成
            content_match = re.search(r"[改为改成更新]+(.+?)(?:$|[,，。;；])", text)
            if content_match:
                item = content_match.group(1).strip()
                if item and len(item) > 1:
                    update_fields["item_name"] = item

        return {
            "intent": "update",
            "record_id": record_id,
            "update_fields": update_fields,
        }

    def _parse_delete(self, text: str) -> dict[str, Any]:
        """解析删除语句。"""
        return {
            "intent": "delete",
            "member": self._extract_member(text),
            "item_keyword": self._extract_item_keyword(text),
            "month_prefix": self._extract_month_prefix(text),
        }

    def _extract_member(self, text: str) -> str | None:
        """从文本中提取家庭成员。"""
        for alias, standard_name in MEMBER_ALIASES.items():
            if alias in text:
                return standard_name
        return None

    def _extract_date(self, text: str) -> str | None:
        """从文本中提取日期，返回 YYYY-MM-DD 格式。"""
        if "今天" in text:
            return self.now.strftime("%Y-%m-%d")

        full_match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
        if full_match:
            year, month, day = map(int, full_match.groups())
            return f"{year:04d}-{month:02d}-{day:02d}"

        month_day_match = re.search(r"(\d{1,2})月(\d{1,2})日", text)
        if month_day_match:
            month, day = map(int, month_day_match.groups())
            return f"{self.now.year:04d}-{month:02d}-{day:02d}"

        return None

    def _extract_month_prefix(self, text: str) -> str | None:
        """提取月份前缀，返回 YYYY-MM 格式。"""
        if "这个月" in text or "本月" in text:
            return self.now.strftime("%Y-%m")

        month_match = re.search(r"(\d{4})年(\d{1,2})月", text)
        if month_match:
            year, month = map(int, month_match.groups())
            return f"{year:04d}-{month:02d}"

        month_only_match = re.search(r"(\d{1,2})月", text)
        if month_only_match:
            month = int(month_only_match.group(1))
            return f"{self.now.year:04d}-{month:02d}"

        return self.now.strftime("%Y-%m")

    def _extract_item_name(self, text: str) -> str:
        """从记账文本中提取事项名称。"""
        cleaned_text = re.sub(r"\d+(?:\.\d+)?\s*元", "", text)
        cleaned_text = re.sub(r"\d{4}年\d{1,2}月\d{1,2}日", "", cleaned_text)
        cleaned_text = re.sub(r"\d{1,2}月\d{1,2}日", "", cleaned_text)
        cleaned_text = cleaned_text.replace("今天", "")

        for word in ["爸爸", "妈妈", "女儿", "我", "自己", "花了", "买了", "收到", "报销", "收入", "支出", "一双", "一本", "一个", "了", "的"]:
            cleaned_text = cleaned_text.replace(word, " ")

        parts = [part.strip(" ，。？?！!的了") for part in cleaned_text.split() if part.strip(" ，。？?！!的了")]

        if not parts:
            return "未命名事项"

        return parts[-1]

    def _extract_category(self, text: str, item_name: str) -> str:
        """根据关键词推断消费类别。"""
        for keyword, category in CATEGORY_KEYWORDS.items():
            if keyword in text or keyword in item_name:
                return category
        return "日常记账"

    def _extract_item_keyword(self, text: str) -> str | None:
        """从查询/删除语句中提取事项关键词。"""
        patterns = [
            r"买的(.+?)$",
            r"删除(?:了)?(?:爸爸|妈妈|女儿|我|自己)?(.+?)(?:的费用|这条|记录)?$",
            r"我哪天买的(.+?)$",
            r"报旅游团",  # 特殊处理"报旅游团"
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                if pattern == r"报旅游团":
                    return "旅游团"
                return match.group(1).strip("，。？? ")

        for keyword in CATEGORY_KEYWORDS:
            if keyword in text:
                return keyword
        return None

    def get_month_range_text(self, month_prefix: str) -> str:
        """将月份前缀转为自然语言日期区间。"""
        year, month = [int(part) for part in month_prefix.split("-")]
        last_day = calendar.monthrange(year, month)[1]
        return f"{year}年{month}月1日~{year}年{month}月{last_day}日"
