# -*- coding: utf-8 -*-
"""
文件功能：自然语言解析模块 —— 将用户的自然语言消息解析为结构化的日程操作指令。

职责说明：
  1. 意图识别：判断用户消息属于以下哪种意图
     - add: 添加日程（支持普通 / 每天 / 每周 / 每月）
     - query: 查询日程（支持今天 / 明天 / 全部）
     - delete: 按编号删除日程
     - delete_by_keyword: 按关键词匹配后删除
     - confirm_delete: 确认删除（与 Agent工单1 的确认机制一致）
     - invalid: 无法解析时的兜底
  2. 信息提取：
     - 时间：HH:MM 格式（支持"下午5点""上午9点30分""8:00"等多种表达）
     - 日期：YYYY-MM-DD 格式（支持"今天""明天""后天""7月5号"等）
     - 重复规则：daily / weekly / monthly 及其细节（星期几 / 几号）
     - 事项内容：去除时间/日期/关键词后的剩余文本

依赖资源：
  - PERIOD_OFFSET: 中文时段关键词→12小时制偏移量映射
  - WEEKDAY_CN: 中文星期名→英文星期名映射
  - REPEAT_DAILY/WEEKLY/MONTHLY: 重复关键词列表

项目背景：
  工单编号：人工智能 NLP-Agent 数字人项目-日程提醒智能体任务
"""

# ---------- 标准库导入 ----------
import calendar    # 月份天数查询（本模块暂未直接使用，保留以备扩展）
import logging     # 日志记录
import re          # 正则表达式，用于提取时间/日期/编号等信息
import traceback   # 打印异常堆栈
from datetime import datetime, timedelta  # 日期时间处理
from typing import Any                      # 通用类型注解

# 获取当前模块的 logger
logger = logging.getLogger("agent_work_order_2.parser")


# ========== 常量定义 ==========

# ---------- 时段偏移映射 ----------
# key: 中文时段关键词
# val: 12 小时制偏移量（0 表示上午，12 表示下午/晚上）
PERIOD_OFFSET = {
    "凌晨": 0, "早上": 0, "早晨": 0, "上午": 0,
    "中午": 0, "下午": 12, "傍晚": 12, "晚上": 12, "今晚": 12,
}

# ---------- 星期中文→英文映射 ----------
# 支持"周一""星期一""礼拜一"三种中文星期表达
WEEKDAY_CN = {
    "周一": "Monday", "周二": "Tuesday", "周三": "Wednesday",
    "周四": "Thursday", "周五": "Friday", "周六": "Saturday", "周日": "Sunday",
    "星期一": "Monday", "星期二": "Tuesday", "星期三": "Wednesday",
    "星期四": "Thursday", "星期五": "Friday", "星期六": "Saturday", "星期日": "Sunday",
    "礼拜一": "Monday", "礼拜二": "Tuesday", "礼拜三": "Wednesday",
    "礼拜四": "Thursday", "礼拜五": "Friday", "礼拜六": "Saturday", "礼拜天": "Sunday",
}

# ---------- 重复关键词列表 ----------
# 每天/天天/每日
REPEAT_DAILY = ["每天", "天天", "每日"]
# 每周/每星期/每个星期
REPEAT_WEEKLY = ["每周", "每星期", "每个星期"]
# 每月/每个月/每个月的
REPEAT_MONTHLY = ["每月", "每个月", "每个月的"]


class ScheduleParser:
    """
    日程自然语言解析器。

    工作模式：
      1. 优先调用 LLM 进行智能解析（支持口语化、模糊表达）
      2. LLM 不可用或失败时，自动降级为正则+关键词规则解析

    将用户输入的自然语言消息（如"明天上午9点提醒我交报告"）
    解析为结构化的日程操作指令，包括意图类型和提取出的各个字段。
    """

    def __init__(self, llm_client=None) -> None:
        """初始化解析器，记录当前时间用于处理相对时间表达。"""
        # 保存当前 datetime，后续处理"今天""明天"等相对时间时使用
        self.now = datetime.now()
        self.llm = llm_client  # LLM 客户端（可选）
        if self.llm:
            logger.info("解析器初始化完成（LLM 模式），当前时间：%s", self.now.strftime("%Y-%m-%d %H:%M"))
        else:
            logger.info("解析器初始化完成（正则模式），当前时间：%s", self.now.strftime("%Y-%m-%d %H:%M"))

    def parse(self, message: str) -> dict[str, Any]:
        """
        统一意图识别入口 —— 将用户消息分发到对应的子解析器。

        意图识别优先级（从高到低）：
          1. 空消息 → invalid
          2. 确认删除关键词 → confirm_delete
          3. 删除/取消关键词 → delete
          4. 查询关键词 → query
          5. 包含时间信息或日程关键词 → add
          6. 兜底 → invalid

        参数:
          message: 用户输入的自然语言消息

        返回:
          包含 intent 和对应结构化字段的字典
        """
        # 去除首尾空白
        text = message.strip()
        logger.info("【解析入口】原始消息：%s", text[:120])
        logger.debug("消息长度：%s字符", len(text))

        # 空消息检查
        if not text:
            logger.warning("【解析结果】收到空消息，返回 invalid")
            return {"intent": "invalid", "reply": "请输入日程信息，我来帮你记录。"}

        # ====== 优先使用 LLM 解析 ======
        if self.llm:
            llm_result = self._try_llm_parse(text)
            if llm_result:
                logger.info("【解析结果】LLM 解析成功：%s", llm_result.get("intent"))
                return llm_result
            logger.warning("【解析结果】LLM 解析失败，降级为正则解析")

        # ====== 降级：正则+关键词规则解析 ======

        # 情况 2：确认修改（需在确认删除之前检查）
        if text in {"确认修改", "确认更新"}:
            logger.info("【意图识别】→ confirm_update（匹配：%s）", text)
            return {"intent": "confirm_update"}

        # 情况 2b：确认删除（需在删除之前检查）
        if text in {"确认删除", "确认", "是", "好的", "确认取消"}:
            logger.info("【意图识别】→ confirm_delete（匹配：%s）", text)
            return {"intent": "confirm_delete"}

        # 情况 3：修改/更新意图
        # 在删除之前检查，因为修改语句中包含编号
        if any(word in text for word in ["修改日程", "更新日程", "更改日程", "变更日程",
                                           "改日程", "修改提醒", "更新提醒"]) or \
           any(re.search(pat, text) for pat in [
               r"把\s*日程\s*\d+\s*[改修改更新变]",
               r"将\s*日程\s*\d+\s*[改修改更新变]",
               r"日程\s*\d+\s*[改修改更新]",
           ]):
            logger.debug("【意图路由】进入修改分支")
            result = self._parse_update(text)
            logger.info("【意图识别】→ %s", result.get("intent"))
            return result

        # 情况 4：删除/取消意图
        # 在添加之前检查，因为删除语句中也可能包含时间信息
        if any(word in text for word in ["删除日程", "取消日程", "删掉日程", "移除日程"]):
            logger.debug("【意图路由】进入删除分支")
            result = self._parse_delete(text)
            logger.info("【意图识别】→ %s", result.get("intent"))
            return result

        # 情况 5：查询意图
        if any(word in text for word in ["日程有哪些", "有什么安排", "查看日程", "我的日程",
                                           "今天有什么", "日程列表", "所有日程", "全部日程"]):
            logger.debug("【意图路由】进入查询分支")
            result = self._parse_query(text)
            logger.info("【意图识别】→ %s, date=%s", result.get("intent"), result.get("schedule_date"))
            return result

        # 情况 6：添加日程（包含时间信息或日程关键词）
        if self._has_time_info(text) or any(kw in text for kw in ["添加日程", "提醒我", "提醒", "日程"]):
            logger.debug("【意图路由】进入添加分支（有时间信息或关键词）")
            result = self._parse_add(text)
            logger.info("【意图识别】→ %s, preview=%s", result.get("intent"), result.get("preview", "")[:80])
            return result

        # 情况 7：兜底尝试
        if self._has_time_info(text):
            logger.debug("【意图路由】兜底进入添加分支")
            result = self._parse_add(text)
            logger.info("【意图识别】→ %s（兜底）", result.get("intent"))
            return result

        # 全部不匹配：返回错误提示
        logger.warning("【解析结果】无法识别意图：%s", text[:80])
        return {"intent": "invalid",
                "reply": "我没理解你的意思。你可以说「添加日程：下午5点开会」或「我今天的日程有哪些？」"}

    def _try_llm_parse(self, text: str) -> dict[str, Any] | None:
        """
        尝试使用 LLM 解析用户消息。

        返回:
          解析后的字典（intent + 对应字段），失败返回 None
        """
        try:
            result = self.llm.parse_message(text)  # type: ignore[union-attr]
            if result is None:
                return None

            intent = result.get("intent", "")

            # ---- 添加日程：补充/校验字段 ----
            if intent == "add" and "schedule" in result:
                schedule = result["schedule"]
                # 确保时间存在
                if not schedule.get("schedule_time"):
                    logger.warning("LLM 添加解析缺时间")
                    return None
                # 确保日期存在
                if not schedule.get("schedule_date"):
                    schedule["schedule_date"] = self.now.strftime("%Y-%m-%d")
                # 确保内容存在
                if not schedule.get("content"):
                    logger.warning("LLM 添加解析缺内容")
                    return None
                # 确保 repeat_rule 存在
                if not schedule.get("repeat_rule"):
                    schedule["repeat_rule"] = "none"
                    schedule["repeat_detail"] = ""
                return result

            # ---- 查询日程 ----
            if intent == "query":
                return result

            # ---- 删除日程 ----
            if intent == "delete":
                return result

            # ---- 确认删除 ----
            if intent == "confirm_delete":
                return result

            # ---- 修改日程 ----
            if intent == "update":
                if not result.get("schedule_id") or not result.get("update_fields"):
                    logger.warning("LLM 修改解析信息不完整")
                    return None
                return result

            # ---- 确认修改 ----
            if intent == "confirm_update":
                return result

            # ---- 无法理解 ----
            if intent == "invalid":
                return {
                    "intent": "invalid",
                    "reply": result.get("reply", "我没理解你的意思，请换一种说法试试。"),
                }

            logger.warning("LLM 返回未知意图：%s", intent)
            return None

        except Exception as e:
            logger.error("LLM 解析异常：%s", e)
            return None

    def _has_time_info(self, text: str) -> bool:
        """
        判断文本是否包含时间信息。

        通过正则匹配检查多种时间表达方式：
          - "X点" "X:XX" "X点半"
          - "上午" "下午" "晚上" "凌晨" "中午" "早上" "傍晚"

        返回:
          True 表示包含时间信息，False 表示不包含
        """
        # 时间正则模式列表
        time_patterns = [
            r"\d{1,2}点",      # 如 "5点" "17点"
            r"\d{1,2}:\d{2}",  # 如 "17:00" "8:30"
            r"上午", r"下午", r"晚上", r"凌晨", r"中午", r"早上", r"傍晚",  # 时段词
            r"点半",            # 如 "7点半"
        ]
        # 逐个模式尝试匹配
        for p in time_patterns:
            if re.search(p, text):
                logger.debug("检测到时间模式：pattern=%s, text=%s", p, text[:60])
                return True
        logger.debug("未检测到时间信息：%s", text[:60])
        return False

    def _parse_add(self, text: str) -> dict[str, Any]:
        """
        解析添加日程语句，提取时间、日期、事项、重复规则。

        典型输入:
          "下午5点开会"           → 普通日程
          "每天早上8点提醒我起床"  → 每日重复
          "每周一上午9点开例会"    → 每周重复
          "明天上午10点提醒我交报告" → 指定日期

        返回:
          包含 intent="add" 和 schedule/preview 字段的字典
        """
        logger.info("【添加解析】开始解析：%s", text[:80])

        # ---------- Step 1：去除前缀 ----------
        # 用户可能以"添加日程："开头
        for prefix in ["添加日程：", "添加日程:", "添加日程", "添加：", "添加:"]:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                logger.debug("移除前缀 '%s'，剩余：%s", prefix, text[:60])
                break

        # ---------- Step 2：提取重复规则 ----------
        repeat_rule = "none"    # 默认无重复
        repeat_detail = ""      # 默认无细节

        # 检测每日重复关键词
        for kw in REPEAT_DAILY:
            if kw in text:
                repeat_rule = "daily"
                logger.debug("识别到每日重复：关键词=%s", kw)
                break

        # 检测每周重复关键词
        if repeat_rule == "none":
            for kw in REPEAT_WEEKLY:
                if kw in text:
                    repeat_rule = "weekly"
                    logger.debug("识别到每周重复：关键词=%s", kw)
                    break

        # 检测每月重复关键词
        if repeat_rule == "none":
            for kw in REPEAT_MONTHLY:
                if kw in text:
                    repeat_rule = "monthly"
                    logger.debug("识别到每月重复：关键词=%s", kw)
                    break

        # ---------- Step 3：提取重复细节 ----------
        # 每周 → 提取星期几
        if repeat_rule == "weekly":
            for cn, en in WEEKDAY_CN.items():
                if cn in text:
                    repeat_detail = en  # 存英文星期名
                    logger.debug("识别到星期详情：%s → %s", cn, en)
                    break
            if not repeat_detail:
                logger.warning("每周重复但未识别到具体星期：%s", text[:60])

        # 每月 → 提取日期号数
        if repeat_rule == "monthly":
            day_match = re.search(r"(\d{1,2})[号日]", text)  # 匹配"X号"或"X日"
            if day_match:
                repeat_detail = str(int(day_match.group(1)))  # 转为整数再转回字符串（去前导零）
                logger.debug("识别到每月日期：%s号", repeat_detail)
            else:
                logger.warning("每月重复但未识别到具体日期：%s", text[:60])

        # ---------- Step 4：提取日期 ----------
        schedule_date = self._extract_date(text)
        logger.debug("提取日期：%s", schedule_date)

        # ---------- Step 5：提取时间 ----------
        schedule_time = self._extract_time(text)
        if not schedule_time:
            logger.warning("【添加解析】未提取到时间：%s", text[:80])
            return {"intent": "invalid",
                    "reply": "我没看清时间，请说具体几点？比如「下午5点」或「上午9点」。"}
        logger.debug("提取时间：%s", schedule_time)

        # ---------- Step 6：提取事项内容 ----------
        content = self._extract_content(text)
        if not content:
            logger.warning("【添加解析】未提取到事项内容：%s", text[:80])
            return {"intent": "invalid",
                    "reply": "我没看清要提醒什么事项，请再说一次？"}
        logger.debug("提取事项内容：%s", content)

        # ---------- Step 7：生成预览文本 ----------
        # 用于向用户展示解析结果
        repeat_desc = ""
        if repeat_rule == "daily":
            repeat_desc = "（每天）"
        elif repeat_rule == "weekly" and repeat_detail:
            # 反向映射英文星期→中文星期
            week_cn = {v: k for k, v in WEEKDAY_CN.items()}.get(repeat_detail, repeat_detail)
            repeat_desc = f"（每{week_cn}）"
        elif repeat_rule == "monthly" and repeat_detail:
            repeat_desc = f"（每月{repeat_detail}号）"

        # 组装返回结果
        result = {
            "intent": "add",
            "schedule": {
                "schedule_time": schedule_time,   # 时间 HH:MM
                "schedule_date": schedule_date,   # 日期 YYYY-MM-DD
                "content": content,               # 事项内容
                "repeat_rule": repeat_rule,       # 重复规则
                "repeat_detail": repeat_detail,   # 重复细节
            },
            "preview": f"已记录日程：{schedule_date} {schedule_time} {repeat_desc}——{content}",
        }
        logger.info("【添加解析】完成：time=%s, date=%s, content=%s, repeat=%s/%s",
                    schedule_time, schedule_date, content, repeat_rule, repeat_detail)
        return result

    def _parse_query(self, text: str) -> dict[str, Any]:
        """
        解析查询语句，确定查询的日期范围。

        典型输入:
          "我今天的日程有哪些？"  → 查今天
          "明天有什么安排"        → 查明天
          "我的日程" / "全部日程"  → 查所有

        返回:
          包含 intent="query" 和 schedule_date 的字典
        """
        logger.info("【查询解析】开始解析：%s", text[:80])

        # 判断查询日期
        if "今天" in text:
            query_date = self.now.strftime("%Y-%m-%d")
            logger.debug("查询日期：今天 → %s", query_date)
        elif "明天" in text or "明日" in text:
            # 明天 = 当前日期 + 1 天
            tomorrow = self.now + timedelta(days=1)
            query_date = tomorrow.strftime("%Y-%m-%d")
            logger.debug("查询日期：明天 → %s", query_date)
        else:
            query_date = None  # None 表示查全部日程
            logger.debug("查询日期：全部日程")

        result = {
            "intent": "query",
            "schedule_date": query_date,
        }
        logger.info("【查询解析】完成：date=%s", query_date)
        return result

    def _parse_delete(self, text: str) -> dict[str, Any]:
        """
        解析删除/取消语句，提取删除目标。

        支持两种删除方式：
          1. 按编号删除：匹配文本中的数字（如 "删除日程1" → id=1）
          2. 按关键词匹配：匹配模式 "删除日程XXX"（如 "删除日程开会"）

        返回:
          包含 intent 和 schedule_id 或 keyword 的字典
        """
        logger.info("【删除解析】开始解析：%s", text[:80])

        # 提取数字编号（如 "1" "12"）
        id_match = re.search(r"(\d+)", text)
        if id_match:
            schedule_id = int(id_match.group(1))
            logger.info("【删除解析】按编号删除：id=%s", schedule_id)
            return {"intent": "delete", "schedule_id": schedule_id}

        # 兜底：按内容关键词匹配
        content_match = re.search(r"(?:删除日程|取消日程|删掉日程|移除日程)\s*(.+)", text)
        if content_match:
            keyword = content_match.group(1).strip()
            logger.info("【删除解析】按关键词删除：keyword=%s", keyword)
            return {"intent": "delete_by_keyword", "keyword": keyword}

        logger.warning("【删除解析】无法解析删除目标：%s", text[:80])
        return {"intent": "invalid", "reply": "请指定要删除的日程编号，如「删除日程1」。"}

    def _parse_update(self, text: str) -> dict[str, Any]:
        """
        解析修改日程语句，提取目标编号和要修改的字段。

        典型输入:
          "修改日程1 时间改为下午3点"      → 改时间
          "修改日程2 内容改为买咖啡"       → 改内容
          "把日程3改成明天上午9点开会"      → 改时间和日期
          "修改日程1 改为每天早上8点提醒"   → 改重复规则
          "更新日程3 日期改成后天"          → 改日期

        解析策略：
          1. 提取日程编号
          2. 提取要修改的字段（时间/日期/内容/重复规则）
          3. 提取新的字段值

        返回:
          包含 intent="update" 和 update 字段的字典
        """
        logger.info("【修改解析】开始解析：%s", text[:80])

        # Step 1：提取日程编号
        id_match = re.search(r"(\d+)", text)
        if not id_match:
            logger.warning("【修改解析】未提取到日程编号")
            return {"intent": "invalid",
                    "reply": "请指定要修改的日程编号，如「修改日程1 时间改为下午3点」。"}
        schedule_id = int(id_match.group(1))
        logger.debug("【修改解析】日程编号：%s", schedule_id)

        # Step 2：去除"把日程X改成"等前缀，保留后半部分作为新描述的来源
        # 同时标记是否包含完整的新描述
        full_replace = False
        for prefix_pattern in [
            r"把日程\d+改成\s*", r"把日程\d+修改为\s*", r"把日程\d+改为\s*",
            r"将日程\d+改成\s*", r"将日程\d+修改为\s*", r"将日程\d+改为\s*",
            r"日程\d+改成\s*", r"日程\d+改为\s*", r"日程\d+修改为\s*",
            r"修改日程\d+[：:]\s*", r"更新日程\d+[：:]\s*",
            r"修改日程\d+为\s*", r"更新日程\d+为\s*",
            r"修改日程\d+改为\s*", r"更改日程\d+改为\s*",
        ]:
            m = re.match(prefix_pattern, text)
            if m:
                text = text[m.end():].strip()
                full_replace = True  # 这是完整替换描述
                logger.debug("【修改解析】完整替换模式，剩余：%s", text[:60])
                break

        # Step 3：提取新值——判断是字段级修改还是整体替换
        update_fields = {}  # 存储要修改的字段：{field: new_value}

        # 模式 A：整体替换（如"修改日程1改成每天8点起床"）
        if full_replace and text:
            # 整体替换时，重新解析时间和内容
            new_date = self._extract_date(text)
            new_time = self._extract_time(text)
            new_content = self._extract_content(text)
            new_repeat_rule = "none"
            new_repeat_detail = ""
            # 检测重复规则
            for kw in REPEAT_DAILY:
                if kw in text:
                    new_repeat_rule = "daily"
                    break
            if new_repeat_rule == "none":
                for kw in REPEAT_WEEKLY:
                    if kw in text:
                        new_repeat_rule = "weekly"
                        break
            if new_repeat_rule == "none":
                for kw in REPEAT_MONTHLY:
                    if kw in text:
                        new_repeat_rule = "monthly"
                        break
            if new_repeat_rule == "weekly":
                for cn, en in WEEKDAY_CN.items():
                    if cn in text:
                        new_repeat_detail = en
                        break
            if new_repeat_rule == "monthly":
                day_match = re.search(r"(\d{1,2})[号日]", text)
                if day_match:
                    new_repeat_detail = str(int(day_match.group(1)))

            if new_date:
                update_fields["schedule_date"] = new_date
            if new_time:
                update_fields["schedule_time"] = new_time
            if new_content:
                update_fields["content"] = new_content
            if new_repeat_rule != "none":
                update_fields["repeat_rule"] = new_repeat_rule
                if new_repeat_detail:
                    update_fields["repeat_detail"] = new_repeat_detail

        # 模式 B：字段级修改（如"时间改为下午3点""内容改为开会"）
        else:
            # 提取"时间"字段的新值
            time_match = re.search(r"时间[改为是改成更新]+(.+?)(?:$|[,，。;；]|内容|日期)", text)
            if not time_match:
                time_match = re.search(r"时间[改为是改成更新]+(.+)", text)
            if time_match:
                time_text = time_match.group(1).strip()
                new_time = self._extract_time(time_text)
                if new_time:
                    update_fields["schedule_time"] = new_time
                    logger.debug("【修改解析】新时间：%s", new_time)

            # 提取"内容"字段的新值
            content_match = re.search(r"内容[改为是改成更新]+(.+?)(?:$|[,，。;；]|时间|日期)", text)
            if not content_match:
                content_match = re.search(r"内容[改为是改成更新]+(.+)", text)
            if content_match:
                new_content = content_match.group(1).strip()
                # 从新内容文本中提取纯粹的事项
                extracted = self._extract_content(new_content)
                if extracted:
                    update_fields["content"] = extracted
                else:
                    update_fields["content"] = new_content
                logger.debug("【修改解析】新内容：%s", update_fields.get("content"))

            # 提取"日期"字段的新值
            date_match = re.search(r"日期[改为是改成更新]+(.+?)(?:$|[,，。;；]|时间|内容)", text)
            if not date_match:
                date_match = re.search(r"日期[改为是改成更新]+(.+)", text)
            if date_match:
                date_text = date_match.group(1).strip()
                new_date = self._extract_date(date_text)
                if new_date:
                    update_fields["schedule_date"] = new_date
                    logger.debug("【修改解析】新日期：%s", new_date)

            # 提取重复规则
            for kw in REPEAT_DAILY:
                if kw in text:
                    update_fields["repeat_rule"] = "daily"
                    update_fields["repeat_detail"] = ""
                    logger.debug("【修改解析】新重复规则：daily")
                    break
            if "repeat_rule" not in update_fields:
                for kw in REPEAT_WEEKLY:
                    if kw in text:
                        update_fields["repeat_rule"] = "weekly"
                        for cn, en in WEEKDAY_CN.items():
                            if cn in text:
                                update_fields["repeat_detail"] = en
                                break
                        logger.debug("【修改解析】新重复规则：weekly/%s", update_fields.get("repeat_detail"))
                        break
            if "repeat_rule" not in update_fields:
                for kw in REPEAT_MONTHLY:
                    if kw in text:
                        update_fields["repeat_rule"] = "monthly"
                        day_match = re.search(r"(\d{1,2})[号日]", text)
                        if day_match:
                            update_fields["repeat_detail"] = str(int(day_match.group(1)))
                        logger.debug("【修改解析】新重复规则：monthly/%s", update_fields.get("repeat_detail"))
                        break

        # Step 4：验证至少有一个字段要修改
        if not update_fields:
            logger.warning("【修改解析】未提取到任何修改字段：%s", text[:80])
            return {"intent": "invalid",
                    "reply": "我没看清要修改什么。你可以说「修改日程1 时间改为下午3点」"
                             "或「修改日程1 内容改为开会」。"}

        # 生成预览描述
        desc_parts = []
        field_cn_map = {
            "schedule_time": "时间",
            "schedule_date": "日期",
            "content": "内容",
            "repeat_rule": "重复规则",
            "repeat_detail": "重复细节",
        }
        for field, value in update_fields.items():
            cn_name = field_cn_map.get(field, field)
            if field == "repeat_rule":
                rule_map = {"daily": "每天", "weekly": "每周", "monthly": "每月"}
                value = rule_map.get(value, value)
            desc_parts.append(f"{cn_name}→{value}")

        result = {
            "intent": "update",
            "schedule_id": schedule_id,
            "update_fields": update_fields,
            "preview": f"准备修改日程 #{schedule_id}：{'，'.join(desc_parts)}",
        }
        logger.info("【修改解析】完成：id=%s, fields=%s", schedule_id, list(update_fields.keys()))
        return result

    def _extract_time(self, text: str) -> str | None:
        """
        从文本中提取时间，返回 HH:MM 格式字符串。

        支持的时间表达：
          1. HH:MM 格式（如 "8:00" "17:30"）
          2. "X点"（如 "5点" "下午5点"）
          3. "X点X分"（如 "9点30分"）
          4. "X点半"（如 "7点半" = 7:30）
          5. 凌晨/早上/上午/中午/下午/傍晚/晚上 时段偏移

        参数:
          text: 用户输入文本

        返回:
          格式化时间字符串 HH:MM，未找到返回 None
        """
        logger.debug("【时间提取】开始：%s", text[:60])

        # 模式 1：HH:MM 格式（优先级最高）
        hhmm_match = re.search(r"(\d{1,2}):(\d{2})", text)
        if hhmm_match:
            hour = int(hhmm_match.group(1))
            minute = int(hhmm_match.group(2))
            result = f"{hour:02d}:{minute:02d}"
            logger.debug("【时间提取】HH:MM格式 → %s", result)
            return result

        # 模式 2：识别中文时段关键词
        period = None
        for p in ["凌晨", "早上", "早晨", "上午", "中午", "下午", "傍晚", "晚上", "今晚"]:
            if p in text:
                period = p
                logger.debug("【时间提取】识别时段：%s", period)
                break

        # 提取小时数（"X点"）
        hour_match = re.search(r"(\d{1,2})\s*点", text)
        if not hour_match:
            logger.warning("【时间提取】未找到小时信息")
            return None
        hour = int(hour_match.group(1))
        logger.debug("【时间提取】小时：%s", hour)

        # 提取分钟数
        minute = 0  # 默认整点
        minute_match = re.search(r"(\d{1,2})\s*分", text)  # "X分"
        half_match = re.search(r"半", text)               # "半"（即30分）
        if minute_match:
            minute = int(minute_match.group(1))
            logger.debug("【时间提取】分钟（分）：%s", minute)
        elif half_match:
            minute = 30  # "点半" = 30分
            logger.debug("【时间提取】分钟（半）：30")

        # 按时段关键词进行 12 小时制偏移
        if period:
            offset = PERIOD_OFFSET.get(period, 0)
            logger.debug("【时间提取】时段偏移：period=%s, offset=%s, raw_hour=%s", period, offset, hour)
            # 下午/晚上/傍晚/今晚：小时 +12
            if period in ("下午", "晚上", "傍晚", "今晚"):
                if hour < 12:
                    hour += 12
                    logger.debug("【时间提取】下午/晚上偏移后：%s", hour)
            # 凌晨/早上/早晨/上午：12 点转为 0 点
            if period in ("凌晨", "早上", "早晨", "上午"):
                if hour == 12:
                    hour = 0
                    logger.debug("【时间提取】上午12点 → 0点")

        # 边界检查：小时 0-23，分钟 0-59
        hour = max(0, min(23, hour))
        minute = max(0, min(59, minute))

        result = f"{hour:02d}:{minute:02d}"
        logger.info("【时间提取】完成：%s → %s", text[:40], result)
        return result

    def _extract_date(self, text: str) -> str:
        """
        从文本中提取日期，返回 YYYY-MM-DD 格式。

        支持的日期表达：
          1. "今天" → 当前日期
          2. "明天"/"明日" → 当前日期 +1 天
          3. "后天" → 当前日期 +2 天
          4. "2025年7月5号" → 完整年月日
          5. "7月5号"/"7月5日" → 缺少年份，补用当前年份
          6. 无日期 → 默认今天

        参数:
          text: 用户输入文本

        返回:
          格式化日期字符串 YYYY-MM-DD
        """
        logger.debug("【日期提取】开始：%s", text[:60])

        # 相对日期："今天"
        if "今天" in text:
            result = self.now.strftime("%Y-%m-%d")
            logger.debug("【日期提取】今天 → %s", result)
            return result

        # 相对日期："明天"/"明日"
        if "明天" in text or "明日" in text:
            tomorrow = self.now + timedelta(days=1)
            result = tomorrow.strftime("%Y-%m-%d")
            logger.debug("【日期提取】明天 → %s", result)
            return result

        # 相对日期："后天"
        if "后天" in text:
            day_after = self.now + timedelta(days=2)
            result = day_after.strftime("%Y-%m-%d")
            logger.debug("【日期提取】后天 → %s", result)
            return result

        # 完整日期："2025年7月5号" 或 "2025年7月5日"
        full_match = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})[号日]", text)
        if full_match:
            y, m, d = map(int, full_match.groups())
            result = f"{y:04d}-{m:02d}-{d:02d}"
            logger.debug("【日期提取】完整日期 → %s", result)
            return result

        # 简写日期："7月5号" 或 "7月5日"（补用当前年份）
        md_match = re.search(r"(\d{1,2})月(\d{1,2})[号日]", text)
        if md_match:
            m, d = map(int, md_match.groups())
            result = f"{self.now.year:04d}-{m:02d}-{d:02d}"
            logger.debug("【日期提取】月日 → %s", result)
            return result

        # 默认：当天
        result = self.now.strftime("%Y-%m-%d")
        logger.debug("【日期提取】默认今天 → %s", result)
        return result

    def _extract_content(self, text: str) -> str:
        """
        从文本中提取事项内容（去除时间、日期、重复关键词后的剩余文本）。

        清理步骤（按顺序）：
          1. 移除添加前缀（"添加日程："等）
          2. 移除时间表达式（HH:MM、X点X分、X点半）
          3. 移除日期关键词（今天/明天/后天）
          4. 移除时段关键词（上午/下午/晚上等）
          5. 移除星期表达
          6. 移除重复关键词（每天/每周/每月）
          7. 移除动词关键词（提醒我/提醒/日程等）
          8. 清洗剩余空白和标点

        参数:
          text: 用户输入文本

        返回:
          清理后的事项内容字符串，空则表示提取失败
        """
        logger.debug("【内容提取】开始：%s", text[:80])
        cleaned = text

        # Step 1：移除添加前缀
        for prefix in ["添加日程：", "添加日程:", "添加日程", "添加：", "添加:"]:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
                logger.debug("【内容提取】移除前缀后：%s", cleaned[:60])

        # Step 2：移除时间表达式（正则批量替换）
        cleaned = re.sub(r"\d{4}年\d{1,2}月\d{1,2}[号日]", "", cleaned)   # 完整日期
        cleaned = re.sub(r"\d{1,2}月\d{1,2}[号日]", "", cleaned)           # 月日
        cleaned = re.sub(r"\d{1,2}:\d{2}", "", cleaned)                    # HH:MM
        cleaned = re.sub(r"\d{1,2}\s*点\s*半?", "", cleaned)               # X点/X点半
        cleaned = re.sub(r"\d{1,2}\s*点\s*\d{1,2}\s*分?", "", cleaned)    # X点X分
        cleaned = re.sub(r"\d{1,2}\s*分", "", cleaned)                     # X分
        logger.debug("【内容提取】移除时间后：%s", cleaned[:60])

        # Step 3：移除日期关键词
        for word in ["今天", "明天", "后天", "明日"]:
            cleaned = cleaned.replace(word, "")
        logger.debug("【内容提取】移除日期关键词后：%s", cleaned[:60])

        # Step 4：移除时段关键词
        for word in ["凌晨", "早上", "早晨", "上午", "中午", "下午", "傍晚", "晚上", "今晚"]:
            cleaned = cleaned.replace(word, "")
        logger.debug("【内容提取】移除时段后：%s", cleaned[:60])

        # Step 5：移除星期（需在移除重复关键词之前，避免"每周一"拆出"一"）
        for w in WEEKDAY_CN:
            cleaned = cleaned.replace(w, "")
        logger.debug("【内容提取】移除星期后：%s", cleaned[:60])

        # Step 6：移除重复关键词
        for words in [REPEAT_DAILY, REPEAT_WEEKLY, REPEAT_MONTHLY]:
            for w in words:
                cleaned = cleaned.replace(w, "")
        cleaned = cleaned.replace("每", "")  # 移除孤立的"每"字
        logger.debug("【内容提取】移除重复关键词后：%s", cleaned[:60])

        # Step 7：移除动词/指令关键词（替换为空格便于分词）
        for word in ["提醒我", "提醒", "日程", "添加", "记录", "记录一下"]:
            cleaned = cleaned.replace(word, " ")
        logger.debug("【内容提取】移除动词后：%s", cleaned[:60])

        # Step 8：清洗空白和首尾标点
        # \s+ → 连续空白合并为一个空格
        # strip(" ，。，、；：！？ 　") → 移除首尾中文/英文/全角标点
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ，。，、；：！？ 　")

        # 内容太短或为空，视为提取失败
        if not cleaned or len(cleaned) <= 1:
            logger.warning("【内容提取】内容为空或太短：%s", cleaned)
            return ""

        logger.info("【内容提取】完成：%s → %s", text[:40], cleaned)
        return cleaned
