# -*- coding: utf-8 -*-
"""
文件功能：服务模块 —— 负责家庭记账本的核心业务流程编排与回复生成。

工单编号：人工智能NLP-Agent数字人项目-记账本任务

职责说明：
  1. 接收用户自然语言消息
  2. 调用 parser 模块进行意图识别和字段提取
  3. 根据意图类型调用 database 模块执行相应的数据操作
  4. 使用 LLM 生成自然、友好的回复（LLM 不可用时使用模板回复）
  5. 对不完整输入进行智能引导补充

业务流程覆盖：
  - record: 解析→入库→返回确认信息
  - query_detail: 解析→查询→格式化明细列表
  - query_summary: 解析→查询→统计汇总
  - query_purchase_day: 解析→查询→返回购买日期
  - delete + confirm_delete: 两步式安全删除
  - incomplete/invalid: 智能引导用户补充信息
"""

# ---------- 标准库导入 ----------
import logging
from typing import Any

# ---------- 项目内部导入 ----------
from 研发.database import LedgerDatabase
from 研发.llm_client import LLMClient
from 研发.parser import MessageParser

# 获取当前模块的 logger
logger = logging.getLogger("agent_work_order_1.service")


class LedgerService:
    """
    家庭记账业务服务类。

    协调 parser（解析）、database（存取）、llm_client（智能回复），
    是 Web 路由和底层数据之间的业务逻辑桥梁。
    """

    def __init__(self, database: LedgerDatabase, llm_client: LLMClient | None = None) -> None:
        """
        初始化服务实例。

        参数:
          database: 已初始化的 LedgerDatabase 实例
          llm_client: LLM 客户端实例（可选）
        """
        self.database = database
        self.llm = llm_client
        self.parser = MessageParser(llm_client=llm_client)
        self.pending_delete_id: int | None = None
        self.pending_update_id: int | None = None
        self.pending_update_fields: dict[str, Any] | None = None

    def handle_message(self, message: str) -> dict[str, Any]:
        """
        处理用户消息的主入口 —— 意图分发。

        参数:
          message: 用户输入的自然语言消息

        返回:
          包含 reply 和可选 data 的字典
        """
        logger.info("开始处理消息：%s", message)

        # Step 1: 解析意图
        parsed = self.parser.parse(message)
        intent = parsed.get("intent")
        logger.info("识别到意图：%s", intent)

        # Step 2: 按意图分发

        if intent == "record":
            return self._handle_record(parsed["record"], parsed.get("reply"))

        if intent == "query_purchase_day":
            return self._handle_purchase_day(parsed)

        if intent == "query_detail":
            return self._handle_detail(parsed)

        if intent == "query_summary":
            return self._handle_summary(parsed)

        if intent == "update":
            return self._prepare_update(parsed)

        if intent == "confirm_update":
            return self._confirm_update()

        if intent == "delete":
            return self._prepare_delete(parsed)

        if intent == "confirm_delete":
            return self._confirm_delete()

        # 兜底：invalid 或其他未识别意图
        logger.warning("未识别有效意图：%s", parsed)
        return {"reply": parsed.get("reply", "我没太理解你的意思~ 你可以试着说\"今天妈妈买菜花了50元\"这样的格式哦！")}

    def _handle_record(self, record: dict[str, Any], llm_reply: str | None = None) -> dict[str, Any]:
        """
        处理记账操作。

        参数:
          record: 结构化账目数据
          llm_reply: LLM 预生成的回复（如果有）

        返回:
          包含回复和数据的字典
        """
        # 防重复：同成员+同事項+同金额+同月 视为重复，不重复入库
        existing = self.database.find_records({
            "member": record.get("member"),
            "item_keyword": record.get("item_name"),
        })
        new_month = record.get("record_date", "")[:7]  # YYYY-MM
        for r in existing:
            same_month = r["record_date"][:7] == new_month if new_month else False
            if (same_month and
                abs(r["amount"] - record.get("amount", 0)) < 0.01):
                logger.info("检测到重复记录，跳过入库：%s", record)
                # PDF格式
                parts = record['record_date'].split('-')
                date_cn = f"{parts[0]}年{parts[1]}月{parts[2]}日" if len(parts) == 3 else record['record_date']
                symbol = "+" if record["action_type"] == "收入" else "-"
                reply = f"{date_cn}，{record['category']}，{record['item_name']}，{symbol}{record['amount']:.0f}元"
                return {"reply": reply, "data": record}

        record_id = self.database.add_record(record)

        # 优先使用 LLM 生成的回复，否则用 PDF 格式
        if llm_reply:
            reply = llm_reply
        else:
            # PDF格式：YYYY年MM月DD日，类别，事项，+/-金额元
            symbol = "+" if record["action_type"] == "收入" else "-"
            parts = record['record_date'].split('-')
            date_cn = f"{parts[0]}年{parts[1]}月{parts[2]}日" if len(parts) == 3 else record['record_date']
            reply = f"{date_cn}，{record['category']}，{record['item_name']}，{symbol}{record['amount']:.0f}元"

        logger.info("记账完成：record_id=%s", record_id)
        return {"reply": reply, "data": record}

    def _handle_purchase_day(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """处理购买日期查询。"""
        records = self.database.find_records({
            "member": parsed.get("member"),
            "item_keyword": parsed.get("item_keyword"),
            "action_type": "支出",
        })

        if not records:
            logger.info("未查到购买日期记录：%s", parsed)
            return {"reply": f"没有查到{parsed.get('member', '')}购买\"{parsed.get('item_keyword', '')}\"的记录。"}

        first_record = records[0]
        # PDF格式：YYYY年MM月DD日购买《事项名》花费金额元
        parts = first_record['record_date'].split('-')
        date_cn = f"{parts[0]}年{parts[1]}月{parts[2]}日" if len(parts) == 3 else first_record['record_date']
        reply = f"{date_cn}购买《{first_record['item_name']}》花费{first_record['amount']:.0f}元"

        logger.info("购买日期查询成功：record_id=%s", first_record["id"])
        return {"reply": reply, "data": records}

    def _handle_detail(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """处理明细查询。"""
        records = self.database.find_records(parsed)

        if not records:
            logger.info("明细查询为空：%s", parsed)
            return {"reply": "这个范围内还没有账目记录哦~"}

        lines = []
        for record in records:
            parts = record['record_date'].split('-')
            date_cn = f"{parts[0]}年{parts[1]}月{parts[2]}日" if len(parts) == 3 else record['record_date']
            sign = "+" if record["action_type"] == "收入" else "-"
            lines.append(
                f"{date_cn} | {record['member']} | {record['category']} | "
                f"{record['item_name']} | {sign}{record['amount']:.0f}元"
            )

        # 计算总额
        total = sum(float(r["amount"]) for r in records)
        header = "本月家庭账目明细如下："
        footer = f"\n共计 {len(records)} 笔，合计 {total:.0f} 元"

        logger.info("明细查询成功：count=%s", len(records))
        return {"reply": header + "\n" + "\n".join(lines) + footer, "data": records}

    def _handle_summary(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """
        处理汇总查询。

        支持三种汇总类型：
          1. 按成员+支出汇总（"这个月女儿花了多少钱"）
          2. 按关键词汇总
          3. 全局汇总
        """
        records = self.database.find_records(parsed)

        if not records:
            logger.info("汇总查询为空：%s", parsed)
            return {"reply": "没有查到符合条件的账目哦~"}

        total_amount = sum(float(record["amount"]) for record in records)

        # 获取月份显示文本
        month_prefix = parsed.get("month_prefix")
        if month_prefix:
            month_text = self.parser.get_month_range_text(month_prefix)
        else:
            month_text = self.parser.get_month_range_text(self.parser.now.strftime("%Y-%m"))

        # ---- 汇总类型 1：某成员某月支出 ----
        if parsed.get("member") and parsed.get("action_type") == "支出":
            detail_lines = [
                f"{record['record_date']}：{record['item_name']} {record['amount']:.0f}元"
                for record in records
            ]
            reply = (
                f"根据您提供的信息，{month_text}{parsed['member']}的总支出金额为{total_amount:.0f}元。\n"
                f"具体支出项目如下：\n" + "\n".join(detail_lines)
            )
            logger.info("成员支出汇总成功：member=%s, total=%s", parsed["member"], total_amount)
            return {"reply": reply, "data": records}

        # ---- 汇总类型 2：按关键词 ----
        if parsed.get("item_keyword"):
            count = len(records)
            # PDF格式："自x~x，共买x本/双/个xx，共花费x元"
            unit = "条"
            kw = parsed['item_keyword']
            if "书" in kw: unit = "本"
            elif "鞋" in kw: unit = "双"
            elif any(w in kw for w in ["菜","饭","咖啡"]): unit = "份"
            reply = f"自{month_text}，共买{count}{unit}{kw}，共花费{total_amount:.0f}元。"
            logger.info("关键词汇总成功：keyword=%s, total=%s", parsed["item_keyword"], total_amount)
            return {"reply": reply, "data": records}

        # ---- 汇总类型 3：全局 ----
        income_count = len([r for r in records if r["action_type"] == "收入"])
        expense_count = len([r for r in records if r["action_type"] == "支出"])
        reply = (
            f"自{month_text}，共{len(records)}笔账目，其中收入{income_count}笔，支出{expense_count}笔，"
            f"合计金额{total_amount:.0f}元。"
        )
        logger.info("全局汇总成功：count=%s, total=%s", len(records), total_amount)
        return {"reply": reply, "data": records}

    def _prepare_update(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """修改操作第一步：匹配并确认。"""
        record_id = parsed.get("record_id")
        update_fields = parsed.get("update_fields", {})

        if not record_id:
            return {"reply": "请指定要修改的记录编号，如「修改记录1 金额改为100元」。"}

        record = self.database.get_record_by_id(record_id)
        if not record:
            return {"reply": f"没有找到编号 #{record_id} 的记录哦~"}

        if not update_fields:
            return {"reply": "我没看清要修改什么，请说具体一点~"}

        self.pending_update_id = int(record["id"])
        self.pending_update_fields = update_fields

        changes = []
        for field, new_val in update_fields.items():
            old_val = record.get(field, "")
            changes.append(f"  {field}：{old_val} → {new_val}")

        reply = (
            f"准备修改记录 #{record['id']}：{record['record_date']} {record['member']} {record['item_name']}\n"
            + "\n".join(changes) +
            "\n若确认修改，请回复「确认修改」。"
        )
        logger.info("修改待确认：id=%s", self.pending_update_id)
        return {"reply": reply}

    def _confirm_update(self) -> dict[str, Any]:
        """修改操作第二步：执行更新。"""
        if self.pending_update_id is None:
            return {"reply": "当前没有待确认修改的记录哦~"}

        success = self.database.update_record(self.pending_update_id, self.pending_update_fields or {})
        rid = self.pending_update_id
        self.pending_update_id = None
        self.pending_update_fields = None

        if not success:
            return {"reply": "修改失败，请重试。"}

        return {"reply": f"已修改记录 #{rid}！"}

    def _prepare_delete(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """删除操作第一步：匹配并确认。"""
        records = self.database.find_records(parsed)

        if not records:
            logger.info("删除目标不存在：%s", parsed)
            return {"reply": "没有找到你要删除的记录哦~ 请确认成员和事项名称是否正确。"}

        target = records[-1]
        self.pending_delete_id = int(target["id"])

        reply = (
            f"准备删除：{target['record_date']}，{target['member']}，{target['item_name']}，"
            f"{target['amount']:.0f}元。\n若确认删除，请回复\"确认删除\"。"
        )

        logger.info("删除待确认：record_id=%s", self.pending_delete_id)
        return {"reply": reply, "data": target}

    def _confirm_delete(self) -> dict[str, Any]:
        """删除操作第二步：执行删除。"""
        if self.pending_delete_id is None:
            logger.warning("收到删除确认，但没有待删除记录")
            return {"reply": "当前没有待确认删除的记录哦~"}

        record = self.database.get_record_by_id(self.pending_delete_id)
        success = self.database.delete_record(self.pending_delete_id)
        self.pending_delete_id = None

        if not success or not record:
            logger.error("删除失败")
            return {"reply": "删除失败，请重试。"}

        logger.info("删除成功：record_id=%s", record["id"])
        return {"reply": f"已删除：{record['record_date']}，{record['item_name']}，{record['amount']:.0f}元。"}
