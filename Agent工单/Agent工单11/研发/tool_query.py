# -*- coding: utf-8 -*-
"""
tool_query.py — 医疗挂号查询业务模块
--------------------------------------------------------------
功能: 挂号管理中的只读查询操作, 不修改数据库:
  1. query_schedule              — 多条件号源查询
  2. query_registration_history  — 用户历史挂号记录
  3. query_doctor_schedule       — 医生坐诊排班表
  4. get_dept_list               — 科室列表

依赖: db_helpers.py (数据库连接, 科室/医生/时间解析)

工单编号: 人工智能NLP-Agent数字人项目-医疗智能体-挂号管理任务
"""
import logging                              # 日志记录
from datetime import date, timedelta        # 日期范围计算
from db_helpers import (                    # 导入辅助函数
    get_db, resolve_dept, resolve_doctor, DOCTOR_TITLE_MAP
)

logger = logging.getLogger("agent.tools")   # 工具模块日志器


def query_schedule(dep_name: str = None, doctor_name: str = None,
                   target_date: str = None, period: str = None,
                   title_filter: str = None) -> list:
    """查询可用号源 — 支持科室/医生/日期/时段/职称5维筛选。
    参数:
        dep_name: 科室名(可选, 如"儿科"/"牙科")
        doctor_name: 医生姓名(可选)
        target_date: 日期 YYYY-MM-DD(可选)
        period: 时段 "上午"/"下午"(可选)
        title_filter: 职称 "专家"/"普通"(可选)
    返回:
        list[dict]: [{sch_ID, d_Name, d_Profession, dep_Name, sch_Date,
                      sch_Period, sch_Remain, sch_Fee}, ...]
    """
    conn = get_db()                          # 获取数据库连接
    cur = conn.cursor()                      # 创建游标
    # 构建基础条件(有剩余 + 状态正常)
    conditions = ["sch_Remain > 0", "sch_Status = 0"]
    params = []
    if target_date:                          # 用户指定了具体日期
        conditions.append("s.sch_Date = ?"); params.append(target_date)
    else:
        # 未指定日期时，默认只看今天及未来（"最近的号"不应返回过去日期）
        conditions.append("s.sch_Date >= date('now')")
    if period:                               # 时段筛选(上午/下午)
        conditions.append("s.sch_Period = ?"); params.append(period)
    # 联表查询: schedule → doctor → department
    cur.execute(f"""
        SELECT s.*, d.d_ID, d.dep_ID, d.d_Name, d.d_Profession, dp.dep_Name
        FROM schedule s
        JOIN doctor d ON s.d_ID = d.d_ID
        JOIN department dp ON d.dep_ID = dp.dep_ID
        WHERE {' AND '.join(conditions)}
        ORDER BY s.sch_Date, s.sch_Period, dp.dep_Name
    """, params)
    results = [dict(r) for r in cur.fetchall()]  # Row对象→普通dict
    # 科室名称过滤(支持别名+模糊)
    if dep_name:
        dept = resolve_dept(dep_name)        # 解析科室(别名表)
        if dept:
            results = [r for r in results if r["dep_Name"] == dept["dep_Name"]]
        else:
            results = [r for r in results if dep_name in r.get("dep_Name", "")]
    # 医生姓名过滤
    if doctor_name:
        results = [r for r in results if doctor_name in r.get("d_Name", "")]
    # 职称过滤(专家→主任/副主任, 普通→主治)
    if title_filter:
        allowed = DOCTOR_TITLE_MAP.get(title_filter, [])
        if allowed:
            results = [r for r in results if r.get("d_Profession") in allowed]
    conn.close()
    return results


def query_registration_history(user_id: int = 1, dep_name: str = None,
                                title_filter: str = None) -> list:
    """查询用户历史挂号记录(最近10条, 含已取消/已完成)。
    参数:
        user_id: 用户ID(默认1=张三)
        dep_name: 科室名(可选过滤)
        title_filter: 职称过滤 "专家"/"普通"(可选)
    返回:
        list[dict]: [{reg_ID, dep_Name, d_Name, d_Profession, p_Name,
                      reg_Time, reg_Fee, reg_Status}, ...]
    """
    conn = get_db()                          # 获取数据库连接
    cur = conn.cursor()                      # 创建游标
    conds = ["r.p_ID = ?"]                   # 按用户ID筛选
    params = [user_id]
    if dep_name:                             # 可选科室过滤
        dept = resolve_dept(dep_name)
        if dept:
            conds.append("r.dep_ID = ?"); params.append(dept["dep_ID"])
    if title_filter:                         # 职称过滤(专家→主任/副主任, 普通→主治)
        allowed = DOCTOR_TITLE_MAP.get(title_filter, [])
        if allowed:
            ph = ",".join("?" * len(allowed))
            conds.append(f"d.d_Profession IN ({ph})")
            params.extend(allowed)
    # 联表查询: register → department → doctor → patient
    cur.execute(f"""
        SELECT r.*, dp.dep_Name, d.d_Name, d.d_Profession, p.p_Name
        FROM register r
        JOIN department dp ON r.dep_ID = dp.dep_ID
        JOIN doctor d ON r.d_ID = d.d_ID
        JOIN patient p ON r.p_ID = p.p_ID
        WHERE {' AND '.join(conds)}
        ORDER BY r.reg_Time DESC LIMIT 10
    """, params)
    results = [dict(r) for r in cur.fetchall()]
    conn.close()
    return results


def query_doctor_schedule(doctor_name: str) -> dict:
    """查询指定医生未来7天坐诊排班表。
    参数:
        doctor_name: 医生姓名(如"张建国")
    返回:
        {"success": bool, "result": str(格式化文本), "data": list}
    """
    conn = get_db()                          # 获取数据库连接
    cur = conn.cursor()                      # 创建游标
    doctors = resolve_doctor(doctor_name)    # 解析医生(精确→模糊)
    if not doctors:                          # 未找到
        conn.close()
        return {"success": False, "result": f"未找到医生: {doctor_name}", "data": None}
    doc = doctors[0]                         # 取最佳匹配
    today = date.today().strftime("%Y-%m-%d")
    end = (date.today() + timedelta(days=7)).strftime("%Y-%m-%d")  # 7天范围
    # 查询该医生未来7天排班
    cur.execute("""
        SELECT s.*, d.d_Name, d.d_Profession, dp.dep_Name
        FROM schedule s JOIN doctor d ON s.d_ID = d.d_ID
        JOIN department dp ON d.dep_ID = dp.dep_ID
        WHERE d.d_ID = ? AND s.sch_Date BETWEEN ? AND ?
        ORDER BY s.sch_Date, s.sch_Period
    """, (doc["d_ID"], today, end))
    schedules = [dict(r) for r in cur.fetchall()]
    conn.close()

    if not schedules:                        # 无排班
        return {"success": True,
                "result": f"{doc['d_Name']}医生({doc['dep_Name']})未来7天暂无排班。",
                "data": []}
    # 格式化输出
    lines = [f"📅 {doc['d_Name']}医生 ({doc['dep_Name']} {doc['d_Profession']}) 坐诊安排:"]
    for s in schedules:
        lines.append(f"  {s['sch_Date']} {s['sch_Period']} | "
                    f"剩余{s['sch_Remain']}号 | {s['sch_Fee']}元")
    return {"success": True, "result": "\n".join(lines), "data": schedules}


def get_dept_list() -> list:
    """获取所有科室列表(按ID排序)。
    返回:
        list[dict]: [{dep_ID, dep_Name, dep_Address}, ...]
    """
    conn = get_db()                          # 获取数据库连接
    cur = conn.cursor()                      # 创建游标
    cur.execute("SELECT * FROM department ORDER BY dep_ID")
    results = [dict(r) for r in cur.fetchall()]
    conn.close()
    return results
