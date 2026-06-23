# -*- coding: utf-8 -*-
"""
文件功能：数据库模块 —— 负责家庭记账本的全部数据存取操作。

工单编号：人工智能NLP-Agent数字人项目-记账本任务

职责说明：
  1. 创建并初始化 SQLite 数据库表结构
  2. 提供账目记录的增、删、查接口
  3. 封装数据库连接和事务管理

数据表 money_notes 字段说明：
  id          INTEGER  主键，自增
  record_date TEXT     记账日期，格式 YYYY-MM-DD
  member      TEXT     家庭成员（爸爸/妈妈/女儿/我）
  action_type TEXT     交易类型（收入/支出）
  category    TEXT     消费类别（买菜/买鞋/报销/旅游/...）
  item_name   TEXT     事项名称（登山鞋/三体/...）
  amount      REAL     金额（元）
  created_at  TEXT     记录创建时间戳
"""

# ---------- 标准库导入 ----------
import logging    # 日志记录
import sqlite3    # SQLite 数据库驱动（Python 内置）
from pathlib import Path      # 跨平台路径处理
from typing import Any         # 通用类型注解

# 获取当前模块的 logger（日志输出时带模块名前缀）
logger = logging.getLogger("agent_work_order_1.database")


class LedgerDatabase:
    """
    家庭记账数据库操作类。

    封装了 SQLite 数据库的建表、增、删、查操作，
    外部只需创建实例后调用 add_record / find_records / delete_record 等方法。
    """

    def __init__(self, db_path: Path) -> None:
        """
        初始化数据库连接。

        参数:
          db_path: SQLite 数据库文件的路径（Path 对象）
        """
        # 保存数据库文件路径，后续所有操作都基于此路径
        self.db_path = db_path
        # 初始化数据库表结构（如果表不存在则创建）
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """
        创建并返回一个 SQLite 数据库连接。

        使用 row_factory = sqlite3.Row 让查询结果可以通过列名访问。
        """
        # 连接 SQLite 数据库文件
        connection = sqlite3.connect(self.db_path)
        # 设置行工厂，使查询结果返回 Row 对象（可用列名访问，如 row["member"]）
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        """
        创建数据表 money_notes（如果表还不存在）。

        CREATE TABLE IF NOT EXISTS 是幂等操作：
        首次运行创建表，后续运行不会重复创建也不会报错。
        """
        # SQL 建表语句
        sql = """
        CREATE TABLE IF NOT EXISTS money_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增主键
            record_date TEXT NOT NULL,              -- 记账日期
            member TEXT NOT NULL,                   -- 家庭成员
            action_type TEXT NOT NULL,              -- 收入/支出
            category TEXT NOT NULL,                 -- 消费类别
            item_name TEXT NOT NULL,                -- 事项名称
            amount REAL NOT NULL,                   -- 金额
            enabled INTEGER DEFAULT 1,              -- 是否启用：1启用/0已删除
            created_at TEXT DEFAULT CURRENT_TIMESTAMP  -- 创建时间
        )
        """
        # 兼容旧表：如果 enabled 列不存在则自动添加
        try:
            with self._connect() as conn:
                conn.execute("ALTER TABLE money_notes ADD COLUMN enabled INTEGER DEFAULT 1")
                conn.commit()
        except Exception:
            pass  # 列已存在则忽略
        # with 语句自动管理连接和事务：退出时自动 commit 并关闭连接
        with self._connect() as connection:
            connection.execute(sql)   # 执行建表语句
            connection.commit()       # 提交事务
        # 记录初始化完成的日志
        logger.info("数据库初始化完成：%s", self.db_path)

    def add_record(self, record: dict[str, Any]) -> int:
        """
        新增一条账目记录。

        参数:
          record: 包含 record_date / member / action_type / category / item_name / amount 的字典

        返回:
          新插入记录的自增 ID
        """
        # SQL 插入语句，使用 ? 占位符防止 SQL 注入
        sql = """
        INSERT INTO money_notes (
            record_date, member, action_type, category, item_name, amount
        ) VALUES (?, ?, ?, ?, ?, ?)
        """
        # 从字典中提取对应字段，组成参数元组
        values = (
            record["record_date"],   # 记账日期
            record["member"],        # 家庭成员
            record["action_type"],   # 收入/支出
            record["category"],      # 消费类别
            record["item_name"],     # 事项名称
            record["amount"],        # 金额
        )
        # 执行插入操作
        with self._connect() as connection:
            cursor = connection.execute(sql, values)   # 执行 SQL
            connection.commit()                        # 提交事务
            # lastrowid 记录最后插入行的自增 ID（SQLite 特性）
            lastrowid = cursor.lastrowid if cursor.lastrowid is not None else 0
        # 记录新增成功的日志
        logger.info(
            "新增账目成功：id=%s, member=%s, item=%s, amount=%s",
            lastrowid, record["member"], record["item_name"], record["amount"]
        )
        return int(lastrowid)

    def find_records(self, conditions: dict[str, Any]) -> list[dict[str, Any]]:
        """
        按条件查询账目记录。

        参数:
          conditions: 查询条件字典，支持以下可选 key：
            - member: 家庭成员名称
            - action_type: 收入/支出
            - month_prefix: 月份前缀，如 "2025-07"
            - item_keyword: 事项关键词，模糊匹配

        返回:
          符合条件的记录列表，每条记录为 dict 格式；
          结果按 record_date ASC, id ASC 排序。
        """
        # 基础 SQL：默认只查启用记录（enabled=1）
        # "WHERE 1=1" 是一个技巧，方便后续动态拼接 AND 条件
        sql = "SELECT * FROM money_notes WHERE enabled = 1"
        values: list[Any] = []  # 存放 SQL 占位符对应的参数值

        # 条件 1：按家庭成员筛选
        if conditions.get("member"):
            sql += " AND member = ?"       # 追加 SQL 条件
            values.append(conditions["member"])  # 追加参数值

        # 条件 2：按交易类型筛选（收入/支出）
        if conditions.get("action_type"):
            sql += " AND action_type = ?"
            values.append(conditions["action_type"])

        # 条件 3：按月份前缀筛选（LIKE 模糊匹配，如 "2025-07%"）
        if conditions.get("month_prefix"):
            sql += " AND record_date LIKE ?"
            values.append(f"{conditions['month_prefix']}%")  # 拼接 LIKE 模式

        # 条件 4：按事项关键词筛选（在 item_name 和 category 中模糊匹配）
        if conditions.get("item_keyword"):
            sql += " AND (item_name LIKE ? OR category LIKE ?)"  # 两个字段同时匹配
            keyword = f"%{conditions['item_keyword']}%"          # 拼接模糊匹配模式
            values.extend([keyword, keyword])                     # 两个占位符用同一个值

        # 排序：先按日期升序，日期相同时按 ID 升序
        sql += " ORDER BY record_date ASC, id ASC"

        # 执行查询
        with self._connect() as connection:
            rows = connection.execute(sql, values).fetchall()  # 获取全部结果

        # 将 Row 对象转为普通字典列表（便于 JSON 序列化和模板渲染）
        results = [dict(row) for row in rows]

        # 记录查询完成日志
        logger.info("查询账目完成：conditions=%s, count=%s", conditions, len(results))
        return results

    def delete_record(self, record_id: int) -> bool:
        """
        按主键 ID 软删除一条账目记录（enabled = 0）。

        采用软删除而非物理删除，保留数据可追溯。

        参数:
          record_id: 要删除的记录 ID

        返回:
          True 表示删除成功，False 表示无匹配记录
        """
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE money_notes SET enabled = 0 WHERE id = ?",
                (record_id,)
            )
            connection.commit()
            success = cursor.rowcount > 0

        logger.info("软删除账目完成：id=%s, success=%s", record_id, success)
        return success

    def find_all_records(self, include_disabled: bool = False) -> list[dict[str, Any]]:
        """
        查询所有账目记录。

        参数:
          include_disabled: True 时包含已删除的，False 时仅返回启用的

        返回:
          全部记录列表
        """
        if include_disabled:
            sql = "SELECT * FROM money_notes ORDER BY record_date ASC, id ASC"
        else:
            sql = "SELECT * FROM money_notes WHERE enabled = 1 ORDER BY record_date ASC, id ASC"

        with self._connect() as connection:
            rows = connection.execute(sql).fetchall()

        results = [dict(row) for row in rows]
        logger.info("查询全部账目完成：count=%s, include_disabled=%s", len(results), include_disabled)
        return results

    def update_record(self, record_id: int, update_fields: dict[str, Any]) -> bool:
        """
        更新账目记录的指定字段。

        参数:
          record_id: 要更新的记录 ID
          update_fields: 要更新的字段字典

        支持的更新字段：record_date, member, action_type, category, item_name, amount

        返回:
          True 表示更新成功
        """
        allowed_fields = {"record_date", "member", "action_type", "category", "item_name", "amount"}
        safe_fields = {k: v for k, v in update_fields.items() if k in allowed_fields}
        if not safe_fields:
            logger.warning("更新账目无合法字段：id=%s", record_id)
            return False

        set_clauses = [f"{field} = ?" for field in safe_fields]
        values = list(safe_fields.values())
        values.append(record_id)
        sql = f"UPDATE money_notes SET {', '.join(set_clauses)} WHERE id = ?"

        with self._connect() as connection:
            cursor = connection.execute(sql, values)
            connection.commit()
            success = cursor.rowcount > 0

        logger.info("更新账目完成：id=%s, fields=%s, success=%s",
                    record_id, list(safe_fields.keys()), success)
        return success

    def get_record_by_id(self, record_id: int) -> dict[str, Any] | None:
        """
        按主键 ID 获取单条记录。

        参数:
          record_id: 要查询的记录 ID

        返回:
          如果找到则返回记录字典，否则返回 None
        """
        with self._connect() as connection:
            # 执行查询，fetchone() 返回单条记录或 None
            row = connection.execute(
                "SELECT * FROM money_notes WHERE id = ?",
                (record_id,)
            ).fetchone()

        # 如果找到记录，转为字典；否则返回 None
        result = dict(row) if row else None

        # 记录查询日志
        logger.info("按ID查询账目：id=%s, found=%s", record_id, result is not None)
        return result
