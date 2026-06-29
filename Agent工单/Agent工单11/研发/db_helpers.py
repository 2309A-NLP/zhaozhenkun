# -*- coding: utf-8 -*-
"""
db_helpers.py — 数据库辅助函数模块
--------------------------------------------------------------
功能: 提供 hospital.db 的底层工具函数, 包括:
  1. 数据库连接管理 (外键约束, Row工厂)
  2. 科室名称解析 (支持别名/模糊匹配)
  3. 医生姓名解析 (支持姓名/科室联合查询)
  4. 家人称呼解析 (大宝/二宝 → 数据库记录)
  5. 中文时间表达式解析 (今天/明天/下周/上周三 → 日期+时段)

被 tool_register.py 导入使用。

工单编号: 人工智能NLP-Agent数字人项目-医疗智能体-挂号管理任务
"""
import sqlite3                              # SQLite 数据库驱动
import logging                              # 日志记录
import re                                   # 正则表达式(小时提取)
from datetime import date, datetime, timedelta  # 日期计算(今天/明天/下周等)

logger = logging.getLogger("agent.tools")   # 工具模块日志器

# 数据库文件路径(项目根目录: hospital.db)
import os as _os
DB_PATH = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "hospital.db")

# ============================================================
# 科室别名映射表 (用户口语 → 数据库正式名)
# ============================================================
DEPT_ALIASES = {
    "儿科": "儿科", "小儿科": "儿科", "儿童科": "儿科",         # 儿科变体
    "牙科": "牙科", "口腔科": "牙科", "口腔": "牙科",           # 牙科变体
    "皮肤科": "皮肤科", "皮肤": "皮肤科",                      # 皮肤科变体
    "消化内科": "消化内科", "消化科": "消化内科", "肠胃科": "消化内科",  # 消化内科变体
    "内科": "内科",                                           # 内科
    "外科": "外科",                                           # 外科
    "妇科": "妇科", "妇产科": "妇科",                          # 妇科变体
    "眼科": "眼科",                                           # 眼科
    "耳鼻喉科": "耳鼻喉科", "耳鼻喉": "耳鼻喉科", "五官科": "耳鼻喉科",  # 耳鼻喉科变体
}

# 医生职称 → 数据库 d_Profession 映射
DOCTOR_TITLE_MAP = {
    "专家": ["主任医师", "副主任医师"],     # 专家号 = 主任/副主任
    "专家号": ["主任医师", "副主任医师"],
    "普通": ["主治医师"],                  # 普通号 = 主治医师
    "普通号": ["主治医师"],
}


def get_db():
    """获取数据库连接, 启用外键约束并设置 Row 工厂。
    返回:
        sqlite3.Connection: 已配置的数据库连接对象
    """
    conn = sqlite3.connect(DB_PATH)            # 连接 SQLite 数据库
    conn.execute("PRAGMA foreign_keys = ON")   # 启用外键约束(级联更新)
    conn.row_factory = sqlite3.Row             # 查询结果可用 dict/行名访问
    return conn


def resolve_dept(query: str) -> dict | None:
    """解析科室名称(三级匹配: 精确→别名→模糊)。
    参数:
        query: 用户输入的口语科室名 (如"儿科"/"口腔科"/"牙")
    返回:
        dict: {dep_ID, dep_Name, dep_Address} 或 None
    """
    conn = get_db()                            # 获取数据库连接
    cur = conn.cursor()                        # 创建游标
    # 第1级: 精确匹配 dep_Name
    cur.execute("SELECT * FROM department WHERE dep_Name=?", (query,))
    row = cur.fetchone()
    if row:
        conn.close(); return dict(row)         # 命中, 返回
    # 第2级: 别名表映射
    alias = DEPT_ALIASES.get(query, query)     # 查别名表, 无则用原名
    if alias != query:                         # 别名不同于原名
        cur.execute("SELECT * FROM department WHERE dep_Name=?", (alias,))
        row = cur.fetchone()
        if row:
            conn.close(); return dict(row)     # 别名命中
    # 第3级: LIKE 模糊匹配 (如"牙" → "牙科")
    cur.execute("SELECT * FROM department WHERE dep_Name LIKE ?", (f"%{query}%",))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None          # 返回结果或None


def resolve_doctor(query: str, dep_id: int = None) -> list:
    """解析医生(姓名精确→模糊, 可选科室过滤)。
    参数:
        query: 医生姓名片段
        dep_id: 科室ID (可选, 用于缩小范围)
    返回:
        list[dict]: 医生信息列表 [{d_ID, d_Name, d_Profession, dep_ID, dep_Name}]
    """
    conn = get_db()                            # 获取数据库连接
    cur = conn.cursor()                        # 创建游标
    # 第1步: 姓名精确匹配
    cur.execute(
        "SELECT d.*, dp.dep_Name FROM doctor d JOIN department dp ON d.dep_ID=dp.dep_ID "
        "WHERE d.d_Name=?", (query,))
    row = cur.fetchone()
    if row:
        results = [dict(row)]                  # 精确命中
    else:
        # 第2步: 姓名 LIKE 模糊匹配
        cur.execute(
            "SELECT d.*, dp.dep_Name FROM doctor d JOIN department dp ON d.dep_ID=dp.dep_ID "
            "WHERE d.d_Name LIKE ?", (f"%{query}%",))
        results = [dict(r) for r in cur.fetchall()]
    # 第3步: 按科室过滤(如果指定)
    if dep_id and results:
        results = [r for r in results if r.get("dep_ID") == dep_id]
    conn.close()
    return results


def resolve_family_member(query: str, user_id: int = 1) -> dict | None:
    """解析家人称呼(大宝/二宝 → family_member记录)。
    参数:
        query: 家人称呼 (如"大宝"/"二宝")
        user_id: 用户ID (默认1=张三)
    返回:
        dict: {fm_ID, fm_Name, fm_Relation, p_ID, fm_Sex, fm_Birth} 或 None
    """
    conn = get_db()                            # 获取数据库连接
    cur = conn.cursor()                        # 创建游标
    # 精确匹配家人姓名 + 用户ID
    cur.execute("SELECT * FROM family_member WHERE fm_Name=? AND p_ID=?",
               (query, user_id))
    row = cur.fetchone()
    if row:
        conn.close(); return dict(row)         # 精确命中
    # 模糊匹配(如"宝" → "大宝")
    cur.execute("SELECT * FROM family_member WHERE fm_Name LIKE ? AND p_ID=?",
               (f"%{query}%", user_id))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None          # 返回结果或None


def parse_time_expression(text: str) -> dict:
    """解析中文时间表达式为结构化日期+时段。
    支持:
      - 相对日期: 今天/明天/后天/大后天/昨天/前天
      - 周几: 周一~周日, 下周X, 上周X
      - 时段: 上午/下午/中午/晚上
      - 时间点: N点/N:00

    参数:
        text: 包含时间描述的用户输入
    返回:
        dict: {target_date: date对象, period: "上午"/"下午"/None, hour: int/None}

    工单编号: 人工智能NLP-Agent数字人项目-医疗智能体-挂号管理任务
    """
    today = date.today()                       # 当前真实日期(2026-06-26)

    # ---- 日期解析 ----
    target = today                             # 默认今天
    if "今天" in text or "今日" in text:
        target = today                         # 今天
    elif "明天" in text or "明日" in text:
        target = today + timedelta(days=1)     # 明天 = 今天+1
    elif "后天" in text or "后日" in text:
        target = today + timedelta(days=2)     # 后天 = 今天+2
    elif "大后天" in text:
        target = today + timedelta(days=3)     # 大后天 = 今天+3
    elif "昨天" in text or "昨日" in text:
        target = today - timedelta(days=1)     # 昨天 = 今天-1
    elif "前天" in text:
        target = today - timedelta(days=2)     # 前天 = 今天-2

    # ---- 周几解析 (周一~周日) ----
    weekdays = {                               # 中文→数字映射 (周一=0, 周日=6)
        "周一": 0, "周二": 1, "周三": 2, "周四": 3,
        "周五": 4, "周六": 5, "周日": 6,
        "星期一": 0, "星期二": 1, "星期三": 2, "星期四": 3,
        "星期五": 4, "星期六": 5, "星期日": 6,
    }
    for wd_name, wd_num in weekdays.items():   # 遍历所有周几表达
        if wd_name in text:                    # 文本中包含该表达
            days_ahead = wd_num - today.weekday()  # 计算距今天数
            if "下周" in text or "下星期" in text:
                days_ahead += 7                # 下周 → +7天
            elif "上周" in text or "上星期" in text:
                days_ahead -= 7                # 上周 → -7天
            else:
                if days_ahead <= 0:            # 默认取未来最近的那个
                    days_ahead += 7
            target = today + timedelta(days=days_ahead)
            break                              # 找到即退出

    # "下周" 不带具体周几 → 默认下周一
    if ("下周" in text or "下星期" in text) and not any(w in text for w in weekdays):
        days_until_mon = 7 - today.weekday()   # 到下周一天数
        target = today + timedelta(days=days_until_mon)

    # "上周" 不带具体周几 → 默认上周一
    if ("上周" in text or "上星期" in text) and not any(w in text for w in weekdays):
        days_since_mon = today.weekday() + 7   # 到上周一天数
        target = today - timedelta(days=days_since_mon)

    # ---- 时段+时间点解析 ----
    period = None                              # 时段(上午/下午)
    hour = None                                # 小时(0-23)
    time_match = re.search(r'(\d{1,2})[点:：]', text)  # 匹配 "14点" 或 "2:00"
    if time_match:
        hour = int(time_match.group(1))        # 提取小时数字
    if "上午" in text:
        period = "上午"                         # 上午时段
    elif "下午" in text:
        period = "下午"                         # 下午时段
    elif "中午" in text:
        period = "上午"; hour = hour or 12      # 中午默认归上午
    elif "晚上" in text:
        period = "下午"                         # 晚上归下午时段
    # 仅有小时无时段 → 反推时段
    if hour and not period:
        period = "上午" if hour < 12 else "下午"

    return {"target_date": target, "period": period, "hour": hour}
