# -*- coding: utf-8 -*-
"""
tool_schedule.py — 日程提醒工具
--------------------------------------------------------------
功能: 基于自然语言实现日程管理。
      支持: 添加日程（含重复规则）、查询今日/未来日程、按编号删除。
      智能提取时间、内容、重复规则。

技术: 关键字判断意图 → LLM 提取结构化信息 → SQLite 执行 → 清单式回复
数据: schedules 表 (id, schedule_date, schedule_time, content, repeat_rule, enabled)

工单编号: 人工智能NLP-Agent数字人项目-智能体任务
所属目录: 研发
"""
import os          # 文件路径操作
import sqlite3     # SQLite 数据库
import json        # JSON 解析（LLM 返回结构化信息）
import logging     # 日志记录
import re          # 正则（提取编号等）
from datetime import datetime  # 日期处理

import config                  # Agent 全局配置
from tool_utils import call_deepseek  # 共享 DeepSeek 调用函数

# 模块日志器
logger = logging.getLogger("agent.tools")


def _init_schedule_db(db_path: str) -> sqlite3.Connection:
    """初始化日程数据库 — 不存在则自动创建 schedules 表

    参数:
        db_path (str): SQLite 数据库文件路径

    返回:
        sqlite3.Connection: 已初始化的数据库连接
    """
    conn = sqlite3.connect(db_path)          # 连接 SQLite
    conn.row_factory = sqlite3.Row           # 按列名取值
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 日程唯一ID
            schedule_date TEXT,                     -- 日期 YYYY-MM-DD
            schedule_time TEXT NOT NULL,             -- 时间 HH:MM
            content TEXT NOT NULL,                   -- 日程内容描述
            repeat_rule TEXT DEFAULT 'none',         -- 重复规则（none/daily/weekly/monthly）
            repeat_detail TEXT DEFAULT '',           -- 重复详情（备用）
            enabled INTEGER DEFAULT 1,              -- 1=有效 0=已删除
            last_reminded TEXT,                      -- 最后提醒时间
            created_at TEXT DEFAULT CURRENT_TIMESTAMP -- 创建时间
        )
    """)
    conn.commit()
    return conn


def _build_schedule_reply(rows: list, today_cn: str) -> str | None:
    """构建日程回复 — 清单格式（按时间排列）

    参数:
        rows (list): 日程查询结果行列表
        today_cn (str): 中文日期（如"06月24日"）

    返回:
        str | None: 格式化的日程清单，无数据时返回 None
    """
    if not rows:
        return None
    lines = []  # 逐条日程
    for i, row in enumerate(rows, 1):
        t = row['schedule_time']           # 时间
        c = row['content']                 # 内容
        rpt = row['repeat_rule'] if 'repeat_rule' in row.keys() else 'none'  # 重复规则
        tag = " 🔁每日" if rpt == 'daily' else ""  # 每日标记
        lines.append(f"{i}. {t} {c}{tag}")
    return f"📅 **{today_cn}**\n\n您今天的日程安排如下：\n\n" + "\n".join(lines)


def tool_schedule(query: str) -> dict:
    """日程提醒工具 — 自然语言添加/查询/删除日程

    功能: 解析用户意图 → 提取时间/内容 → 执行操作 → 清单式回复

    参数:
        query (str): 用户自然语言查询

    返回:
        dict: {"success": bool, "result": str, "tool": str}
    """
    logger.info("📅 日程: %s", query[:60])  # 记录用户查询

    try:
        # --- 日期计算 ---
        today = datetime.now().strftime("%Y-%m-%d")          # 今天 2026-06-24
        now_cn = datetime.now().strftime("%Y年%m月%d日")       # 中文完整日期
        today_cn = datetime.now().strftime("%m月%d日")         # 简短中文日期

        # --- 数据库初始化 ---
        local_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schedule_notes.db")
        db_path = config.SCHEDULE_DB if os.path.exists(config.SCHEDULE_DB) else local_db
        conn = _init_schedule_db(db_path)
        cur = conn.cursor()

        # --- 关键字判断意图 ---
        is_query = any(kw in query for kw in [
            '有哪些', '查看', '查询', '今天', '日程', '什么日程', '我的日程'
        ])
        is_add = any(kw in query for kw in [
            '添加', '新增', '记录', '安排', '提醒我', '提醒', '新建'
        ])
        is_delete = any(kw in query for kw in [
            '删除', '取消', '移除', '去掉'
        ])

        # ==================== 添加日程 ====================
        if is_add:
            # 让 LLM 从用户输入中提取结构化日程信息
            extract_prompt = (
                f"你是日程助手。从用户输入提取日程信息。今天是{now_cn}。\n"
                f"用户: {query}\n"
                f'输出JSON: {{"date":"YYYY-MM-DD或null","time":"HH:MM",'
                f'"content":"日程内容","repeat":"none/daily/weekly/monthly"}}\n'
                f"只输出JSON:"
            )
            raw = call_deepseek([{"role": "user", "content": extract_prompt}], max_tokens=300)

            # 默认值
            dt, tm, content, rpt = today, "09:00", query, "none"
            if raw:
                try:
                    r2 = raw.strip()
                    # 去除可能的 markdown 包裹
                    if r2.startswith("```"):
                        r2 = r2.split("```")[1].replace("json", "", 1)
                    p = json.loads(r2)
                    dt = p.get("date", today) or today            # 日期
                    tm = p.get("time", "09:00")                   # 时间
                    content = p.get("content", query)              # 内容
                    rpt = p.get("repeat", "none")                 # 重复规则
                except json.JSONDecodeError:
                    pass  # 解析失败时使用默认值

            # 插入日程记录
            cur.execute(
                "INSERT INTO schedules(schedule_date,schedule_time,content,repeat_rule) VALUES(?,?,?,?)",
                (dt, tm, content, rpt)
            )
            conn.commit()
            rid = cur.lastrowid  # 新记录的 ID
            result = f"✅ **已添加日程**\n\n📌 {content}\n⏰ {dt} {tm}\n🔢 编号: {rid}"
            conn.close()
            return {"success": True, "result": result, "tool": "日程提醒"}

        # ==================== 删除日程 ====================
        if is_delete:
            # 从用户输入中提取数字编号
            ids = re.findall(r'\d+', query)
            rid = int(ids[0]) if ids else None

            if rid:
                # 查找目标日程
                cur.execute("SELECT * FROM schedules WHERE id=?", (rid,))
                target = cur.fetchone()
                if target:
                    # 软删除（设置 enabled=0）
                    cur.execute("UPDATE schedules SET enabled=0 WHERE id=?", (rid,))
                    conn.commit()
                    result = (
                        f"✅ **已删除日程**\n\n"
                        f"编号{rid}: {target['schedule_time']} {target['content']}"
                    )
                else:
                    result = f"未找到编号为{rid}的日程"
            else:
                result = "请提供要删除的日程编号（如：删除日程1）"
            conn.close()
            return {"success": True, "result": result, "tool": "日程提醒"}

        # ==================== 查询日程 ====================
        # 查今日日程
        cur.execute(
            "SELECT * FROM schedules WHERE enabled=1 AND schedule_date=? ORDER BY schedule_time",
            (today,)
        )
        today_rows = cur.fetchall()

        if today_rows:
            reply = _build_schedule_reply(today_rows, today_cn)
        else:
            # 今日无日程 → 查未来日程
            cur.execute(
                "SELECT * FROM schedules WHERE enabled=1 AND schedule_date>=? "
                "ORDER BY schedule_date, schedule_time LIMIT 10",
                (today,)
            )
            all_rows = cur.fetchall()
            if all_rows:
                reply = f"📅 今天暂无日程。\n\n最近的日程安排：\n\n"
                for i, row in enumerate(all_rows, 1):
                    reply += f"{i}. {row['schedule_date']} {row['schedule_time']} {row['content']}\n"
            else:
                reply = (
                    f"📅 您目前没有任何日程安排。\n\n"
                    f"💡 试试说：\n"
                    f"• \"下午3点开会\"\n"
                    f"• \"每天早上8点提醒我运动\"\n"
                    f"• \"查看我的日程\""
                )

        conn.close()
        return {"success": True, "result": reply, "tool": "日程提醒"}

    except Exception as e:
        logger.error("日程错误: %s", e)
        return {"success": False, "result": f"日程操作失败: {str(e)[:150]}", "tool": "日程提醒"}
