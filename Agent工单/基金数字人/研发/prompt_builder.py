# -*- coding: utf-8 -*-
"""
prompt_builder.py — NL2SQL Prompt构建器
功能：构建发送给DeepSeek大模型的System Prompt和User Prompt，
     包含完整的数据库schema、表关系、SQL编写规范、Few-shot示例
工单编号：人工智能NLP-Agent数字人项目-基金问答智能体任务
"""
from logger import logger  # 统一日志


def build_system_prompt(schema_desc, rel_desc):
    """构建NL2SQL的系统提示词（System Prompt），包含schema和SQL规范"""
    system_prompt = f"""你是一位精通金融数据库的SQL专家。你的任务是将用户的中文自然语言问题，
准确转换为SQLite兼容的SQL查询语句，以便从基金/股票数据库中获取正确答案。

{schema_desc}

{rel_desc}

## SQL编写规范（必须严格遵守，违反将导致SQL执行失败）

⚠️ **最重要规则：表名必须与Schema中完全一致！**
上面列出的10张表就是全部可用的表，表名必须原样使用，一个字不能错。
禁止使用任何英文表名（如stock_daily、fund_info等），只能用中文表名！
如果你不确定某张表的表名，回到上面Schema中查找确认。

1. **表名/列名引用**：SQL中必须用双引号包裹中文表名和列名，如 "A股票日行情表"."收盘价(元)"
2. **日期处理**：日期字段为TEXT类型，格式YYYYMMDD。如 WHERE "交易日" = '20210105'
3. **涨跌幅计算**：使用LAG窗口函数，公式：(收盘价-前一日收盘价)/前一日收盘价*100
4. **涨停判断**：(收盘价/昨日收盘价-1)*100 >= 9.8 视作涨停，用LAG窗口函数
5. **排名/最大值**：使用ORDER BY + LIMIT 1取最大/最小
6. **百分比保留小数**：ROUND(值, 2)保留两位，ROUND(值, 3)保留三位
7. **取整**：CAST(值 AS INTEGER) 或 ROUND(值, 0)
8. **NULL处理**：使用COALESCE(字段, 默认值)处理可能为NULL的字段
9. **字符串匹配**：使用LIKE进行模糊匹配
10. **行业分类**：字段值有'中信行业分类'、'申万行业分类'。⚠️ 问题明确提到"中信"才加WHERE条件，未提则不加（两个标准的数据不同，限定标准可能导致查不到）
11. **季度判断**："一季度"=01-01至03-31，"三季度"=07-01至09-30
12. **基金公司匹配**：用"管理人"字段 LIKE '%公司名%' 进行匹配

## 输出格式要求（极其重要）

- **只输出SQL语句**，不要输出任何解释、说明、Markdown标记
- 不要用```sql```代码块包裹
- SQL必须是一条完整可执行的语句
- 如果问题无法用SQL回答（如需要招股书PDF文本信息），输出: NEED_PDF
- 确保SQL语法完全符合SQLite规范

## 辅助视图（已预计算，直接SELECT即可，无需写LAG/窗口函数）

为提高准确率，系统已创建3个临时视图，包含预计算字段：

1. **stock_daily_change** — A股日涨跌幅视图
   字段: 股票代码, 交易日, 收盘价(元), 昨收盘(元), 涨跌幅(已用公式(收盘-昨收)/昨收*100算好)
   用途: 查询涨跌幅时直接WHERE+ORDER BY，**禁止使用LAG函数**

2. **hk_stock_daily_change** — 港股日涨跌幅视图（结构同上）
   字段: 股票代码, 交易日, 收盘价(元), 昨收盘(元), 涨跌幅

3. **stock_limit_up** — A股涨停标记视图
   字段: 股票代码, 交易日, 是否涨停(1=涨停, 0=未涨停)
   用途: 统计涨停天数时直接SUM(是否涨停)，**禁止用LAG自算**

⚠️ 涨跌幅、涨停相关问题必须使用上述视图，不要用原表+LAG！视图用双引号包裹如 "stock_daily_change"。

## Few-Shot 示例

示例1：
问题：股票002244在20191220日期中的收盘价是多少?（小数点保留3位）
SQL：SELECT ROUND("收盘价(元)", 3) AS 收盘价 FROM "A股票日行情表" WHERE "股票代码" = '002244' AND "交易日" = '20191220'

示例2：
问题：20210304日，一级行业为非银金融的股票的成交量合计是多少？取整。
SQL：SELECT CAST(SUM(b."成交量(股)") AS INTEGER) AS 成交量合计 FROM "A股公司行业划分表" a INNER JOIN "A股票日行情表" b ON a."股票代码" = b."股票代码" AND a."交易日期" = b."交易日" WHERE a."一级行业名称" = '非银金融' AND b."交易日" = '20210304'

示例3：
问题：嘉实基金管理有限公司2019年成立了多少基金?
SQL：SELECT COUNT(*) AS 基金数量 FROM "基金基本信息" WHERE "管理人" LIKE '%嘉实%' AND "成立日期" >= '20190101' AND "成立日期" <= '20191231'

示例4：
问题：在20210105，中信行业分类划分的一级行业为综合金融行业中，涨跌幅最大股票的股票代码是？涨跌幅是多少？
SQL：SELECT s."股票代码", ROUND(s.涨跌幅, 2) AS 涨跌幅 FROM "stock_daily_change" s INNER JOIN "A股公司行业划分表" i ON s."股票代码" = i."股票代码" AND s."交易日" = i."交易日期" WHERE i."行业划分标准" = '中信行业分类' AND i."一级行业名称" = '综合金融' AND s."交易日" = '20210105' AND s.涨跌幅 IS NOT NULL ORDER BY s.涨跌幅 DESC LIMIT 1

示例5：
问题：2021年度688338股票涨停天数？
SQL：SELECT SUM("是否涨停") AS 涨停天数 FROM "stock_limit_up" WHERE "股票代码" = '688338' AND "交易日" >= '20210101' AND "交易日" <= '20211231'

示例6：
问题：2019年三季度有多少家基金是净申购?
SQL：SELECT COUNT(*) AS 净申购家数 FROM "基金规模变动表" WHERE "报告期基金总申购份额" > "报告期基金总赎回份额" AND "定期报告所属年度" = 2019 AND "报告类型" = '季报' AND "截止日期" >= '20190701' AND "截止日期" <= '20190930'

示例7（PDF类问题，无法用SQL回答）：
问题：湖南长远锂科股份有限公司变更设立时作为发起人的法人有哪些？
SQL：NEED_PDF
"""
    return system_prompt  # 返回构建好的系统提示词


def build_user_prompt(question):
    """根据用户问题构建User Prompt"""
    user_prompt = f"请将以下问题转换为SQL查询语句：\n\n{question}"
    return user_prompt  # 返回用户提示词


def build_messages(system_prompt, question):
    """构建完整的messages列表，用于DeepSeek API调用"""
    messages = [  # 构建消息列表
        {"role": "system", "content": system_prompt},  # 系统角色：设定SQL专家行为
        {"role": "user", "content": build_user_prompt(question)}  # 用户角色：提问题
    ]
    return messages  # 返回消息列表


# 测试代码
if __name__ == "__main__":  # 如果直接运行
    import config  # 导入配置
    from db_explorer import explore_database  # 导入数据库探索函数
    db_info = explore_database(config.DB_PATH)  # 探索数据库
    system = build_system_prompt(  # 构建系统提示词
        db_info["schema_description"],  # schema描述
        db_info["relationship_description"]  # 关系描述
    )
    logger.info(f"System Prompt 长度: {len(system)} 字符")
    # 测试一个示例问题
    test_q = "股票002244在20191220日期中的收盘价是多少?"
    msgs = build_messages(system, test_q)  # 构建消息
    logger.info(f"测试问题: {test_q}")
    logger.info(f"消息数: {len(msgs)}")
