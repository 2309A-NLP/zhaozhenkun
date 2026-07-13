"""工单19：自适应练习、画像更新与错题本记录服务。"""

# 工单19：导入 JSON 工具，用于处理题目选项与变式题列表。
import json

# 工单19：导入时间工具，用于记录练习与错题时间。
from datetime import datetime

# 工单19：导入数据库读写能力。
from development.database import execute_write, fetch_all, fetch_one

# 工单19：导入画像趋势服务，用于练习后刷新趋势。
from development.services.portrait_service import append_trend_snapshot

# 工单19：导入大模型错题解析服务。
from development.services.llm_service import generate_wrong_book_content


# 工单19：读取题目基础信息，并解析选项字段。
def get_question_map():
    rows = fetch_all("SELECT * FROM questions ORDER BY id")
    mapping = {}
    for row in rows:
        row["options"] = json.loads(row["options"])
        mapping[row["id"]] = row
    return mapping


# 工单19：读取学生掌握度，并按知识点编号输出字典结构。
def get_mastery_map(student_id):
    rows = fetch_all("SELECT knowledge_id, score FROM student_mastery WHERE student_id = ?", (student_id,))
    return {row["knowledge_id"]: float(row["score"]) for row in rows}


# 工单19：基于学生掌握度挑选最合适的自适应练习题。
def get_adaptive_questions(student_id, limit=5):
    question_map = get_question_map()
    mastery_map = get_mastery_map(student_id)
    weak_ids = [item[0] for item in sorted(mastery_map.items(), key=lambda pair: pair[1])]
    selected = []
    used_question_ids = set()
    for knowledge_id in weak_ids:
        target_score = mastery_map.get(knowledge_id, 0.0)
        target_difficulty = 1 if target_score < 0.4 else 2 if target_score < 0.6 else 3
        candidate_rows = [item for item in question_map.values() if item["knowledge_id"] == knowledge_id and item["id"] not in used_question_ids]
        candidate_rows.sort(key=lambda item: (abs(item["difficulty"] - target_difficulty), item["id"]))
        if not candidate_rows:
            continue
        question = candidate_rows[0]
        used_question_ids.add(question["id"])
        selected.append(
            {
                "question_id": question["id"],
                "knowledge_id": question["knowledge_id"],
                "question": question["question"],
                "options": question["options"],
                "difficulty": question["difficulty"],
            }
        )
        if len(selected) >= limit:
            break
    return selected


# 工单19：根据答题结果增减知识掌握度，形成持续迭代画像。
def update_mastery(student_id, knowledge_id, is_correct, difficulty):
    row = fetch_one("SELECT score FROM student_mastery WHERE student_id = ? AND knowledge_id = ?", (student_id, knowledge_id))
    old_score = float(row["score"])
    delta = (0.08 + difficulty * 0.015) if is_correct else -(0.05 + difficulty * 0.01)
    new_score = max(0.0, min(1.0, round(old_score + delta, 4)))
    timestamp = datetime.now().isoformat(timespec="seconds")
    execute_write(
        "UPDATE student_mastery SET score = ?, updated_at = ? WHERE student_id = ? AND knowledge_id = ?",
        (new_score, timestamp, student_id, knowledge_id),
    )
    return new_score


# 工单19：生成并写入错题本记录，支撑复盘与变式练习。
def create_wrong_book_entry(student_id, question_row, chosen_answer):
    knowledge_point = fetch_one("SELECT id, name FROM knowledge_points WHERE id = ?", (question_row["knowledge_id"],))
    generated = generate_wrong_book_content(question_row, chosen_answer, knowledge_point)
    execute_write(
        "INSERT INTO wrong_book(student_id, question_id, analysis, reason, variants, created_at, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            student_id,
            question_row["id"],
            generated["analysis"],
            generated["reason"],
            json.dumps(generated["variants"], ensure_ascii=False),
            datetime.now().isoformat(timespec="seconds"),
            "open",
        ),
    )
    return generated


# 工单19：提交练习答案，记录结果并刷新画像与趋势。
def submit_practice(student_id, answers):
    if not answers:
        return {"total": 0, "correct": 0, "wrong": 0, "results": []}
    question_map = get_question_map()
    results = []
    correct_count = 0
    for answer in answers:
        question_id = int(answer["question_id"])
        chosen_answer = answer.get("chosen_answer", "")
        question_row = question_map[question_id]
        is_correct = int(chosen_answer == question_row["answer"])
        correct_count += is_correct
        execute_write(
            "INSERT INTO practice_records(student_id, question_id, chosen_answer, is_correct, created_at) VALUES (?, ?, ?, ?, ?)",
            (student_id, question_id, chosen_answer, is_correct, datetime.now().isoformat(timespec="seconds")),
        )
        new_score = update_mastery(student_id, question_row["knowledge_id"], bool(is_correct), question_row["difficulty"])
        wrong_book_payload = None
        if not is_correct:
            wrong_book_payload = create_wrong_book_entry(student_id, question_row, chosen_answer)
        results.append(
            {
                "question_id": question_id,
                "question": question_row["question"],
                "chosen_answer": chosen_answer,
                "correct_answer": question_row["answer"],
                "is_correct": bool(is_correct),
                "knowledge_id": question_row["knowledge_id"],
                "knowledge_score": round(new_score * 100),
                "wrong_book": wrong_book_payload,
            }
        )
    append_trend_snapshot(student_id)
    return {
        "total": len(answers),
        "correct": correct_count,
        "wrong": len(answers) - correct_count,
        "results": results,
    }
