# -*- coding: utf-8 -*-
"""
tool_register.py — 医疗挂号写操作业务模块
--------------------------------------------------------------
功能: 挂号管理中修改数据库的写操作, 所有写入通过 SQLite 事务保证:
  1. make_registration  — 创建挂号(事务: INSERT register + UPDATE schedule -1)
  2. cancel_registration — 取消挂号(事务: UPDATE register + UPDATE schedule +1)

包含替代号源推荐逻辑(无专家号时自动建议普通号)。

依赖: db_helpers.py, tool_query.py

工单编号: 人工智能NLP-Agent数字人项目-医疗智能体-挂号管理任务
"""
import logging                              # 日志记录
from datetime import timedelta              # 日期范围(±3天)
from db_helpers import (                    # 导入辅助函数
    get_db, resolve_dept, resolve_family_member,
    parse_time_expression, DOCTOR_TITLE_MAP
)
from tool_query import query_schedule       # 导入号源查询(复用)

logger = logging.getLogger("agent.tools")   # 工具模块日志器


def make_registration(user_id: int = 1, patient_name: str = None,
                      dep_name: str = None, doctor_name: str = None,
                      target_date: str = None, period: str = None,
                      title_filter: str = None) -> dict:
    """创建挂号 — 事务保证号源扣减与记录创建原子性。

    业务流程:
      ① 解析患者(含大宝/二宝等家人关系)
      ② 解析科室名称(别名+模糊匹配)
      ③ 查询匹配号源(科室/日期/时段/职称)
      ④ 无号源时查询替代方案并提示用户
      ⑤ 事务: INSERT register记录 + UPDATE schedule号源-1

    返回:
        {"success": bool, "result": str(自然语言), "data": dict|None}

    工单编号: 人工智能NLP-Agent数字人项目-医疗智能体-挂号管理任务
    """
    conn = get_db()                          # 获取数据库连接
    conn.execute("PRAGMA foreign_keys = ON") # 启用外键约束(保证引用完整性)
    cur = conn.cursor()                      # 创建游标

    try:
        # === ① 解析患者身份(含家人关系) ===
        family_info = None                   # 家人信息(大宝/二宝)
        if patient_name:                     # 用户指定了就诊人
            family_info = resolve_family_member(patient_name, user_id)
            # 如果指定了家人名但未匹配, 检查是否用户本人
            if not family_info:
                cur.execute("SELECT * FROM patient WHERE p_ID=? AND p_Name=?",
                           (user_id, patient_name))
                self_row = cur.fetchone()
                if not self_row:             # 既不是家人也不是自己→报错
                    conn.close()
                    return {"success": False,
                            "result": f"未找到就诊人: {patient_name}（可用: 张三/大宝/二宝）",
                            "data": None}
        # 获取用户基本信息
        row = cur.execute("SELECT * FROM patient WHERE p_ID=?", (user_id,)).fetchone()
        if not row:                          # 用户ID无效
            conn.close()
            return {"success": False, "result": f"未找到用户(ID={user_id})", "data": None}
        patient_info = dict(row)
        # 确定实际就诊人姓名(家人名 > 自己名)
        actual_patient = family_info["fm_Name"] if family_info else patient_info["p_Name"]

        # === ② 解析科室 ===
        dept = resolve_dept(dep_name) if dep_name else None
        if dep_name and not dept:            # 科室名无法匹配
            conn.close()
            return {"success": False, "result": f"未找到科室: {dep_name}", "data": None}

        # === ③ 查询精确匹配的号源 ===
        schedules = query_schedule(           # 调用查询函数(严格条件)
            dep_name=dep_name, target_date=target_date,
            period=period, doctor_name=doctor_name,
            title_filter=title_filter)

        # === ④ 无号源 → 查询替代方案 ===
        if not schedules:
            # 放宽条件(去掉职称/医生限制)重查
            alt = query_schedule(
                dep_name=dep_name, target_date=target_date, period=period)
            if alt:                          # 有替代号源
                names = {s["d_Name"] for s in alt}
                titles = {s["d_Profession"] for s in alt}
                dept_label = dept["dep_Name"] if dept else dep_name
                return {"success": False,
                        "result": (f"抱歉，{dept_label}{target_date or ''}"
                                  f"{period or ''}没有"
                                  f"{'专家号' if title_filter=='专家' else '号源'}。\n"
                                  f"可选医生: {', '.join(sorted(names))}"
                                  f"({', '.join(sorted(titles))})，需要为您挂号吗？"),
                        "data": {"alternatives": alt}}

            # 进一步放宽：去掉日期限制，查找该科室最近有号的日期
            alt_all = query_schedule(dep_name=dep_name)
            dept_label = dept["dep_Name"] if dept else dep_name
            if alt_all:
                # 找到最近的可用日期
                dates = sorted({s["sch_Date"] for s in alt_all})
                periods = sorted({s["sch_Period"] for s in alt_all})
                date_str = "、".join(dates[:3])
                period_str = "、".join(periods)
                # 检查是否周末
                from datetime import date as dt_date
                weekday_names = ["周一","周二","周三","周四","周五","周六","周日"]
                target_dt = dt_date.fromisoformat(target_date) if target_date else dt_date.today()
                wd = weekday_names[target_dt.weekday()]
                hint = f"（{target_date}是{wd}，该科室可能周末无排班）" if wd in ("周六","周日") else ""
                conn.close()
                return {"success": False,
                        "result": (f"抱歉，{dept_label}在{target_date or '指定日期'}"
                                  f"{period or ''}暂无可用号源。{hint}\n"
                                  f"最近有号日期: {date_str}（{period_str}时段）\n"
                                  f"是否需要为您预约最近日期的号？"),
                        "data": {"alternatives": alt_all, "available_dates": dates}}
            conn.close()
            return {"success": False,
                    "result": f"抱歉，{dep_name or '该科室'}暂无可用号源。", "data": None}

        # === ⑤ 选择最佳号源 + 事务执行 ===
        best = schedules[0]                  # 默认取第1个
        for s in schedules:                  # 医生名匹配则优先
            if doctor_name and doctor_name in s.get("d_Name", ""):
                best = s; break

        order_num = cur.execute(             # 获取新挂号序号
            "SELECT COALESCE(MAX(reg_Order),0)+1 FROM register").fetchone()[0]
        # 插入挂号记录(status=0已预约)
        cur.execute("""
            INSERT INTO register (dep_ID, p_ID, d_ID, reg_Time, reg_Fee, reg_Order, reg_Status)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (best["dep_ID"], user_id, best["d_ID"],
              f"{best['sch_Date']} {best['sch_Period']}",
              best["sch_Fee"], order_num))
        reg_id = cur.lastrowid               # 获取自增挂号ID
        # 号源剩余数-1
        cur.execute(
            "UPDATE schedule SET sch_Remain = sch_Remain - 1 WHERE sch_ID = ?",
            (best["sch_ID"],))
        conn.commit()                        # 提交事务(原子操作)

        result = {
            "success": True,
            "result": (f"✅ 挂号成功！\n"
                      f"患者: {actual_patient}\n"
                      f"科室: {best['dep_Name']}\n"
                      f"医生: {best['d_Name']}({best['d_Profession']})\n"
                      f"时间: {best['sch_Date']} {best['sch_Period']}\n"
                      f"费用: {best['sch_Fee']}元\n"
                      f"挂号单号: {reg_id}\n"
                      f"剩余号源: {best['sch_Remain'] - 1}个"),
            "data": {"reg_ID": reg_id, "schedule": best, "patient": actual_patient}
        }
        conn.close(); return result

    except Exception as e:
        conn.rollback()                      # 异常回滚
        conn.close()
        logger.error("挂号失败: %s", e)
        return {"success": False, "result": f"挂号异常: {str(e)[:100]}", "data": None}


def rebook_from_history(user_id: int = 1, dep_name: str = None,
                         title_filter: str = None, patient_name: str = None,
                         target_date: str = None, period: str = None) -> dict:
    """复约 — 从历史记录中找到医生并重新挂号。

    业务流程:
      ① 查历史 → 找到最近一次匹配的挂号记录(科室+职称)
      ② 获取当时看过的医生信息
      ③ 查该医生当前号源 → 有号直接挂，无号找同科室同职称替代

    参数:
        user_id: 用户ID
        dep_name: 科室名(可选，如"眼科")
        title_filter: 职称(可选，如"专家")
        patient_name: 就诊人(可选)
        target_date: 期望日期(可选，默认今天)
        period: 时段(可选)
    返回:
        {"success": bool, "result": str, "data": dict|None}
    """
    from tool_query import query_registration_history, query_schedule
    from datetime import date as dt_date

    today_str = dt_date.today().strftime("%Y-%m-%d")
    if not target_date:
        target_date = today_str

    logger.info("复约: user=%d dep=%s title=%s date=%s",
                user_id, dep_name, title_filter, target_date)

    # === ① 查历史 — 找最近一次匹配的挂号 ===
    history = query_registration_history(
        user_id=user_id, dep_name=dep_name, title_filter=title_filter)

    if not history:
        dept_label = dep_name or "相关科室"
        title_label = title_filter or ""
        return {"success": False,
                "result": f"未找到您在{dept_label}{title_label}的历史挂号记录，请先挂号。",
                "data": None}

    # 取最近一条(已按时间降序排列)
    latest = history[0]
    doctor_name = latest["d_Name"]
    doctor_title = latest["d_Profession"]
    dept_name = latest["dep_Name"]
    hist_date = latest["reg_Time"][:10] if latest["reg_Time"] else ""

    logger.info("复约 → 找到历史医生: %s(%s %s)", doctor_name, dept_name, doctor_title)

    # === ② 查该医生当前号源(今天起) ===
    schedules = query_schedule(
        dep_name=dept_name, doctor_name=doctor_name,
        target_date=target_date, period=period)

    if schedules:
        # 直接有号 → 走正常挂号流程
        best = schedules[0]
        return make_registration(
            user_id=user_id, patient_name=patient_name,
            dep_name=dept_name, doctor_name=doctor_name,
            target_date=target_date, period=period)
    else:
        # === ③ 指定日期无号 → 自动找该医生最近有号的日期 ===
        all_doc = query_schedule(dep_name=dept_name, doctor_name=doctor_name)
        if all_doc:
            # 取最近的可用日期自动挂号
            nearest = all_doc[0]  # 已按日期升序排列，第一条就是最近
            auto_date = nearest["sch_Date"]
            auto_period = period or nearest["sch_Period"]
            logger.info("复约 → %s无号，自动尝试最近日期 %s", target_date, auto_date)

            # 在该日期精确匹配(含时段/职称)
            exact = query_schedule(
                dep_name=dept_name, doctor_name=doctor_name,
                target_date=auto_date, period=period, title_filter=title_filter)
            if exact:
                return make_registration(
                    user_id=user_id, patient_name=patient_name,
                    dep_name=dept_name, doctor_name=doctor_name,
                    target_date=auto_date, period=period,
                    title_filter=title_filter)
            else:
                # 最近日期有号但职称/时段不匹配，直接用该日期最近时段挂
                same_date = query_schedule(
                    dep_name=dept_name, doctor_name=doctor_name,
                    target_date=auto_date)
                if same_date:
                    return make_registration(
                        user_id=user_id, patient_name=patient_name,
                        dep_name=dept_name, doctor_name=doctor_name,
                        target_date=auto_date, period=(period or same_date[0]["sch_Period"]))

            # 理论上不会到这里
            dates = sorted({s["sch_Date"] for s in all_doc})
            return {"success": False,
                    "result": (
                        f"您之前在{dept_name}看过{doctor_name}({doctor_title})医生({hist_date})。\n"
                        f"当前无合适号源，该医生最近出诊: {', '.join(dates[:5])}。"),
                    "data": None}

        # === ④ 该医生完全无号 → 查同科室同职称替代 ===
        alt_schedules = query_schedule(
            dep_name=dept_name, target_date=target_date,
            period=period, title_filter=title_filter)
        if alt_schedules:
            names = list({s["d_Name"] for s in alt_schedules})
            titles = list({s["d_Profession"] for s in alt_schedules})
            return {"success": False,
                    "result": (
                        f"您之前在{dept_name}看过{doctor_name}({doctor_title})医生({hist_date})。\n"
                        f"该医生近期暂无号源。\n"
                        f"同科室{title_filter or ''}可选: {', '.join(sorted(names))}"
                        f"({', '.join(sorted(titles))})，需要为您挂号吗？"),
                    "data": {"previous_doctor": doctor_name, "alternatives": alt_schedules}}

        # ⑤ 完全没有号源
        return {"success": False,
                "result": (
                    f"您之前在{dept_name}看过{doctor_name}({doctor_title})医生({hist_date})。\n"
                    f"抱歉，该科室近期暂无号源。"),
                "data": None}


def cancel_registration(user_id: int = 1, dep_name: str = None,
                        date_desc: str = None, title_filter: str = None) -> dict:
    """取消挂号 — 事务: 标记取消 + 恢复号源。

    查找策略: 科室(模糊) + 日期描述(±3天容差) + 职称 → 取最佳匹配

    参数:
        user_id: 用户ID
        dep_name: 科室名(如"消化内科")
        date_desc: 日期描述(如"上周三"/"昨天")
        title_filter: 职称(如"普通"/"专家")
    返回:
        {"success": bool, "result": str, "data": dict|None}

    工单编号: 人工智能NLP-Agent数字人项目-医疗智能体-挂号管理任务
    """
    conn = get_db()                          # 获取数据库连接
    conn.execute("PRAGMA foreign_keys = ON") # 启用外键
    cur = conn.cursor()                      # 创建游标

    try:
        # 解析时间表达式 → 目标日期
        time_info = parse_time_expression(date_desc or "")
        target_date = time_info["target_date"].strftime("%Y-%m-%d")

        # 构建查询条件(日期±3天容差, 防止"上周三"因日期计算偏差而漏查)
        conds = ["r.reg_Status = 0", "r.p_ID = ?"]  # 只查有效预约
        params = [user_id]
        if dep_name:                         # 科室模糊匹配
            dept = resolve_dept(dep_name)
            if dept:
                conds.append("r.dep_ID = ?"); params.append(dept["dep_ID"])
            else:
                conds.append("dp.dep_Name LIKE ?"); params.append(f"%{dep_name}%")
        if title_filter:                     # 职称筛选(专家→主任/副主任, 普通→主治)
            allowed = DOCTOR_TITLE_MAP.get(title_filter, [])
            if allowed:
                ph = ",".join("?" * len(allowed))
                conds.append(f"d.d_Profession IN ({ph})")
                params.extend(allowed)
        # 日期范围(目标±3天, 用>= < 避免BETWEEN边界遗漏问题)
        td = time_info["target_date"]
        d_start = (td - timedelta(days=3)).strftime("%Y-%m-%d")
        d_end = (td + timedelta(days=4)).strftime("%Y-%m-%d")  # +4确保覆盖目标日全天
        conds.append("r.reg_Time >= ? AND r.reg_Time < ?")
        params.extend([d_start, d_end])

        # 查询匹配的挂号记录
        cur.execute(f"""
            SELECT r.*, dp.dep_Name, d.d_Name, d.d_Profession, p.p_Name
            FROM register r
            JOIN department dp ON r.dep_ID = dp.dep_ID
            JOIN doctor d ON r.d_ID = d.d_ID
            JOIN patient p ON r.p_ID = p.p_ID
            WHERE {' AND '.join(conds)}
            ORDER BY r.reg_Time DESC
        """, params)
        records = [dict(r) for r in cur.fetchall()]

        if not records:                      # 无匹配记录
            conn.close()
            return {"success": False,
                    "result": f"未找到{date_desc or '相关'}的{title_filter or ''}挂号记录，可能已取消。",
                    "data": None}

        rec = records[0]                     # 取最佳匹配(时间最近)
        reg_id = rec["reg_ID"]

        # 事务: 标记取消 + 恢复号源
        cur.execute("UPDATE register SET reg_Status = 1 WHERE reg_ID = ?", (reg_id,))
        # 从reg_Time提取日期和时段
        sch_date = rec["reg_Time"][:10]      # "2026-06-17 14:00:00" → "2026-06-17"
        reg_hour = int(rec["reg_Time"][11:13]) if len(rec["reg_Time"]) > 10 else 12
        sch_period = "上午" if reg_hour < 12 else "下午"
        # 恢复号源(+1)
        cur.execute("""UPDATE schedule SET sch_Remain = sch_Remain + 1
                       WHERE d_ID = ? AND sch_Date = ? AND sch_Period = ?""",
                   (rec["d_ID"], sch_date, sch_period))
        conn.commit()                        # 提交事务

        conn.close()
        return {"success": True,
                "result": (f"✅ 挂号已取消！\n患者: {rec['p_Name']}\n"
                          f"科室: {rec['dep_Name']}\n医生: {rec['d_Name']}\n"
                          f"时间: {rec['reg_Time']}\n费用: {rec['reg_Fee']}元已退还"),
                "data": rec}
    except Exception as e:
        conn.rollback()                      # 回滚事务
        conn.close()
        logger.error("取消挂号失败: %s", e)
        return {"success": False, "result": f"取消异常: {str(e)[:100]}", "data": None}
