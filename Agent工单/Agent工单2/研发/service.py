# -*- coding: utf-8 -*-
"""
文件功能：服务模块 —— 负责日程提醒智能体的核心业务流程编排与回复生成。

职责说明：
  1. 接收用户自然语言消息
  2. 调用 parser 模块进行意图识别和字段提取
  3. 根据意图类型调用 database 模块执行相应数据操作
  4. 将结果格式化为用户友好的回复文本

业务流程覆盖：
  - add: 解析→入库→返回确认（含重复规则描述）
  - query: 解析→查询→格式化日程列表
  - delete: 按编号匹配→确认→执行软删除
  - delete_by_keyword: 按关键词匹配→（单条）确认 /（多条）列出
  - confirm_delete: 两步式安全删除的第二步
  - get_welcome: 根据当前时段生成个性化欢迎语

设计要点：
  - pending_delete_id 保存待确认删除的记录 ID，避免误删
  - 所有异常统一捕获，确保不因单条失败导致服务崩溃

项目背景：
  工单编号：人工智能 NLP-Agent 数字人项目-日程提醒智能体任务
"""

# ---------- 标准库导入 ----------
import logging      # 日志记录
import traceback    # 打印异常堆栈
from datetime import datetime  # 获取当前时间（用于欢迎语时段判断）
from typing import Any          # 通用类型注解

# ---------- 项目内部导入 ----------
from 研发.database import ScheduleDatabase  # 日程数据库操作类
from 研发.parser import ScheduleParser      # 日程自然语言解析器

# 获取当前模块的 logger
logger = logging.getLogger("agent_work_order_2.service")


class ScheduleService:
    """
    日程提醒业务服务类。

    作为控制层，协调 parser（解析）和 database（存取），
    是 Web 路由和底层数据之间的业务逻辑桥梁。
    """

    def __init__(self, database: ScheduleDatabase, llm_client=None) -> None:
        """
        初始化服务实例。

        参数:
          database: 已初始化的 ScheduleDatabase 实例
          llm_client: LLM 客户端实例（可选，为 None 时仅使用正则解析）
        """
        logger.info("初始化业务服务模块...")
        # 保存数据库操作实例
        self.database = database
        # 创建自然语言解析器实例（传入 LLM 客户端）
        self.parser = ScheduleParser(llm_client=llm_client)
        # 待确认删除的日程 ID（两步式删除的中间状态）
        # None 表示当前没有待确认的删除操作
        self.pending_delete_id: int | None = None
        # 待确认修改的日程 ID 和修改字段（两步式修改的中间状态）
        self.pending_update_id: int | None = None
        self.pending_update_fields: dict[str, Any] | None = None
        if llm_client:
            logger.info("业务服务模块初始化完成（LLM 模式）")
        else:
            logger.info("业务服务模块初始化完成（正则模式）")

    def handle_message(self, message: str) -> dict[str, Any]:
        """
        处理用户消息的主入口 —— 意图分发。

        流程：
          1. 调用 parser.parse() 进行意图识别
          2. 根据 intent 分发到对应 handler
          3. 统一异常捕获，确保总是返回有效的回复

        参数:
          message: 用户输入的自然语言消息

        返回:
          包含 reply（回复文本）和可选 data（结构化数据）的字典
        """
        logger.info("【服务入口】收到消息：%s", message[:120])

        # Step 1：解析消息
        try:
            parsed = self.parser.parse(message)
        except Exception as e:
            logger.error("【服务异常】解析失败：%s", e)
            logger.debug("异常堆栈：%s", traceback.format_exc())
            return {"reply": "抱歉，我没能理解你的意思，请换一种说法试试。"}

        intent = parsed.get("intent")
        logger.info("【服务路由】意图=%s", intent)

        # Step 2：按意图分发处理
        try:
            if intent == "add":
                result = self._handle_add(parsed["schedule"])
            elif intent == "query":
                result = self._handle_query(parsed)
            elif intent == "update":
                result = self._prepare_update(parsed)
            elif intent == "confirm_update":
                result = self._confirm_update()
            elif intent == "delete":
                result = self._prepare_delete(parsed)
            elif intent == "delete_by_keyword":
                result = self._prepare_delete_by_keyword(parsed)
            elif intent == "confirm_delete":
                result = self._confirm_delete()
            elif intent == "invalid":
                # 解析器已经生成了错误提示
                result = {"reply": parsed.get("reply", "我没理解你的意思，请换一种说法。")}
            else:
                logger.warning("【服务路由】未处理的意图：%s", intent)
                result = {"reply": "我没理解你的意思。你可以说「添加日程：下午5点开会」试试。"}
        except Exception as e:
            logger.error("【服务异常】处理意图 %s 时出错：%s", intent, e)
            logger.debug("异常堆栈：%s", traceback.format_exc())
            result = {"reply": "处理出错了，请再试一次。"}

        logger.info("【服务出口】回复：%s", result.get("reply", "")[:100])
        return result

    def _handle_add(self, schedule: dict[str, Any]) -> dict[str, Any]:
        """
        处理添加日程操作：将解析后的日程数据存入数据库。

        参数:
          schedule: 包含 schedule_time / schedule_date / content / repeat_rule / repeat_detail 的字典

        返回:
          包含回复文本和原始数据的字典
        """
        logger.info("【添加日程】开始处理：%s", schedule.get("content"))
        logger.debug("【添加日程】完整数据：%s", schedule)

        # 防重复：同内容+同时间+同重复规则 不入库
        today = schedule.get("schedule_date", "")
        existing = self.database.find_schedules({"schedule_date": today})
        for r in existing:
            if (r["schedule_time"] == schedule.get("schedule_time") and
                r["content"] == schedule.get("content") and
                r.get("repeat_rule", "none") == schedule.get("repeat_rule", "none")):
                logger.info("【添加日程】重复记录，跳过入库")
                return {"reply": f"日程已存在：{schedule['schedule_time']}|{r['id']:07d}|{schedule['content']}", "data": schedule}

        # 写入数据库
        try:
            record_id = self.database.add_schedule(schedule)
        except Exception as e:
            logger.error("【添加日程】数据库写入失败：%s", e)
            return {"reply": "日程记录失败，请重试。"}

        # PDF格式：简洁确认
        reply = f"已记录：{schedule['schedule_time']}|{record_id:07d}|{schedule['content']}"
        logger.info("【添加日程】成功：id=%s, reply=%s", record_id, reply)
        return {"reply": reply, "data": schedule}

    def _prepare_update(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """
        修改操作第一步：按照日程编号匹配目标记录，展示修改预览。

        参数:
          parsed: 包含 schedule_id 和 update_fields 的解析结果

        返回:
          提示用户确认修改的回复

        安全设计：
          1. 先通过 ID 查询匹配记录
          2. 展示修改前后的对比
          3. 将修改信息存入待确认状态等待确认
        """
        schedule_id = parsed.get("schedule_id")
        update_fields = parsed.get("update_fields", {})
        logger.info("【修改确认】开始：id=%s, fields=%s", schedule_id, list(update_fields.keys()))

        # 检查是否提供了编号
        if not schedule_id:
            logger.warning("【修改确认】未指定日程编号")
            return {"reply": "请指定要修改的日程编号，如「修改日程1 时间改为下午3点」。"}

        # 查询日程是否存在且未被取消
        record = self.database.get_schedule_by_id(schedule_id)
        if not record or record.get("enabled") == 0:
            logger.info("【修改确认】日程不存在或已取消：id=%s", schedule_id)
            return {"reply": f"没有找到日程 #{schedule_id}，可能已经被删除了。"}

        # 检查是否有有效的修改字段
        if not update_fields:
            logger.warning("【修改确认】无修改字段")
            return {"reply": "我没看清要修改什么。你可以说「修改日程1 时间改为下午3点」试试。"}

        # 将目标 ID 和修改字段存入待确认状态
        self.pending_update_id = int(record["id"])
        self.pending_update_fields = update_fields

        # 生成修改前后对比描述
        field_cn_map = {
            "schedule_time": "时间",
            "schedule_date": "日期",
            "content": "内容",
            "repeat_rule": "重复规则",
            "repeat_detail": "重复细节",
        }
        changes = []
        for field, new_value in update_fields.items():
            old_value = record.get(field, "")
            cn_name = field_cn_map.get(field, field)
            # 特殊处理重复规则的可读性
            if field == "repeat_rule":
                rule_map = {"none": "不重复", "daily": "每天", "weekly": "每周", "monthly": "每月"}
                old_value = rule_map.get(str(old_value), str(old_value))
                new_value = rule_map.get(str(new_value), str(new_value))
            changes.append(f"  {cn_name}：{old_value} → {new_value}")

        # 拼接确认提示
        reply = (
            f"准备修改日程 #{record['id']}：{record.get('schedule_date', '')} {record['schedule_time']}"
            f" —— {record['content']}\n"
            f"修改内容：\n"
            + "\n".join(changes) +
            f"\n若确认修改，请回复「确认修改」。"
        )
        logger.info("【修改确认】待确认：id=%s, fields=%s",
                    self.pending_update_id, list(update_fields.keys()))
        return {"reply": reply, "data": {"old": record, "new": update_fields}}

    def _confirm_update(self) -> dict[str, Any]:
        """
        修改操作第二步：执行真正的字段更新。

        流程：
          1. 检查 pending_update_id 是否有效
          2. 查询记录（用于验证和成功提示）
          3. 执行 UPDATE
          4. 清除待确认状态

        返回:
          修改成功或失败的回复
        """
        logger.info("【执行修改】开始：pending_id=%s, fields=%s",
                    self.pending_update_id,
                    self.pending_update_fields.keys() if self.pending_update_fields else None)

        # 安全检查
        if self.pending_update_id is None or self.pending_update_fields is None:
            logger.warning("【执行修改】无待确认记录")
            return {"reply": "当前没有待确认修改的日程。"}

        # 先查询记录详情
        record = self.database.get_schedule_by_id(self.pending_update_id)
        if not record or record.get("enabled") == 0:
            pid = self.pending_update_id
            logger.info("【执行修改】日程已不存在：id=%s", pid)
            self.pending_update_id = None
            self.pending_update_fields = None
            return {"reply": f"日程 #{pid} 已经不存在了。"}

        # 执行更新
        try:
            success = self.database.update_schedule(
                self.pending_update_id, self.pending_update_fields
            )
        except Exception as e:
            logger.error("【执行修改】数据库操作失败：%s", e)
            return {"reply": "修改失败，请重试。"}

        # 提取信息用于回复，然后清除待确认状态
        updated_id = self.pending_update_id
        update_fields = self.pending_update_fields
        old_content = record.get("content", "")
        self.pending_update_id = None
        self.pending_update_fields = None

        # 处理结果
        if not success:
            logger.error("【执行修改】失败：id=%s", updated_id)
            return {"reply": "修改失败，请重试。"}

        # 生成成功回复
        field_cn_map = {
            "schedule_time": "时间",
            "schedule_date": "日期",
            "content": "内容",
            "repeat_rule": "重复规则",
        }
        changes_desc = []
        for field, new_value in update_fields.items():
            cn_name = field_cn_map.get(field, field)
            if field == "repeat_rule":
                rule_map = {"daily": "每天", "weekly": "每周", "monthly": "每月", "none": "不重复"}
                new_value = rule_map.get(str(new_value), str(new_value))
            changes_desc.append(f"{cn_name}已更新为「{new_value}」")

        reply = f"已修改日程 #{updated_id}（{old_content}）：" + "，".join(changes_desc)
        logger.info("【执行修改】成功：id=%s, reply=%s", updated_id, reply)
        return {"reply": reply}

    def _handle_query(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """
        处理查询日程：按日期或全部查询日程列表。

        参数:
          parsed: 包含 schedule_date 的解析结果

        返回:
          包含日程列表回复的字典
        """
        query_date = parsed.get("schedule_date")
        logger.info("【查询日程】开始：date=%s", query_date)

        # 按日期查询或查全部
        if query_date:
            conditions = {"schedule_date": query_date}
            records = self.database.find_schedules(conditions)
        else:
            records = self.database.find_all_schedules(include_disabled=False)

        logger.debug("【查询日程】查询到 %s 条记录", len(records))

        # 无记录时返回友好提示
        if not records:
            if query_date:
                logger.info("【查询日程】%s 无日程", query_date)
                return {"reply": f"{query_date} 暂无日程安排。"}
            logger.info("【查询日程】无任何日程")
            return {"reply": "当前没有任何日程记录。"}

        # 按需求文档图片格式拼接：您今天的日程包括：1. HH:MM 内容 2. HH:MM 内容 ...
        items = []
        for i, r in enumerate(records, 1):
            items.append(f"{i}. {r['schedule_time']} {r['content']}")

        # 拼接为一行，格式如：您今天的日程包括：1. 08:00 提醒您起床 2. 12:00 提醒您吃饭
        reply = "您今天的日程包括：" + " ".join(items)
        logger.info("【查询日程】完成：返回 %s 条日程", len(records))
        return {"reply": reply, "data": records}

    def _prepare_delete(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """
        删除操作第一步：按照日程编号匹配目标记录，返回确认提示。

        参数:
          parsed: 包含 schedule_id 的解析结果

        返回:
          提示用户确认删除的回复

        安全设计：
          1. 先通过 ID 查询匹配记录
          2. 展示完整信息给用户确认
          3. 将 ID 存入 pending_delete_id 等待确认
        """
        schedule_id = parsed.get("schedule_id")
        logger.info("【删除确认】开始：id=%s", schedule_id)

        # 检查是否提供了编号
        if not schedule_id:
            logger.warning("【删除确认】未指定日程编号")
            return {"reply": "请指定要删除的日程编号，如「删除日程1」。"}

        # 查询日程是否存在且未被取消
        record = self.database.get_schedule_by_id(schedule_id)
        if not record or record.get("enabled") == 0:
            logger.info("【删除确认】日程不存在或已取消：id=%s", schedule_id)
            return {"reply": f"没有找到日程 #{schedule_id}，可能已经被删除了。"}

        # 将目标 ID 存入待确认状态
        self.pending_delete_id = int(record["id"])

        # 拼接确认提示
        reply = (
            f"准备删除日程 {record['id']}："
            f"{record.get('schedule_date', '')} {record['schedule_time']}"
            f" —— {record['content']}。\n"
            f"若确认删除，请回复「确认删除」。"
        )
        logger.info("【删除确认】待确认：id=%s, content=%s", self.pending_delete_id, record.get("content"))
        return {"reply": reply, "data": record}

    def _prepare_delete_by_keyword(self, parsed: dict[str, Any]) -> dict[str, Any]:
        """
        按关键词匹配后删除确认。

        流程：
          - 匹配到 1 条 → 直接进入确认流程
          - 匹配到多条 → 列出所有匹配，让用户指定编号
          - 匹配到 0 条 → 提示未找到

        参数:
          parsed: 包含 keyword 的解析结果

        返回:
          确认提示或候选列表
        """
        keyword = parsed.get("keyword", "")
        logger.info("【删除(关键词)】开始：keyword=%s", keyword)

        # 模糊查询匹配的日程
        records = self.database.find_schedules({"content_keyword": keyword})
        logger.debug("【删除(关键词)】匹配到 %s 条", len(records))

        # 无匹配
        if not records:
            logger.info("【删除(关键词)】无匹配记录")
            return {"reply": f"没有找到包含「{keyword}」的日程。"}

        # 唯一匹配 → 直接确认
        if len(records) == 1:
            record = records[0]
            self.pending_delete_id = int(record["id"])
            reply = (
                f"找到一条日程 #{record['id']}："
                f"{record.get('schedule_date', '')} {record['schedule_time']}"
                f" —— {record['content']}。\n"
                f"若确认删除，请回复「确认删除」。"
            )
            logger.info("【删除(关键词)】唯一匹配：id=%s", record["id"])
            return {"reply": reply, "data": record}
        else:
            # 多条匹配 → 列出所有，让用户选
            lines = [f"找到 {len(records)} 条相关日程："]
            for r in records:
                lines.append(f"  #{r['id']} | {r['schedule_time']} | {r['content']}")
            lines.append("请指定编号删除，如「删除日程1」。")
            logger.info("【删除(关键词)】多条匹配：%s条", len(records))
            return {"reply": "\n".join(lines)}

    def _confirm_delete(self) -> dict[str, Any]:
        """
        删除操作第二步：执行真正的软删除（enabled = 0）。

        流程：
          1. 检查 pending_delete_id 是否有效
          2. 查询记录（用于成功提示）
          3. 执行 soft delete
          4. 清除待确认状态

        返回:
          删除成功或失败的回复
        """
        logger.info("【执行删除】开始：pending_id=%s", self.pending_delete_id)

        # 安全检查
        if self.pending_delete_id is None:
            logger.warning("【执行删除】无待确认记录")
            return {"reply": "当前没有待确认删除的日程。"}

        # 先查询记录详情
        record = self.database.get_schedule_by_id(self.pending_delete_id)
        if not record or record.get("enabled") == 0:
            pid = self.pending_delete_id
            logger.info("【执行删除】日程已不存在：id=%s", pid)
            self.pending_delete_id = None
            return {"reply": f"日程 #{pid} 已经不存在了。"}

        # 执行软删除（enabled = 0）
        try:
            success = self.database.disable_schedule(self.pending_delete_id)
        except Exception as e:
            logger.error("【执行删除】数据库操作失败：%s", e)
            return {"reply": "删除失败，请重试。"}

        # 提取信息用于回复，然后清除待确认状态
        deleted_id = self.pending_delete_id
        content = record.get("content", "")
        schedule_time = record.get("schedule_time", "")
        self.pending_delete_id = None

        # 处理结果
        if not success:
            logger.error("【执行删除】失败：id=%s", deleted_id)
            return {"reply": "删除失败，请重试。"}

        reply = f"已经删除日程 {deleted_id}，删除的日程内容是：{schedule_time} {content}"
        logger.info("【执行删除】成功：id=%s, reply=%s", deleted_id, reply)
        return {"reply": reply}

    def get_welcome(self) -> str:
        """
        根据当前时段生成个性化欢迎语。

        时段划分：
          - 0-6 点：夜深了
          - 6-9 点：早上好
          - 9-12 点：上午好
          - 12-14 点：中午好
          - 14-18 点：下午好
          - 18-24 点：晚上好

        返回:
          包含问候语、当前日期、使用说明的欢迎文本
        """
        logger.debug("生成欢迎语...")

        # 根据当前小时数判断时段并选择问候语
        now = datetime.now()
        hour = now.hour
        if hour < 6:
            greeting = "夜深了"
        elif hour < 9:
            greeting = "早上好"
        elif hour < 12:
            greeting = "上午好"
        elif hour < 14:
            greeting = "中午好"
        elif hour < 18:
            greeting = "下午好"
        else:
            greeting = "晚上好"
        logger.debug("当前时段：%s点 → %s", hour, greeting)

        # 拼接完整欢迎语（含使用说明）
        welcome = (
            f"{greeting}！我是你的日程提醒小助手～\n"
            f"今天是 {now.strftime('%Y年%m月%d日')} {now.strftime('%A')}。\n"
            f"你可以这样跟我说话：\n"
            f"  📝 「添加日程：下午5点开会」\n"
            f"  📝 「每天早上8点提醒我起床」\n"
            f"  🔍 「我今天的日程有哪些？」\n"
            f"  🗑 「删除日程1」\n"
            f"我会按时提醒你，再也不怕忘事啦！"
        )
        logger.info("欢迎语生成完成：greeting=%s", greeting)
        return welcome
