# -*- coding: utf-8 -*-
"""
tool_ledger.py — 记账本工具
--------------------------------------------------------------
功能: 基于 DeepSeek NL2SQL 实现自然语言记账。
      支持: 添加收支记录、按人/日期/类别查询、删除（软删除 enabled=0）。
      自动理解"我"指代当前用户，口语化自然语言回复。

技术: DeepSeek 生成 SQL → SQLite 执行 → AI 润色回复（失败时模板兜底）
数据: money_notes 表 (id, record_date, member , action_type, category, item_name, amount, enabled)

工单编号: 人工智能NLP-Agent数字人项目-智能体任务
所属目录: 研发
"""
import os          # 文件路径操作
import sqlite3     # SQLite 数据库
import json        # JSON 解析（LLM 返回的 SQL + 回复）
import logging     # 日志记录
import re          # 正则（JSON 提取、字段匹配）
from datetime import datetime  # 日期处理（今天、本月）

import config      # Agent 全局配置（数据库路径等）
from tool_utils import call_deepseek, clean_sql  # 共享工具（API 调用 + SQL 清理）

# 模块日志器
logger = logging.getLogger("agent.tools")


def tool_ledger(query: str) -> dict:
    """记账本工具 — 自然语言记账/查账/删账

    功能: 解析用户自然语言意图 → DeepSeek 生成 SQL → 执行 → 回复润色。
          支持"我"、"爸爸"、"妈妈"、"女儿"等家庭成员。

    参数:
        query (str): 用户自然语言查询（如"今天买书花了50元"）

    返回:
        dict: {"success": bool, "result": str, "tool": str}
    """
    logger.info("📒 记账: %s", query[:60])  # 记录用户查询（截断60字）

    try:
        # --- 数据库初始化 ---
        # 优先使用项目配置的数据库路径，不存在时自动创建本地 DB
        local_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "money_notes.db")
        db_path = config.LEDGER_DB if os.path.exists(config.LEDGER_DB) else local_db

        # 连接 SQLite，设置 row_factory 方便按列名取值
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # 确保 money_notes 表存在（首次使用自动建表）
        cur.execute("""
            CREATE TABLE IF NOT EXISTS money_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 记录唯一ID
                record_date TEXT NOT NULL,               -- 日期 YYYY-MM-DD
                member TEXT NOT NULL,                    -- 成员（我/爸爸/妈妈/女儿）
                action_type TEXT NOT NULL,               -- 类型（收入/支出）
                category TEXT NOT NULL,                  -- 分类（买书/买菜/购物/餐饮/交通/工资/娱乐/其他）
                item_name TEXT NOT NULL,                 -- 物品名称
                amount REAL NOT NULL,                    -- 金额（纯数字）
                enabled INTEGER DEFAULT 1,              -- 1=有效 0=已删除（软删除）
                created_at TEXT DEFAULT CURRENT_TIMESTAMP -- 创建时间
            )
        """)
        conn.commit()

        # --- 获取当前全部数据（供 LLM 生成 SQL 时参考上下文）---
        cur.execute("SELECT * FROM money_notes WHERE enabled=1 ORDER BY record_date, id")
        rows = cur.fetchall()
        cols = [desc[0] for desc in cur.description] if cur.description else []
        # 格式化为可读的行数据字符串
        data_str = "\n".join([
            " | ".join(f"{col}={row[col]}" for col in cols)
            for row in rows
        ])

        # --- 日期计算 ---
        today = datetime.now().strftime("%Y-%m-%d")       # 今天 2026-06-24
        now_cn = datetime.now().strftime("%Y年%m月%d日")    # 中文日期
        month_start = today[:7] + "-01"                    # 本月第一天
        today_year = today[:4]                             # 当前年份

        # --- 构建 LLM Prompt（含完整表结构 + SQL 示例 + 当前数据 + 规则）---
        prompt = f"""你是家庭记账助手。操作SQLite数据库 money_notes。

## 表结构（严格按此！）
CREATE TABLE money_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_date TEXT NOT NULL,   -- 格式 YYYY-MM-DD
    member TEXT NOT NULL,        -- 爸爸/妈妈/女儿/我
    action_type TEXT NOT NULL,   -- 支出 或 收入
    category TEXT NOT NULL,      -- 买书/买菜/购物/餐饮/交通/报销/工资/娱乐/其他
    item_name TEXT NOT NULL,     -- 具体物品或事项名称
    amount REAL NOT NULL,        -- 金额，纯数字不含单位
    enabled INTEGER DEFAULT 1    -- 1=有效 0=已删除
);

## SQL 示例（照此格式写！）
-- 记账：今天买书花了50元（"我"=用户本人）→
INSERT INTO money_notes (record_date, member, action_type, category, item_name, amount, enabled) VALUES ('{today}', '我', '支出', '买书', '三体', 50, 1);
-- 记账：7月5日妈妈收到报销1000元 →
INSERT INTO money_notes (record_date, member, action_type, category, item_name, amount, enabled) VALUES ('{today[:5]}07-05', '妈妈', '收入', '报销', '报销款', 1000, 1);
-- 查某人总消费：女儿花了多少钱 →
SELECT COALESCE(SUM(amount), 0) AS total FROM money_notes WHERE enabled=1 AND member='女儿' AND action_type='支出';
-- 查本月某人：这个月女儿花了多少钱 →
SELECT COALESCE(SUM(amount), 0) AS total FROM money_notes WHERE enabled=1 AND member='女儿' AND action_type='支出' AND record_date>='{month_start}';
-- 查本月明细：这个月花钱明细 →
SELECT * FROM money_notes WHERE enabled=1 AND action_type='支出' AND record_date>='{month_start}' ORDER BY record_date;
-- 查某物购买日期：我哪天买的三体 →
SELECT * FROM money_notes WHERE enabled=1 AND item_name LIKE '%三体%' ORDER BY record_date;
-- 删账：删除第3条记录 →
UPDATE money_notes SET enabled=0 WHERE id=3;

## 当前数据库内容
{data_str[:3000] if data_str else '(空)'}

## 规则
- 今天是{now_cn}({today})，本月从{month_start}开始
- "我"就是 member='我'，不要替换成其他名字
- 记账用INSERT，查账用SELECT，删账用UPDATE SET enabled=0
- 回复要口语化友好，查账时总结数据给结论
- INSERT必须包含全部6个字段：record_date, member, action_type, category, item_name, amount, enabled

## 用户: {query}

输出一个JSON对象（以{{开头，}}结尾，不要markdown包裹，不要注释）:
{{"sql":"完整SQL语句","reply":"友好回复"}}
{{"""

        # --- 调用 DeepSeek 生成 SQL + 回复 ---
        raw = call_deepseek([{"role": "user", "content": prompt}], max_tokens=1024)
        if not raw:
            conn.close()
            return {"success": False, "result": "AI服务暂不可用，请稍后重试", "tool": "记账本"}

        # --- 解析 LLM 返回的 JSON（多策略鲁棒提取）---
        sql, reply = "", ""  # 提取结果初始化
        json_str = raw.strip()

        # 策略1: 去 markdown 代码块包裹
        for tag in ["```json", "```sql", "```"]:
            if tag in json_str:
                parts = json_str.split(tag)
                if len(parts) >= 2:
                    json_str = parts[1].split("```")[0] if "```" in parts[1] else parts[1]
                    break

        # 策略2: 定位花括号范围提取 JSON 对象
        start = json_str.find('{')
        end = json_str.rfind('}')
        if start >= 0 and end > start:
            json_str = json_str[start:end + 1]

        # 尝试 JSON 解析
        try:
            parsed = json.loads(json_str)
            sql = (parsed.get("sql", "") or "").strip()
            reply = (parsed.get("reply", "") or "").strip()
            logger.info("记账 JSON 解析成功 | SQL=%s", sql[:80])
        except json.JSONDecodeError:
            logger.warning("JSON 解析失败: %s", raw[:150])
            # 降级提取 SQL — 找第一个 SQL 关键字
            for kw in ["SELECT", "INSERT", "UPDATE", "DELETE"]:
                idx = raw.upper().find(kw)
                if idx >= 0:
                    tail = raw[idx:]
                    for delim in [';', '\n', '",', '"}"']:
                        end_idx = tail.find(delim)
                        if end_idx > 0:
                            sql = tail[:end_idx].strip()
                            break
                    if not sql:
                        sql = tail.strip()
                    break
            # 尝试从文本中提取 reply 字段
            if not reply:
                match = re.search(r'"reply"\s*:\s*"([^"]*)"', raw)
                if match:
                    reply = match.group(1)

        # --- SQL 校验 ---
        if sql:
            sql_upper = sql.upper().strip()
            # 校验1: 必须引用 money_notes 表
            if "money_notes" not in sql.lower():
                logger.warning("SQL 未引用 money_notes 表，丢弃: %s", sql[:100])
                sql = ""
            # 校验2: INSERT 必须有 VALUES
            elif sql_upper.startswith("INSERT") and "VALUES" not in sql_upper:
                logger.warning("INSERT 缺少 VALUES，丢弃: %s", sql[:100])
                sql = ""

        # --- SQL 执行 ---
        if sql:
            try:
                cur.execute(sql)  # 执行 SQL
                if sql.upper().startswith("SELECT"):
                    # 查询操作：获取结果并生成回复
                    result_rows = cur.fetchall()
                    if result_rows:
                        if not reply:
                            # 无预生成回复 → 调 LLM 润色
                            data_dump = "\n".join([
                                " | ".join(str(r[col]) for col in cols)
                                for r in result_rows[:20]
                            ])
                            fallback_prompt = (
                                f"根据查询结果用一句话友好回复:\n{data_dump}\n\n"
                                f"问题:{query}\n回复:"
                            )
                            reply = call_deepseek(
                                [{"role": "user", "content": fallback_prompt}],
                                max_tokens=256
                            ) or str(result_rows[:3])
                        result = reply
                    else:
                        result = "未查询到相关记录，可能还没有这笔账哦~"
                else:
                    # 写操作（INSERT/UPDATE/DELETE）：提交事务
                    conn.commit()
                    result = reply or "操作成功"
                logger.info("记账 SQL 执行成功: %s", sql[:100])

            except Exception as e:
                logger.warning("记账 SQL 执行失败 (%s)，尝试修正...", str(e)[:60])
                # 带错误信息让 LLM 修正 SQL 后重试一次
                fix_prompt = (
                    f"SQL执行错误: {e}\n"
                    f"原SQL: {sql}\n"
                    f"表: money_notes(id,record_date,member,action_type,category,item_name,amount,enabled)\n"
                    f"今天:{today}\n"
                    f'修正后输出JSON: {{"sql":"...","reply":"..."}}'
                )
                retry_raw = call_deepseek([{"role": "user", "content": fix_prompt}], max_tokens=512)
                if retry_raw:
                    try:
                        js = retry_raw.strip()
                        for tag in ["```json", "```"]:
                            if tag in js:
                                js = js.split(tag)[1].split("```")[0]
                        s = js.find('{')
                        e = js.rfind('}')
                        if s >= 0 and e > s:
                            js = js[s:e + 1]
                        parsed2 = json.loads(js)
                        sql2 = (parsed2.get("sql", "") or "").strip()
                        if sql2 and "money_notes" in sql2.lower():
                            cur.execute(sql2)
                            if not sql2.upper().startswith("SELECT"):
                                conn.commit()
                            result = parsed2.get("reply", "操作成功")
                        else:
                            result = f"操作失败: {str(e)[:80]}"
                    except Exception:
                        result = f"操作失败: {str(e)[:80]}"
                else:
                    result = f"操作失败: {str(e)[:80]}"
        else:
            # SQL 无效 → LLM 兜底直接回答
            if not reply:
                fallback_data = (
                    f"用户问: {query}\n数据:\n{data_str[:2000]}\n请直接自然语言回答(不要SQL):"
                )
                reply = call_deepseek(
                    [{"role": "user", "content": fallback_data}],
                    max_tokens=256
                )
            result = reply or "抱歉，没能理解您的需求，请换个说法试试～"

        conn.close()
        return {"success": True, "result": result, "tool": "记账本"}

    except Exception as e:
        logger.error("记账错误: %s", e)
        return {"success": False, "result": f"记账失败: {str(e)[:150]}", "tool": "记账本"}
