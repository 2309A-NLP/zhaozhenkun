"""工单19：学生画像、趋势分析与仪表盘聚合服务。"""

# 工单19：导入 JSON 工具，用于解析错题变式题列表。
import json

# 工单19：导入时间工具，用于记录画像更新时间。
from datetime import datetime

# 工单19：导入数据库读写能力。
from development.database import execute_write, fetch_all, fetch_one

# 工单19：导入推荐服务，用于聚合首页数据。
from development.services.recommendation_service import build_learning_path, build_resource_recommendations, build_today_tasks


# 工单19：读取学生基础信息。
def get_student(student_id):
    return fetch_one("SELECT * FROM students WHERE id = ?", (student_id,))


# 工单19：读取所有学生列表，供登录切换与顶部下拉使用。
def get_students():
    return fetch_all("SELECT * FROM students ORDER BY id")


# 工单19：读取知识掌握度明细，并转换为前端友好的百分比结构。
def get_mastery_levels(student_id):
    rows = fetch_all(
        "SELECT kp.id, kp.name, kp.description, kp.difficulty, sm.score, sm.updated_at FROM student_mastery sm JOIN knowledge_points kp ON sm.knowledge_id = kp.id WHERE sm.student_id = ? ORDER BY sm.score ASC, kp.id ASC",
        (student_id,),
    )
    levels = []
    for row in rows:
        score = float(row["score"])
        levels.append(
            {
                "knowledge_id": row["id"],
                "title": row["name"],
                "description": row["description"],
                "difficulty": row["difficulty"],
                "score": round(score * 100),
                "band": "薄弱" if score < 0.5 else "提升中" if score < 0.75 else "已掌握",
                "updated_at": row["updated_at"],
            }
        )
    return levels


# 工单19：汇总最近练习趋势，支持首页折线图展示。
def get_trend_points(student_id):
    rows = fetch_all("SELECT day_index, score FROM trend_history WHERE student_id = ? ORDER BY day_index DESC LIMIT 7", (student_id,))
    rows.reverse()
    return [{"label": f"D{row['day_index']}", "score": row["score"]} for row in rows]


# 工单19：读取错题本明细，并附带变式题内容。
def get_wrong_book_items(student_id, limit=6):
    rows = fetch_all(
        "SELECT wb.id, wb.analysis, wb.reason, wb.variants, wb.status, wb.created_at, q.question, q.answer, kp.name AS knowledge_name FROM wrong_book wb JOIN questions q ON wb.question_id = q.id JOIN knowledge_points kp ON q.knowledge_id = kp.id WHERE wb.student_id = ? ORDER BY wb.id DESC LIMIT ?",
        (student_id, limit),
    )
    items = []
    for row in rows:
        items.append(
            {
                "id": row["id"],
                "question": row["question"],
                "answer": row["answer"],
                "knowledge_name": row["knowledge_name"],
                "analysis": row["analysis"],
                "reason": row["reason"],
                "variants": json.loads(row["variants"]),
                "status": row["status"],
                "created_at": row["created_at"],
            }
        )
    return items


# 工单19：根据知识掌握、练习和错题汇总首页关键指标。
def get_summary(student_id):
    levels = get_mastery_levels(student_id)
    overall = round(sum(item["score"] for item in levels) / len(levels)) if levels else 0
    mastered = len([item for item in levels if item["score"] >= 75])
    risk = len([item for item in levels if item["score"] < 50])
    recent = fetch_all("SELECT is_correct FROM practice_records WHERE student_id = ? ORDER BY id DESC LIMIT 10", (student_id,))
    accuracy = round(sum(item["is_correct"] for item in recent) * 100 / len(recent)) if recent else 0
    strengths = [item["title"] for item in sorted(levels, key=lambda entry: entry["score"], reverse=True)[:2]]
    gaps = [item["title"] for item in levels[:3]]
    return {
        "overall_score": overall,
        "mastered_count": mastered,
        "risk_count": risk,
        "recent_accuracy": accuracy,
        "strengths": strengths,
        "gaps": gaps,
    }


# 工单19：向趋势历史中追加新的总体分数快照。
def append_trend_snapshot(student_id):
    levels = get_mastery_levels(student_id)
    overall = round(sum(item["score"] for item in levels) / len(levels)) if levels else 0
    max_row = fetch_one("SELECT COALESCE(MAX(day_index), 0) AS max_day FROM trend_history WHERE student_id = ?", (student_id,))
    next_day = max_row["max_day"] + 1
    execute_write("INSERT OR REPLACE INTO trend_history(student_id, day_index, score) VALUES (?, ?, ?)", (student_id, next_day, overall))


# 工单19：导入历史成绩，快速建立学生初始画像。
def import_historical_score(student_id, score):
    bounded = max(0, min(100, int(score)))
    rows = fetch_all("SELECT knowledge_id, score FROM student_mastery WHERE student_id = ? ORDER BY knowledge_id", (student_id,))
    timestamp = datetime.now().isoformat(timespec="seconds")
    for index, row in enumerate(rows, start=1):
        old_score = float(row["score"])
        target_score = max(0.15, min(0.95, bounded / 100 - index * 0.02 + 0.12))
        new_score = round(old_score * 0.55 + target_score * 0.45, 4)
        execute_write(
            "UPDATE student_mastery SET score = ?, updated_at = ? WHERE student_id = ? AND knowledge_id = ?",
            (new_score, timestamp, student_id, row["knowledge_id"]),
        )
    append_trend_snapshot(student_id)
    return get_dashboard_snapshot(student_id)


# 工单19：聚合首页仪表盘所需全部数据。
def get_dashboard_snapshot(student_id):
    return {
        "student": get_student(student_id),
        "students": get_students(),
        "summary": get_summary(student_id),
        "mastery_levels": get_mastery_levels(student_id),
        "learning_path": build_learning_path(student_id),
        "today_tasks": build_today_tasks(student_id),
        "resources": build_resource_recommendations(student_id),
        "wrong_book": get_wrong_book_items(student_id),
        "trend_points": get_trend_points(student_id),
    }
