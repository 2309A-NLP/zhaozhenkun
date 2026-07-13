"""工单19：数据库表结构初始化模块。"""

# 工单19：定义项目全部表结构，供首次启动时统一初始化。
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    level TEXT NOT NULL,
    target_role TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS knowledge_points (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    difficulty INTEGER NOT NULL,
    prerequisites TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS resources (
    id INTEGER PRIMARY KEY,
    knowledge_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    type TEXT NOT NULL,
    minutes INTEGER NOT NULL,
    description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS assistant_faqs (
    id INTEGER PRIMARY KEY,
    knowledge_id INTEGER NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY,
    knowledge_id INTEGER NOT NULL,
    question TEXT NOT NULL,
    options TEXT NOT NULL,
    answer TEXT NOT NULL,
    difficulty INTEGER NOT NULL,
    common_error TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS student_mastery (
    student_id INTEGER NOT NULL,
    knowledge_id INTEGER NOT NULL,
    score REAL NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (student_id, knowledge_id)
);
CREATE TABLE IF NOT EXISTS practice_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    chosen_answer TEXT NOT NULL,
    is_correct INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS wrong_book (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    analysis TEXT NOT NULL,
    reason TEXT NOT NULL,
    variants TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trend_history (
    student_id INTEGER NOT NULL,
    day_index INTEGER NOT NULL,
    score INTEGER NOT NULL,
    PRIMARY KEY (student_id, day_index)
);
"""


# 工单19：执行表结构初始化，保证数据库拥有完整可用的表。
def initialize_schema(connection):
    connection.cursor().executescript(SCHEMA_SQL)
    connection.commit()
