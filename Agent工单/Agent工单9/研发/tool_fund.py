# -*- coding: utf-8 -*-
"""
tool_fund.py — 基金问答工具
--------------------------------------------------------------
功能: 基于 NL2SQL 实现金融数据自然语言查询。
      支持: 基金净值查询、股票涨跌幅排名、基金持仓（债券/股票）、行业分析。

技术: DeepSeek 生成 SQL → SQLite 查询（博金杯金融数据库）→ AI 润色回复
      润色失败时自动回退到模板格式化（保留数值精度）

数据: bs_challenge_financial_14b_dataset（含10+张金融数据表）

工单编号: 人工智能NLP-Agent数字人项目-智能体任务
所属目录: 研发
"""
import sqlite3     # SQLite 数据库查询
import logging     # 日志记录

from tool_utils import call_deepseek, clean_sql, resolve_data_path  # 共享工具

# 模块日志器
logger = logging.getLogger("agent.tools")


def _format_fund_answer(query: str, rows: list, cols: list) -> str:
    """将 SQL 查询结果格式化为自然语言答案

    功能: 先用 AI 润色原始查询结果，失败时自动回退到模板格式化。
          确保百分数、小数精度保留，数据完整呈现。

    参数:
        query (str): 用户原始查询
        rows (list): SQL 查询结果行列表
        cols (list): 列名列表

    返回:
        str: 格式化的自然语言答案
    """
    if not rows:
        return "未查询到相关数据，请检查基金名称、日期或筛选条件是否正确。"

    # 将查询结果格式化为文本（供 AI 润色）
    data_text = "\n".join([
        " | ".join(str(row[col]) for col in cols) for row in rows
    ])

    # 尝试 AI 润色
    refine_prompt = (
        f"根据以下查询结果，用自然流畅的中文回答用户问题。要求：\n"
        f"1. 完整复现所有查询结果，不要遗漏任何数据\n"
        f"2. 保持数据精度（小数位数）不变\n"
        f"3. 如果用户问的是\"前N大\"，请用编号逐条列出\n"
        f"4. 百分数保留两位小数，带%符号\n"
        f"5. 回答2-5句话，信息要完整\n\n"
        f"查询结果:\n{data_text}\n\n"
        f"用户问题: {query}\n\n"
        f"请直接回答（不要markdown标记）:"
    )
    ai_answer = call_deepseek(
        [{"role": "user", "content": refine_prompt}],
        max_tokens=2048
    )
    if ai_answer and len(ai_answer.strip()) >= 10:
        return ai_answer.strip()

    # AI 润色失败 → 模板兜底（程序化格式化）
    logger.warning("AI 润色失败 (len=%d)，使用模板兜底", len(ai_answer or ""))
    col_names = [str(c) for c in cols]
    lines = ["根据查询结果，"]
    for i, row in enumerate(rows, 1):
        vals = []
        for c in cols:
            val = row[c]
            if isinstance(val, float):
                # 百分比类数值 → 格式化为 xx.xx%
                if any(kw in str(c) for kw in ['占比', '率', '比']):
                    vals.append(f"{val * 100:.2f}%")
                else:
                    # 普通小数 → 保留精度，整数则去小数点
                    vals.append(f"{val:.2f}" if val != int(val) else str(int(val)))
            else:
                vals.append(str(val))
        lines.append(f"第{i}项: {' | '.join(vals)}")
    if len(rows) > 1:
        lines.append(f"以上共{len(rows)}条记录。")
    return "\n".join(lines)


def tool_fund_qa(query: str) -> dict:
    """基金问答工具 — NL2SQL 自然语言查询金融数据

    功能: 接收中文自然语言查询 → DeepSeek 生成 SQL → 执行 → 润色回复。
          支持自动 SQL 修正重试。

    参数:
        query (str): 用户自然语言查询（如"20210715消费者服务涨跌幅最大"）

    返回:
        dict: {"success": bool, "result": str, "tool": str}
    """
    logger.info("📊 基金: %s", query[:60])

    try:
        # --- 数据库路径解析 ---
        db_path = resolve_data_path("dataset/博金杯比赛数据.db", env_var="FUND_DB_DIR")
        if not db_path:
            return {
                "success": False,
                "result": "基金数据库未找到（需下载 bs_challenge_financial_14b_dataset 或设置 FUND_DB_DIR）",
                "tool": "基金问答"
            }

        # --- 连接数据库并读取表结构 ---
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # 获取所有表名
        cur.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'idx_%'"
        )
        tables = [r[0] for r in cur.fetchall()]

        # 逐表获取列信息 + 行数
        schema_str = ""
        for tbl in tables:
            cur.execute(f"PRAGMA table_info('{tbl}')")
            cols_info = [f"{r['name']}({r['type']})" for r in cur.fetchall()]
            cur.execute(f"SELECT COUNT(*) FROM '{tbl}'")
            cnt = cur.fetchone()[0]
            schema_str += f"表:{tbl}({cnt}行) 列:{', '.join(cols_info)}\n"

        # --- 构建 SQL 生成 Prompt ---
        prompt = f"""你是基金数据库SQL专家。根据以下schema生成SQLite查询。

## 全部表结构（列名必须原样使用！带括号的列名必须保留）
{schema_str[:3500]}

## SQL示例（严格参照！）

### 1.基金债券/股票持仓查询
-- 某基金在某日季报的前N大持仓债券：
SELECT b."债券名称", ROUND(b."持债市值占基金资产净值比" * 100, 2) AS "持仓占比(%)"
FROM "基金债券持仓明细" b
JOIN "基金基本信息" f ON b."基金代码" = f."基金代码"
WHERE f."基金简称" LIKE '%景顺长城中短债债券C%'
  AND b."持仓日期" = '20210331'
  AND b."报告类型" LIKE '%季报%'
ORDER BY b."持债市值占基金资产净值比" DESC LIMIT 3;

-- 某基金股票持仓：
SELECT b."股票名称", ROUND(b."市值占基金资产净值比" * 100, 2) AS "持仓占比(%)"
FROM "基金股票持仓明细" b
JOIN "基金基本信息" f ON b."基金代码" = f."基金代码"
WHERE f."基金简称" LIKE '%基金名称%' AND b."持仓日期" = '日期'
ORDER BY b."市值占基金资产净值比" DESC LIMIT N;

### 2.股票涨跌幅查询（行业+日期）
SELECT a."股票代码",
  ROUND((a."收盘价(元)" - a."昨收盘(元)") / a."昨收盘(元)" * 100, 2) AS "涨跌幅(%)"
FROM "A股票日行情表" a
JOIN "A股公司行业划分表" i ON a."股票代码" = i."股票代码" AND a."交易日" = i."交易日期"
WHERE a."交易日" = '20210715' AND i."行业划分标准" = '中信行业分类'
  AND i."一级行业名称" = '消费者服务'
ORDER BY "涨跌幅(%)" DESC LIMIT 1;

### 3.基金净值查询
SELECT "单位净值", "累计单位净值" FROM "基金日行情表"
WHERE "基金代码" = (
  SELECT "基金代码" FROM "基金基本信息" WHERE "基金简称" LIKE '%基金名%'
) AND "交易日期" = '20210105';

## 关键规则
- 日期格式YYYYMMDD，无分隔符
- 带括号的列名必须完整保留，如 "收盘价(元)"
- 基金名用LIKE模糊匹配，基金代码用子查询
- 持仓查询需"报告类型"过滤（季报/年报/半年报）
- 排序取前N: ORDER BY 某列 DESC LIMIT N
- 别名用英文双引号包裹，如 AS "涨跌幅(%)"

## 查询
{query}

只输出一条完整SELECT语句（以SELECT开头，分号结尾）:"""

        # --- 生成 SQL ---
        raw_sql = call_deepseek([{"role": "user", "content": prompt}], max_tokens=4096)
        sql = clean_sql(raw_sql)  # 清理 markdown 和注释
        logger.info("基金 SQL: %s", str(sql)[:200])

        # --- SQL 执行 + 自动修正重试 ---
        if sql and sql.upper().startswith("SELECT"):
            try:
                cur.execute(sql)
                rows = cur.fetchall()[:20]  # 最多取20行
                if rows:
                    cols = [desc[0] for desc in cur.description]
                    result = _format_fund_answer(query, rows, cols)
                else:
                    result = "未查询到相关数据，请检查基金名称、日期或筛选条件是否正确。"
            except Exception as e:
                logger.warning("首次 SQL 失败: %s", str(e)[:100])
                # 带错误信息让 LLM 修正 SQL 后重试
                fix_prompt = (
                    f"SQL执行报错: {e}\n"
                    f"原SQL: {sql}\n"
                    f"表结构: {schema_str[:2500]}\n"
                    f"查询需求: {query}\n"
                    f"请修正SQL错误，只输出修正后的SELECT语句:"
                )
                raw_sql2 = call_deepseek([{"role": "user", "content": fix_prompt}], max_tokens=4096)
                sql2 = clean_sql(raw_sql2)
                if sql2 and sql2.upper().startswith("SELECT"):
                    try:
                        cur.execute(sql2)
                        rows = cur.fetchall()[:20]
                        if rows:
                            cols = [desc[0] for desc in cur.description]
                            result = _format_fund_answer(query, rows, cols)
                        else:
                            result = "未查询到相关数据，请检查基金名称、日期或筛选条件是否正确。"
                    except Exception as e2:
                        result = f"查询失败(已重试): {str(e2)[:150]}"
                else:
                    result = f"SQL修正失败，原错误: {str(e)[:150]}"
        else:
            result = "SQL生成失败，请尝试更明确地描述您的查询需求。"

        conn.close()
        return {"success": True, "result": result, "tool": "基金问答"}

    except Exception as e:
        logger.error("基金错误: %s", e)
        return {"success": False, "result": f"基金查询失败: {str(e)[:200]}", "tool": "基金问答"}
