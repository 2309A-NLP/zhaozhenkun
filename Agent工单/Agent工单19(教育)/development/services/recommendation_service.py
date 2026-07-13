"""工单19：学习路径、今日任务与学习资源推荐服务。"""

# 工单19：导入 JSON 工具，用于解析知识点前置关系。
import json

# 工单19：导入数据库查询能力。
from development.database import fetch_all


# 工单19：读取学生掌握度映射，作为推荐引擎的输入。
def get_mastery_map(student_id):
    rows = fetch_all("SELECT knowledge_id, score FROM student_mastery WHERE student_id = ?", (student_id,))
    return {row["knowledge_id"]: row["score"] for row in rows}


# 工单19：读取知识点图谱并解析前置依赖。
def get_knowledge_graph():
    rows = fetch_all("SELECT * FROM knowledge_points ORDER BY id")
    for row in rows:
        row["prerequisites"] = json.loads(row["prerequisites"])
    return rows


# 工单19：将知识点编号转换为名称，便于前端解释展示。
def get_knowledge_name_map():
    rows = fetch_all("SELECT id, name FROM knowledge_points ORDER BY id")
    return {row["id"]: row["name"] for row in rows}


# 工单19：构建基于知识图谱的可解释学习路径。
def build_learning_path(student_id, limit=6):
    mastery_map = get_mastery_map(student_id)
    knowledge_rows = get_knowledge_graph()
    name_map = {row["id"]: row["name"] for row in knowledge_rows}
    ordered_items = []
    used_ids = set()
    weak_rows = sorted(knowledge_rows, key=lambda item: mastery_map.get(item["id"], 0.0))
    for row in weak_rows:
        if len(ordered_items) >= limit:
            break
        unmet = [item for item in row["prerequisites"] if mastery_map.get(item, 0.0) < 0.75 and item not in used_ids]
        for prerequisite_id in unmet:
            if len(ordered_items) >= limit:
                break
            used_ids.add(prerequisite_id)
            ordered_items.append(
                {
                    "knowledge_id": prerequisite_id,
                    "title": name_map[prerequisite_id],
                    "score": round(mastery_map.get(prerequisite_id, 0.0) * 100),
                    "state": "建议先学",
                    "reason": f"因为后续知识点“{row['name']}”依赖它，所以需要先补齐前置基础。",
                    "dependencies": [],
                    "recommended_minutes": 18,
                }
            )
        if row["id"] in used_ids or mastery_map.get(row["id"], 0.0) >= 0.86:
            continue
        used_ids.add(row["id"])
        dependency_names = [name_map[item] for item in row["prerequisites"]]
        ordered_items.append(
            {
                "knowledge_id": row["id"],
                "title": row["name"],
                "score": round(mastery_map.get(row["id"], 0.0) * 100),
                "state": "立即巩固" if mastery_map.get(row["id"], 0.0) < 0.6 else "冲刺提升",
                "reason": f"当前掌握度较低，且与目标课程路径中的关键能力直接相关。",
                "dependencies": dependency_names,
                "recommended_minutes": 18 + row["difficulty"] * 6,
            }
        )
    return ordered_items[:limit]


# 工单19：结合薄弱知识点和错题记录，生成今日学习任务。
def build_today_tasks(student_id):
    learning_path = build_learning_path(student_id, limit=3)
    wrong_count = fetch_all("SELECT COUNT(*) AS total FROM wrong_book WHERE student_id = ? AND status = 'open'", (student_id,))[0]["total"]
    tasks = []
    for index, item in enumerate(learning_path, start=1):
        tasks.append(
            {
                "id": index,
                "title": f"完成《{item['title']}》定向学习",
                "minutes": item["recommended_minutes"],
                "priority": "高优先级" if index == 1 else "计划内",
                "reason": item["reason"],
            }
        )
    tasks.append(
        {
            "id": 99,
            "title": f"复盘 {wrong_count} 条错题本记录",
            "minutes": 15 + wrong_count * 3,
            "priority": "查漏补缺",
            "reason": "基于近期错题生成解析与变式练习，适合快速纠偏。",
        }
    )
    return tasks


# 工单19：根据学习画像、错题本和助教问题库推荐资源。
def build_resource_recommendations(student_id, limit=5):
    mastery_map = get_mastery_map(student_id)
    weak_ids = [item[0] for item in sorted(mastery_map.items(), key=lambda pair: pair[1])[:4]]
    wrong_ids = fetch_all(
        "SELECT DISTINCT q.knowledge_id FROM wrong_book wb JOIN questions q ON wb.question_id = q.id WHERE wb.student_id = ? ORDER BY wb.id DESC LIMIT 3",
        (student_id,),
    )
    target_ids = list(dict.fromkeys(weak_ids + [row["knowledge_id"] for row in wrong_ids]))
    resources = fetch_all("SELECT * FROM resources ORDER BY id")
    faqs = fetch_all("SELECT * FROM assistant_faqs ORDER BY id")
    faq_map = {row["knowledge_id"]: row for row in faqs}
    selected = []
    for resource in resources:
        if resource["knowledge_id"] not in target_ids and len(selected) >= 2:
            continue
        faq = faq_map.get(resource["knowledge_id"])
        selected.append(
            {
                "id": resource["id"],
                "title": resource["title"],
                "type": resource["type"],
                "minutes": resource["minutes"],
                "description": resource["description"],
                "reason": "该资源与当前薄弱知识点或错题关联度最高。",
                "faq": faq["question"] if faq else "建议先完成相关练习，再回看资源。",
            }
        )
        if len(selected) >= limit:
            break
    return selected
