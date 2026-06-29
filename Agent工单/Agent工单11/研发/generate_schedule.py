# -*- coding: utf-8 -*-
"""
generate_schedule.py — 排班数据生成器
================================================================
功能: 为 hospital.db 批量生成未来 30 天的排班号源数据。

数据规则:
  - 所有科室每天都有排班（含周末）
  - 上午 sch_Total=30, 下午 sch_Total=20
  - sch_Remain 在 40%-100% 之间随机分布（模拟真实预约率）
  - 周末剩余号源略少（模拟周末就诊需求波动）
  - sch_Fee: 主任医师=20元, 副主任医师=15元, 主治医师=15元

运行方式:
      cd Agent工单11
      python 研发/generate_schedule.py

工单编号: 人工智能NLP-Agent数字人项目-医疗智能体-挂号管理任务
"""
import sqlite3
import os
import random
from datetime import date, timedelta

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "hospital.db")

# 医生配置: (d_ID, 姓名, 职称, 科室名, 费用)
DOCTORS = [
    (1,  "张伟",  "主任医师", "内科",   20),
    (2,  "李芳",  "副主任医师", "内科", 15),
    (13, "张建国", "主任医师", "内科",   20),
    (3,  "王强",  "主任医师", "外科",   20),
    (4,  "赵敏",  "主治医师", "外科",   15),
    (5,  "刘洋",  "副主任医师", "儿科", 15),
    (6,  "陈静",  "主任医师", "儿科",   20),
    (7,  "林霞",  "主任医师", "妇科",   20),
    (8,  "黄丽",  "主治医师", "妇科",   15),
    (9,  "周明",  "副主任医师", "眼科", 15),
    (10, "吴丹",  "主任医师", "眼科",   20),
    (11, "郑涛",  "主治医师", "耳鼻喉科", 15),
    (12, "孙悦",  "副主任医师", "耳鼻喉科", 15),
    (14, "钱明",  "副主任医师", "牙科", 15),
    (15, "赵雪",  "主任医师", "牙科",   20),
    (16, "孙伟",  "主治医师", "牙科",   15),
    (17, "杨红",  "主任医师", "皮肤科", 20),
    (18, "马超",  "副主任医师", "皮肤科", 15),
    (19, "朱丽",  "主任医师", "消化内科", 20),
    (20, "胡涛",  "主治医师", "消化内科", 15),
]


def generate(start_date: str, days: int = 30):
    """生成排班数据。

    参数:
        start_date: 起始日期 YYYY-MM-DD
        days: 生成天数
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 获取当前最大 ID
    max_id = cur.execute("SELECT COALESCE(MAX(sch_ID), 0) FROM schedule").fetchone()[0]
    next_id = max_id + 1

    start = date.fromisoformat(start_date)
    inserted = 0

    for day_offset in range(days):
        current_date = start + timedelta(days=day_offset)
        date_str = current_date.strftime("%Y-%m-%d")
        weekday = current_date.weekday()  # 0=Mon, 6=Sun
        is_weekend = weekday >= 5

        for (d_id, name, title, dept, fee) in DOCTORS:
            # 上午
            total_am = 30
            if is_weekend:
                remain_am = random.randint(8, 22)   # 周末剩余偏少
            else:
                remain_am = random.randint(12, 30)  # 工作日正常
            remain_am = min(remain_am, total_am)

            cur.execute(
                "INSERT INTO schedule (sch_ID, d_ID, sch_Date, sch_Period, sch_Total, sch_Remain, sch_Fee, sch_Status) "
                "VALUES (?, ?, ?, '上午', ?, ?, ?, 0)",
                (next_id, d_id, date_str, total_am, remain_am, fee))
            next_id += 1
            inserted += 1

            # 下午
            total_pm = 20
            if is_weekend:
                remain_pm = random.randint(5, 16)
            else:
                remain_pm = random.randint(8, 20)
            remain_pm = min(remain_pm, total_pm)

            cur.execute(
                "INSERT INTO schedule (sch_ID, d_ID, sch_Date, sch_Period, sch_Total, sch_Remain, sch_Fee, sch_Status) "
                "VALUES (?, ?, ?, '下午', ?, ?, ?, 0)",
                (next_id, d_id, date_str, total_pm, remain_pm, fee))
            next_id += 1
            inserted += 1

    conn.commit()
    conn.close()

    print(f"✅ 已生成 {inserted} 条排班记录（{start_date} ~ {(start + timedelta(days=days-1)).strftime('%Y-%m-%d')}）")
    print(f"   sch_ID 范围: {max_id + 1} ~ {next_id - 1}")


if __name__ == "__main__":
    # 从当前数据最后一天(06-30)的下一天开始，生成30天
    generate("2026-07-01", days=30)
