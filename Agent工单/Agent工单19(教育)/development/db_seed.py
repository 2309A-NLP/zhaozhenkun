"""工单19：数据库种子数据写入模块。"""

# 工单19：导入 JSON 工具，用于序列化知识点依赖与题目选项。
import json

# 工单19：导入时间工具，用于记录初始化时间。
from datetime import datetime

# 工单19：导入演示种子数据。
from development.data.seed_content import ASSISTANT_FAQS, INITIAL_MASTERY, KNOWLEDGE_POINTS, QUESTIONS, RESOURCES, STUDENTS, TREND_SAMPLES


# 工单19：将知识点与题库数据转换为可直接入库的结构。
def build_seed_rows():
    knowledge_rows = [{**item, "prerequisites": json.dumps(item["prerequisites"], ensure_ascii=False)} for item in KNOWLEDGE_POINTS]
    question_rows = [{**item, "options": json.dumps(item["options"], ensure_ascii=False)} for item in QUESTIONS]
    return knowledge_rows, question_rows


# 工单19：向空表写入演示数据，避免重复插入。
def seed_database(connection):
    cursor = connection.cursor()
    if cursor.execute("SELECT COUNT(*) FROM students").fetchone()[0] > 0:
        return
    knowledge_rows, question_rows = build_seed_rows()
    cursor.executemany("INSERT INTO students(id, name, level, target_role) VALUES (:id, :name, :level, :target_role)", STUDENTS)
    cursor.executemany("INSERT INTO knowledge_points(id, name, description, difficulty, prerequisites) VALUES (:id, :name, :description, :difficulty, :prerequisites)", knowledge_rows)
    cursor.executemany("INSERT INTO resources(id, knowledge_id, title, type, minutes, description) VALUES (:id, :knowledge_id, :title, :type, :minutes, :description)", RESOURCES)
    cursor.executemany("INSERT INTO assistant_faqs(id, knowledge_id, question, answer) VALUES (:id, :knowledge_id, :question, :answer)", ASSISTANT_FAQS)
    cursor.executemany("INSERT INTO questions(id, knowledge_id, question, options, answer, difficulty, common_error) VALUES (:id, :knowledge_id, :question, :options, :answer, :difficulty, :common_error)", question_rows)
    timestamp = datetime.now().isoformat(timespec="seconds")
    for student_id, mastery_map in INITIAL_MASTERY.items():
        mastery_rows = [(student_id, knowledge_id, score, timestamp) for knowledge_id, score in mastery_map.items()]
        cursor.executemany("INSERT INTO student_mastery(student_id, knowledge_id, score, updated_at) VALUES (?, ?, ?, ?)", mastery_rows)
    for student_id, scores in TREND_SAMPLES.items():
        trend_rows = [(student_id, index, score) for index, score in enumerate(scores, start=1)]
        cursor.executemany("INSERT INTO trend_history(student_id, day_index, score) VALUES (?, ?, ?)", trend_rows)
    connection.commit()
