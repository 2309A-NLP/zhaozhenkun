# -*- coding: utf-8 -*-
"""
db_explorer.py — 数据库探索工具
功能：连接SQLite数据库，获取所有表的schema、示例数据、行数、表关系
工单编号：人工智能NLP-Agent数字人项目-基金问答智能体任务
"""

import sqlite3  # SQLite数据库驱动
import pandas as pd  # 数据处理库，用于格式化展示
from logger import logger  # 统一日志


def get_connection(db_path):
    """创建数据库连接"""
    conn = sqlite3.connect(db_path)  # 连接数据库（中文路径兼容）
    conn.row_factory = sqlite3.Row  # 行工厂：查询结果可用列名访问
    return conn  # 返回连接对象（创建临时视图后可设只读）


def get_all_tables(conn):
    """获取数据库中所有用户表的名称列表"""
    cursor = conn.cursor()  # 创建游标
    # 从sqlite_master系统表查询所有用户表，排除系统表和索引
    cursor.execute(  # 执行查询
        "SELECT name FROM sqlite_master "  # 从系统表查询
        "WHERE type='table' "  # 只查表类型
        "AND name NOT LIKE 'sqlite_%' "  # 排除SQLite系统表
        "AND name NOT LIKE 'idx_%'"  # 排除索引
    )
    tables = [row["name"] for row in cursor.fetchall()]  # 提取表名到列表
    return tables  # 返回表名列表


def get_table_schema(conn, table_name):
    """获取指定表的完整schema信息（列名和数据类型）"""
    cursor = conn.cursor()  # 创建游标
    # 使用PRAGMA table_info获取表的列信息
    cursor.execute(f"PRAGMA table_info('{table_name}')")  # 执行PRAGMA查询
    columns = cursor.fetchall()  # 获取所有列信息
    # 构建schema描述：列名 -> 类型
    schema = []  # 存储列信息
    for col in columns:  # 遍历每一列
        col_name = col["name"]  # 列名
        col_type = col["type"] if col["type"] else "TEXT"  # 列类型，默认TEXT
        schema.append(f"  {col_name} ({col_type})")  # 格式化列信息
    return schema  # 返回列信息列表


def get_table_row_count(conn, table_name, fast=True):
    """获取指定表的行数（fast=True使用快速估算，避免大表COUNT超时）"""
    cursor = conn.cursor()  # 创建游标
    if fast:  # 快速估算模式：使用表统计信息
        # 尝试从sqlite_stat1获取近似行数
        try:
            cursor.execute(  # 查询统计表
                "SELECT stat FROM sqlite_stat1 WHERE tbl=? AND idx IS NULL",  # 表级统计
                (table_name,)  # 参数绑定
            )
            row = cursor.fetchone()  # 获取统计行
            if row:  # 有统计数据
                # stat格式: "表名 行数 索引信息..."
                parts = row["stat"].split()  # 按空格分割
                if len(parts) > 1:  # 至少有两部分
                    return int(parts[1])  # 第二部分是行数估算
        except Exception:  # 统计查询失败
            pass  # 使用备选方案
        # 备选方案：使用MAX(rowid)快速估算
        try:
            cursor.execute(f'SELECT MAX(rowid) FROM "{table_name}"')  # 最大rowid
            row = cursor.fetchone()  # 获取结果
            if row and row[0]:  # 有结果
                return row[0]  # 返回估算行数
        except Exception:  # 估算失败
            pass  # 返回0
        return 0  # 无法估算
    else:  # 精确计数（慢）
        cursor.execute(f"SELECT COUNT(*) as cnt FROM '{table_name}'")  # COUNT查询
        result = cursor.fetchone()  # 获取结果
        return result["cnt"]  # 返回精确行数


def get_sample_rows(conn, table_name, limit=3):
    """获取指定表的前N行示例数据，用于给LLM展示数据格式"""
    cursor = conn.cursor()  # 创建游标
    cursor.execute(f"SELECT * FROM '{table_name}' LIMIT {limit}")  # 取前N行
    rows = cursor.fetchall()  # 获取所有示例行
    if not rows:  # 如果表为空
        return []  # 返回空列表
    # 提取列名作为第一行
    columns = [desc[0] for desc in cursor.description]  # 从游标描述中取列名
    # 将数据行转为字典列表
    result = []  # 存储结果
    result.append(columns)  # 第一行是列名
    for row in rows:  # 遍历数据行
        result.append([str(row[col]) if row[col] is not None else "NULL" for col in columns])  # 转字符串
    return result  # 返回示例数据


def get_all_table_info(conn, sample_limit=3):
    """获取数据库中所有表的完整信息（schema + 行数 + 示例数据）"""
    tables = get_all_tables(conn)  # 获取所有表名
    all_info = {}  # 存储所有表的详细信息
    for table_name in tables:  # 遍历每张表
        schema = get_table_schema(conn, table_name)  # 获取字段结构
        row_count = get_table_row_count(conn, table_name)  # 获取行数
        samples = get_sample_rows(conn, table_name, sample_limit)  # 获取示例数据
        all_info[table_name] = {  # 存储表信息
            "schema": schema,  # 字段结构
            "row_count": row_count,  # 数据行数
            "samples": samples  # 示例数据
        }
    return all_info  # 返回所有表信息


def build_schema_description(all_info):
    """根据表信息构建schema的文字描述，用于嵌入LLM的System Prompt"""
    description_parts = []  # 存储描述文本的各部分
    description_parts.append("## 数据库表结构说明\n")  # 标题
    # 逐表描述
    for table_name, info in all_info.items():  # 遍历每张表
        desc = f"### 表名: {table_name}"  # 表名标题
        desc += f"\n- 总行数: {info['row_count']:,}"  # 行数（格式化千分位）
        desc += f"\n- 字段列表:"  # 字段列表标题
        for col in info["schema"]:  # 遍历字段
            desc += f"\n{col}"  # 添加字段信息
        # 添加示例数据
        if info["samples"]:  # 如果有示例数据
            desc += f"\n- 示例数据（前{len(info['samples'])-1}行）:"  # 示例数据标题
            # 格式化示例数据为紧凑字符串
            header = info["samples"][0]  # 列名行
            desc += f"\n  列名: {' | '.join(header)}"  # 打印列名
            for i, row in enumerate(info["samples"][1:], 1):  # 遍历数据行（跳过列名行）
                desc += f"\n  行{i}: {' | '.join(row)}"  # 打印数据行
        description_parts.append(desc)  # 加入描述列表
        description_parts.append("")  # 空行分隔
    return "\n".join(description_parts)  # 合并所有描述


def build_relationship_description():
    """构建表关系说明文字，帮助LLM理解如何JOIN表"""
    relationships = []  # 存储关系描述
    relationships.append("## 表关联关系说明\n")  # 标题
    relationships.append("核心关联字段及JOIN方式：\n")  # 说明
    # 基金相关关联
    relationships.append("1. 基金基本信息 ↔ 基金股票/债券/可转债持仓明细")
    relationships.append("   JOIN条件: 基金代码 = 基金代码")
    relationships.append("2. 基金基本信息 ↔ 基金日行情表")
    relationships.append("   JOIN条件: 基金代码 = 基金代码")
    relationships.append("3. 基金基本信息 ↔ 基金规模变动表")
    relationships.append("   JOIN条件: 基金代码 = 基金代码")
    relationships.append("4. 基金基本信息 ↔ 基金份额持有人结构")
    relationships.append("   JOIN条件: 基金代码 = 基金代码\n")
    # 股票相关关联
    relationships.append("5. A股票日行情表 ↔ A股公司行业划分表")
    relationships.append("   JOIN条件: 股票代码 = 股票代码 AND 交易日 = 交易日期")
    relationships.append("6. 基金股票持仓明细 ↔ A股票日行情表")
    relationships.append("   JOIN条件: 股票代码 = 股票代码")
    relationships.append("7. 基金可转债持仓明细 ↔ A股票日行情表")
    relationships.append("   JOIN条件: 对应股票代码 = 股票代码\n")
    # 日期格式说明
    relationships.append("## 重要注意事项\n")
    relationships.append("- 日期格式: 所有日期字段均为TEXT类型，格式为YYYYMMDD（如20210105）")
    relationships.append("- 行业划分标准: A股公司行业划分表的'行业划分标准'字段值包括'中信'和'申万'")
    relationships.append("- 涨跌幅计算: (收盘价-前一日收盘价)/前一日收盘价*100%")
    relationships.append("- 涨停判断: (收盘价/昨日收盘价-1) >= 9.8%")
    relationships.append("- 报告类型: 包括'季报'、'中报'、'年报'、'半年报'等")
    relationships.append("- 基金类型: 包括'混合型'、'股票型'、'债券型'、'货币型'等")
    relationships.append("- NULL处理: 数据中可能存在NULL值，SQL中需使用COALESCE或IS NULL判断")
    relationships.append("- 港股数据: 港股票日行情表结构与A股相同，但代码体系不同")
    return "\n".join(relationships)  # 返回关系描述


def explore_database(db_path):
    """主函数：全面探索数据库，返回完整的描述信息"""
    conn = get_connection(db_path)  # 建立只读连接
    try:
        all_info = get_all_table_info(conn)  # 获取所有表的详细信息
        schema_desc = build_schema_description(all_info)  # 构建schema文字描述
        rel_desc = build_relationship_description()  # 构建表关系描述
        return {  # 返回完整信息字典
            "all_info": all_info,  # 所有表的结构信息
            "schema_description": schema_desc,  # schema文字描述（用于Prompt）
            "relationship_description": rel_desc,  # 关系文字描述（用于Prompt）
            "table_names": list(all_info.keys())  # 所有表名列表
        }
    finally:
        conn.close()  # 确保连接被关闭


# 测试代码：直接运行时打印数据库概况
if __name__ == "__main__":  # 如果直接运行此脚本
    import config  # 导入配置文件
    db_info = explore_database(config.DB_PATH)  # 探索数据库
    logger.info(f"共发现 {len(db_info['table_names'])} 张表:")
    for t in db_info['table_names']:  # 遍历表名
        info = db_info['all_info'][t]  # 获取表信息
        logger.info(f"  {t}: {info['row_count']:,} 行, {len(info['schema'])} 个字段")
