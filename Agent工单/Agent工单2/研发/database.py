# -*- coding: utf-8 -*-
"""
文件功能：数据库模块 —— 负责日程提醒智能体的全部数据存取操作。

职责说明：
  1. 创建并初始化 SQLite 数据库表结构（schedules 表）
  2. 提供日程记录的增、删（软删除）、查接口
  3. 支持到期日程查询（按时间 + 重复规则匹配）
  4. 支持提醒时间更新（防止同一天重复提醒）

数据表 schedules 字段说明：
  id              INTEGER   主键，自增
  schedule_time   TEXT      日程时间，格式 HH:MM（如 "17:00"）
  schedule_date   TEXT      日程日期，格式 YYYY-MM-DD；循环日程可为空
  content         TEXT      日程内容/事项名称
  repeat_rule     TEXT      重复规则：none / daily / weekly / monthly
  repeat_detail   TEXT      重复细节：星期英文名 / 月份日期
  enabled         INTEGER   是否启用：1=启用，0=已取消（软删除）
  last_reminded   TEXT      上次提醒日期，用于防止同一天重复提醒
  created_at      TEXT      记录创建时间戳

项目背景：
  工单编号：人工智能 NLP-Agent 数字人项目-日程提醒智能体任务
"""

# ---------- 标准库导入 ----------
import logging     # 日志记录
import sqlite3     # SQLite 数据库驱动（Python 内置）
import traceback   # 打印异常堆栈
from pathlib import Path       # 跨平台路径处理
from typing import Any          # 通用类型注解

# 获取当前模块的 logger
logger = logging.getLogger("agent_work_order_2.database")


class ScheduleDatabase:
    """
    日程提醒数据库操作类。

    封装 SQLite 数据库的建表、增删查操作，
    支持普通日程和循环日程（每天/每周/每月）的到期判断。
    """

    def __init__(self, db_path: Path) -> None:
        """
        初始化数据库连接并创建表结构。

        参数:
          db_path: SQLite 数据库文件的路径（Path 对象）
        """
        logger.info("初始化数据库模块，路径：%s", db_path)
        logger.debug("数据库文件是否存在：%s", db_path.exists())
        # 保存数据库文件路径
        self.db_path = db_path
        # 初始化表结构（表不存在则创建）
        self._init_db()
        logger.info("数据库模块初始化完成")

    def _connect(self) -> sqlite3.Connection:
        """
        创建并返回一个 SQLite 数据库连接。

        返回:
          sqlite3.Connection 对象，配置了 row_factory
        """
        logger.debug("创建数据库连接：%s", self.db_path)
        try:
            # 连接 SQLite 数据库文件
            connection = sqlite3.connect(self.db_path)
            # 设置行工厂为 Row，使查询结果可用列名访问（如 row["content"]）
            connection.row_factory = sqlite3.Row
            logger.debug("数据库连接创建成功")
            return connection
        except sqlite3.Error as e:
            logger.error("数据库连接失败：%s", e)
            logger.debug("异常堆栈：%s", traceback.format_exc())
            raise  # 连接失败是致命错误，向上抛出

    def _init_db(self) -> None:
        """
        创建数据表 schedules（如果表还不存在）。

        CREATE TABLE IF NOT EXISTS 是幂等操作：
        首次运行创建表，后续运行跳过不报错。
        """
        logger.info("开始初始化数据表...")

        # SQL 建表语句
        sql = """
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,   -- 自增主键
            schedule_time TEXT NOT NULL,             -- 日程时间 HH:MM
            schedule_date TEXT DEFAULT NULL,         -- 日程日期 YYYY-MM-DD（循环日程可为空）
            content TEXT NOT NULL,                   -- 日程内容/事项
            repeat_rule TEXT DEFAULT 'none',         -- 重复规则：none/daily/weekly/monthly
            repeat_detail TEXT DEFAULT '',           -- 重复细节：星期英文/日期数字
            enabled INTEGER DEFAULT 1,               -- 是否启用：1启用/0取消
            last_reminded TEXT DEFAULT NULL,         -- 上次提醒日期
            created_at TEXT DEFAULT CURRENT_TIMESTAMP -- 创建时间
        )
        """
        logger.debug("执行建表SQL：%s", sql.strip()[:100])

        try:
            # with 语句自动管理连接：退出时 commit 并关闭
            with self._connect() as connection:
                connection.execute(sql)   # 执行建表
                connection.commit()       # 提交事务
            logger.info("数据表初始化完成：%s", self.db_path)
        except sqlite3.Error as e:
            logger.error("数据表初始化失败：%s", e)
            logger.debug("异常堆栈：%s", traceback.format_exc())
            raise

    def add_schedule(self, record: dict[str, Any]) -> int:
        """
        新增一条日程记录。

        参数:
          record: 包含 schedule_time / schedule_date / content / repeat_rule / repeat_detail 的字典

        返回:
          新插入记录的自增 ID
        """
        logger.info("开始新增日程：time=%s, content=%s, repeat=%s",
                    record.get("schedule_time"), record.get("content"), record.get("repeat_rule", "none"))
        logger.debug("完整记录数据：%s", record)

        # SQL 插入语句，使用 ? 占位符防止 SQL 注入
        sql = """
        INSERT INTO schedules (
            schedule_time, schedule_date, content, repeat_rule, repeat_detail, enabled
        ) VALUES (?, ?, ?, ?, ?, 1)  -- enabled 默认 1（启用）
        """
        # 从字典提取字段组成参数元组
        values = (
            record["schedule_time"],                             # 时间 HH:MM
            record.get("schedule_date", ""),                     # 日期（可选）
            record["content"],                                    # 事项内容
            record.get("repeat_rule", "none"),                   # 重复规则
            record.get("repeat_detail", ""),                     # 重复细节
        )
        logger.debug("执行INSERT SQL，参数：time=%s, date=%s, content=%s, rule=%s, detail=%s",
                     values[0], values[1], values[2], values[3], values[4])

        try:
            with self._connect() as connection:
                cursor = connection.execute(sql, values)   # 执行插入
                connection.commit()                        # 提交事务
                # lastrowid 记录最后插入行的自增 ID
                lastrowid = cursor.lastrowid if cursor.lastrowid is not None else 0
            logger.info("新增日程成功：id=%s, time=%s, content=%s, repeat=%s",
                        lastrowid, record["schedule_time"], record["content"], record.get("repeat_rule", "none"))
            return int(lastrowid)
        except sqlite3.Error as e:
            logger.error("新增日程失败：%s, record=%s", e, record)
            logger.debug("异常堆栈：%s", traceback.format_exc())
            raise

    def find_schedules(self, conditions: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """
        按条件查询日程记录（仅返回启用的日程）。

        参数:
          conditions: 可选查询条件字典，支持：
            - schedule_date: 按日期筛选（同时匹配同日普通日程和循环日程）
            - content_keyword: 按内容关键词模糊匹配
            - id: 按编号精确匹配

        返回:
          符合条件的记录列表，按 schedule_time ASC, id ASC 排序
        """
        conditions = conditions or {}
        logger.info("开始条件查询日程：conditions=%s", conditions)

        # 基础 SQL：只查启用的日程
        sql = "SELECT * FROM schedules WHERE enabled = 1"
        values: list[Any] = []  # 参数列表

        # 条件 1：按日期筛选
        filter_date = conditions.get("schedule_date")
        if filter_date:
            # 宽松匹配：同日普通日程 + 所有循环日程
            # 后续在 Python 中用 _is_due_today 精确过滤 weekly/monthly
            sql += " AND (schedule_date = ? OR repeat_rule != 'none')"
            values.append(filter_date)
            logger.debug("添加查询条件：schedule_date=%s", filter_date)

        # 条件 2：按内容关键词模糊匹配
        if conditions.get("content_keyword"):
            sql += " AND content LIKE ?"
            values.append(f"%{conditions['content_keyword']}%")  # 拼接 LIKE 模式
            logger.debug("添加查询条件：content_keyword=%s", conditions["content_keyword"])

        # 条件 3：按 ID 精确匹配
        if conditions.get("id"):
            sql += " AND id = ?"
            values.append(conditions["id"])
            logger.debug("添加查询条件：id=%s", conditions["id"])

        # 排序：先按时间，同时间按 ID
        sql += " ORDER BY schedule_time ASC, id ASC"
        logger.debug("最终查询SQL：%s", sql)
        logger.debug("查询参数：%s", values)

        try:
            with self._connect() as connection:
                rows = connection.execute(sql, values).fetchall()  # 获取全部结果
            # 将 Row 对象转为普通字典（便于 JSON 序列化）
            all_results = [dict(row) for row in rows]

            # 按日期查询时，对 weekly/monthly 做精确过滤
            if filter_date:
                results = []
                for r in all_results:
                    rule = r.get("repeat_rule", "none")
                    if rule in ("none", "daily"):
                        results.append(r)  # 普通和每日直接保留
                    elif self._is_due_today(r, filter_date):
                        results.append(r)  # weekly/monthly 精确匹配
            else:
                results = all_results

            logger.info("条件查询日程完成：conditions=%s, 命中=%s条", conditions, len(results))
            if results:
                # 日志输出查询结果的关键字段摘要
                logger.debug("查询结果摘要：%s", [{k: r[k] for k in ("id", "schedule_time", "content")} for r in results])
            else:
                logger.debug("查询结果为空")
            return results
        except sqlite3.Error as e:
            logger.error("条件查询日程失败：%s, conditions=%s", e, conditions)
            logger.debug("异常堆栈：%s", traceback.format_exc())
            return []  # 查询失败返回空列表而非抛异常

    def find_all_schedules(self, include_disabled: bool = False) -> list[dict[str, Any]]:
        """
        查询所有日程记录。

        参数:
          include_disabled: True 时包含已取消的日程，False 时仅返回启用的

        返回:
          全部日程记录列表
        """
        logger.info("开始查询全部日程：include_disabled=%s", include_disabled)

        # 根据参数决定是否过滤已取消的日程
        if include_disabled:
            sql = "SELECT * FROM schedules ORDER BY schedule_time ASC, id ASC"
        else:
            sql = "SELECT * FROM schedules WHERE enabled = 1 ORDER BY schedule_time ASC, id ASC"
        logger.debug("执行SQL：%s", sql)

        try:
            with self._connect() as connection:
                rows = connection.execute(sql).fetchall()
            results = [dict(row) for row in rows]
            # 统计启用和取消的数量
            enabled_count = sum(1 for r in results if r.get("enabled", 0) == 1)
            disabled_count = len(results) - enabled_count
            logger.info("查询全部日程完成：总计=%s条 (启用=%s, 已取消=%s)", len(results), enabled_count, disabled_count)
            return results
        except sqlite3.Error as e:
            logger.error("查询全部日程失败：%s", e)
            logger.debug("异常堆栈：%s", traceback.format_exc())
            return []

    def find_due_schedules(self, current_time: str, current_date: str) -> list[dict[str, Any]]:
        """
        查找当前时间到期的日程（供调度器调用）。

        匹配逻辑：
          1. 精确时间匹配（同一天的普通日程）
          2. 每日重复日程（daily）
          3. 每周重复日程（weekly，星期匹配）
          4. 每月重复日程（monthly，日期匹配）
          5. 排除今天已经提醒过的（last_reminded != current_date）

        参数:
          current_time: 当前时间 HH:MM
          current_date: 当前日期 YYYY-MM-DD

        返回:
          到期日程列表
        """
        logger.debug("检查到期日程：time=%s, date=%s", current_time, current_date)

        # 第一次 SQL 查询：获取可能到期的日程（含宽松条件）
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT * FROM schedules
                    WHERE enabled = 1                                    -- 只查启用的
                      AND schedule_time = ?                              -- 时间精确匹配
                      AND (
                        schedule_date = ? OR schedule_date = '' OR       -- 同日或无条件
                        (repeat_rule = 'daily') OR                       -- 每日重复
                        (repeat_rule = 'weekly' AND ? = ?) OR            -- 每周重复（占位）
                        (repeat_rule = 'monthly' AND ? = ?)              -- 每月重复（占位）
                      )
                      AND (last_reminded IS NULL OR last_reminded != ?)  -- 今天未提醒过
                    ORDER BY id ASC
                    """,
                    (
                        current_time,        # schedule_time 匹配
                        current_date,        # schedule_date 匹配
                        "daily", "weekly", "monthly",  # 占位参数（供 repeat_rule 对比）
                        current_date,        # 占位参数
                        current_date,        # last_reminded 排除
                    )
                ).fetchall()
            logger.debug("到期日程SQL原始命中：%s条", len(rows))
        except sqlite3.Error as e:
            logger.error("到期日程查询失败：%s", e)
            logger.debug("异常堆栈：%s", traceback.format_exc())
            return []

        # 在 Python 层面精确过滤 weekly / monthly 重复规则
        due = []
        for row in rows:
            r = dict(row)
            # 调用 _is_due_today 做精确的重复规则判断
            is_due = self._is_due_today(r, current_date)
            logger.debug("检查日程 #%s 是否到期：rule=%s, detail=%s, is_due=%s",
                        r["id"], r.get("repeat_rule"), r.get("repeat_detail"), is_due)
            if is_due:
                due.append(r)

        # 补充查询：每日重复日程（独立 SQL 确保不漏）
        try:
            with self._connect() as connection:
                daily_rows = connection.execute(
                    """
                    SELECT * FROM schedules
                    WHERE enabled = 1                            -- 启用的
                      AND schedule_time = ?                      -- 时间匹配
                      AND repeat_rule = 'daily'                  -- 每日重复
                      AND (last_reminded IS NULL OR last_reminded != ?)  -- 今天未提醒
                    """,
                    (current_time, current_date)
                ).fetchall()
            logger.debug("每日重复日程额外命中：%s条", len(daily_rows))
        except sqlite3.Error as e:
            logger.error("每日重复日程查询失败：%s", e)
            daily_rows = []

        # 合并每日重复结果（去重）
        for row in daily_rows:
            r = dict(row)
            if r["id"] not in [d["id"] for d in due]:  # 去重判断
                logger.debug("添加每日重复日程 #%s：%s", r["id"], r["content"])
                due.append(r)

        if due:
            logger.info("发现到期日程：%s条 -> %s",
                       len(due), [(d["id"], d["content"]) for d in due])
        else:
            logger.debug("当前无到期日程")
        return due

    def _is_due_today(self, record: dict[str, Any], current_date: str) -> bool:
        """
        判断一条日程是否在今天到期。

        支持的重复规则：
          - none: 仅当 schedule_date == current_date 时到期
          - daily: 每天都到期
          - weekly: 当 repeat_detail 中的星期与当前星期匹配时到期
          - monthly: 当 repeat_detail 中的日期与当前日期匹配时到期

        参数:
          record: 日程记录字典
          current_date: 当前日期 YYYY-MM-DD

        返回:
          True 表示今天到期，False 表示不到期
        """
        rule = record.get("repeat_rule", "none")
        logger.debug("判断到期：id=%s, rule=%s, detail=%s, schedule_date=%s, current=%s",
                    record["id"], rule, record.get("repeat_detail"), record.get("schedule_date"), current_date)

        # 无重复：仅在同一天到期
        if rule == "none":
            result = record.get("schedule_date", "") == current_date
            logger.debug("无重复规则：schedule_date==current → %s", result)
            return result

        # 每日重复：始终到期
        if rule == "daily":
            logger.debug("每日重复：始终到期")
            return True

        # 每周重复：检查星期是否匹配
        if rule == "weekly":
            from datetime import datetime
            try:
                # 获取当前日期的英文星期名（如 "Monday"）
                current_weekday = datetime.strptime(current_date, "%Y-%m-%d").strftime("%A")
                detail = record.get("repeat_detail", "")
                # detail 中存储的是英文星期名，与当前星期比对
                result = detail == current_weekday
                logger.debug("每周重复：detail=%s, current_weekday=%s → %s", detail, current_weekday, result)
                return result
            except ValueError as e:
                logger.warning("日期解析失败：%s", e)
                return False

        # 每月重复：检查日号是否匹配
        if rule == "monthly":
            try:
                # 获取当前日期的"日"部分
                current_day = datetime.strptime(current_date, "%Y-%m-%d").day
                detail = record.get("repeat_detail", "")
                # detail 是数字字符串，表示每月的第几天
                if detail.isdigit():
                    result = int(detail) == current_day
                    logger.debug("每月重复：detail_day=%s, current_day=%s → %s", detail, current_day, result)
                    return result
                # 如果 detail 为空，从 schedule_date 中提取日期
                if record.get("schedule_date"):
                    result = record["schedule_date"].split("-")[2] == current_date.split("-")[2]
                    logger.debug("每月重复(schedule_date)：%s", result)
                    return result
            except (ValueError, IndexError) as e:
                logger.warning("每月重复日期解析失败：%s", e)
                return False

        # 未知重复规则
        logger.debug("未知重复规则：%s", rule)
        return False

    def update_reminded(self, record_id: int, reminded_date: str) -> bool:
        """
        更新日程的最后提醒日期（防止同一天重复提醒）。

        参数:
          record_id: 日程 ID
          reminded_date: 提醒日期 YYYY-MM-DD

        返回:
          True 表示更新成功，False 表示失败
        """
        logger.debug("更新提醒时间：id=%s, date=%s", record_id, reminded_date)
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    "UPDATE schedules SET last_reminded = ? WHERE id = ?",
                    (reminded_date, record_id)
                )
                connection.commit()
                success = cursor.rowcount > 0  # rowcount > 0 表示有行被更新
            if success:
                logger.info("更新提醒时间成功：id=%s, date=%s", record_id, reminded_date)
            else:
                logger.warning("更新提醒时间失败：id=%s 未找到匹配记录", record_id)
            return success
        except sqlite3.Error as e:
            logger.error("更新提醒时间异常：%s, id=%s", e, record_id)
            logger.debug("异常堆栈：%s", traceback.format_exc())
            return False

    def disable_schedule(self, record_id: int) -> bool:
        """
        取消/删除日程（软删除：将 enabled 设为 0）。

        采用软删除而非物理删除，保留了历史数据，便于恢复。

        参数:
          record_id: 要取消的日程 ID

        返回:
          True 表示取消成功，False 表示失败
        """
        logger.info("开始取消日程：id=%s", record_id)
        try:
            with self._connect() as connection:
                cursor = connection.execute(
                    "UPDATE schedules SET enabled = 0 WHERE id = ?",  # 软删除标记
                    (record_id,)
                )
                connection.commit()
                success = cursor.rowcount > 0
            if success:
                logger.info("取消日程成功：id=%s", record_id)
            else:
                logger.warning("取消日程失败：id=%s 未找到匹配记录", record_id)
            return success
        except sqlite3.Error as e:
            logger.error("取消日程异常：%s, id=%s", e, record_id)
            logger.debug("异常堆栈：%s", traceback.format_exc())
            return False

    def update_schedule(self, record_id: int, update_fields: dict[str, Any]) -> bool:
        """
        更新日程记录的指定字段。

        参数:
          record_id: 要更新的日程 ID
          update_fields: 要更新的字段字典，如 {"schedule_time": "15:00", "content": "开会"}

        支持的更新字段：
          - schedule_time: 日程时间 HH:MM
          - schedule_date: 日程日期 YYYY-MM-DD
          - content: 日程内容/事项
          - repeat_rule: 重复规则 none/daily/weekly/monthly
          - repeat_detail: 重复细节

        返回:
          True 表示更新成功，False 表示失败
        """
        # 允许更新的字段白名单（防止注入）
        allowed_fields = {"schedule_time", "schedule_date", "content",
                          "repeat_rule", "repeat_detail"}

        # 过滤出合法的字段
        safe_fields = {k: v for k, v in update_fields.items() if k in allowed_fields}
        if not safe_fields:
            logger.warning("更新日程无合法字段：id=%s, fields=%s", record_id, update_fields.keys())
            return False

        logger.info("开始更新日程：id=%s, fields=%s", record_id, safe_fields)

        # 动态构建 SET 子句
        set_clauses = [f"{field} = ?" for field in safe_fields]
        values = list(safe_fields.values())
        values.append(record_id)  # WHERE 条件的参数

        sql = f"UPDATE schedules SET {', '.join(set_clauses)} WHERE id = ?"
        logger.debug("执行UPDATE SQL：%s, 参数：%s", sql, values)

        try:
            with self._connect() as connection:
                cursor = connection.execute(sql, values)
                connection.commit()
                success = cursor.rowcount > 0
            if success:
                logger.info("更新日程成功：id=%s, fields=%s", record_id, list(safe_fields.keys()))
            else:
                logger.warning("更新日程失败：id=%s 未找到匹配记录", record_id)
            return success
        except sqlite3.Error as e:
            logger.error("更新日程异常：%s, id=%s", e, record_id)
            logger.debug("异常堆栈：%s", traceback.format_exc())
            return False

    def get_schedule_by_id(self, record_id: int) -> dict[str, Any] | None:
        """
        按主键 ID 获取单条日程记录。

        参数:
          record_id: 要查询的日程 ID

        返回:
          找到返回记录字典，未找到返回 None
        """
        logger.debug("按ID查询日程：id=%s", record_id)
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM schedules WHERE id = ?", (record_id,)
                ).fetchone()
            # 如果找到，转为字典；否则返回 None
            result = dict(row) if row else None
            if result:
                logger.info("按ID查询日程成功：id=%s, content=%s, enabled=%s",
                           record_id, result.get("content"), result.get("enabled"))
            else:
                logger.info("按ID查询日程：id=%s 未找到", record_id)
            return result
        except sqlite3.Error as e:
            logger.error("按ID查询日程异常：%s, id=%s", e, record_id)
            logger.debug("异常堆栈：%s", traceback.format_exc())
            return None

    def get_max_id(self) -> int:
        """
        获取当前最大 ID，用于前端编号显示。

        返回:
          当前 schedules 表中的最大 ID，表为空时返回 0
        """
        logger.debug("查询最大ID")
        try:
            with self._connect() as connection:
                # MAX() 是 SQL 聚合函数
                row = connection.execute("SELECT MAX(id) as max_id FROM schedules").fetchone()
            max_id = row["max_id"] or 0  # 表为空时 MAX 返回 NULL，转为 0
            logger.debug("当前最大ID：%s", max_id)
            return max_id
        except sqlite3.Error as e:
            logger.error("查询最大ID异常：%s", e)
            return 0
