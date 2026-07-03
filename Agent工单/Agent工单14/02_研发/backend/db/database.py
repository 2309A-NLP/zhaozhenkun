"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理 V1.0
SQLite 数据库模块 —— 挂号管理系统（用户/孩子/科室/医生/排班/预约）
================================================================================
"""
import sqlite3, threading
from pathlib import Path
from datetime import datetime, timedelta

# 数据库文件路径（项目根目录 data/hospital.db）
DB_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "hospital.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# 写锁：SQLite 单写多读，写操作串行化防止 database locked 错误
_lock = threading.Lock()

def get_conn():
    """获取数据库连接（WAL 模式 + 外键约束）"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row          # 查询结果可通过列名访问
    conn.execute("PRAGMA journal_mode=WAL") # WAL 模式支持并发读
    conn.execute("PRAGMA foreign_keys=ON") # 启用外键约束
    return conn

def init_db():
    """初始化数据库：建表 + 插入种子数据（仅在首次调用时执行）"""
    with _lock:                              # 串行化写操作
        conn = get_conn()
        # ====== 建表 ======
        conn.executescript("""
        -- 用户表
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        -- 孩子表（一个用户可以有多个孩子）
        CREATE TABLE IF NOT EXISTS children (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            age INTEGER,
            gender TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        -- 科室表
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT
        );
        -- 医生表
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            department_id INTEGER NOT NULL,
            title TEXT NOT NULL,              -- 主任医师/副主任医师/主治医师
            description TEXT,
            FOREIGN KEY(department_id) REFERENCES departments(id)
        );
        -- 排班表（每个医生每天的号源分配）
        CREATE TABLE IF NOT EXISTS schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER NOT NULL,
            date TEXT NOT NULL,               -- YYYY-MM-DD
            time_slot TEXT NOT NULL,          -- 上午/下午
            max_patients INTEGER DEFAULT 20, -- 每个时段最大接诊量
            current_patients INTEGER DEFAULT 0, -- 已挂号人数
            FOREIGN KEY(doctor_id) REFERENCES doctors(id),
            UNIQUE(doctor_id, date, time_slot)
        );
        -- 预约表
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            child_id INTEGER,                -- 可为空（自己看病）
            doctor_id INTEGER NOT NULL,
            schedule_id INTEGER NOT NULL,
            status TEXT DEFAULT 'confirmed',  -- confirmed/cancelled/completed
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(doctor_id) REFERENCES doctors(id),
            FOREIGN KEY(schedule_id) REFERENCES schedules(id)
        );
        """)
        # ====== 种子数据（仅在空库时插入） ======
        if conn.execute("SELECT COUNT(*) FROM departments").fetchone()[0] == 0:
            # 12 个常见科室
            depts = [("儿科","小儿内科/外科"),("内科","成人内科"),("外科","手术治疗"),
                     ("妇产科","妇女及产科"),("骨科","骨骼关节"),("眼科","眼部疾病"),
                     ("耳鼻喉科","耳鼻喉"),("皮肤科","皮肤病"),("消化内科","消化系统"),
                     ("口腔科","口腔牙齿"),("神经内科","神经系统"),("心血管内科","心脏血管")]
            conn.executemany("INSERT INTO departments(name,description) VALUES(?,?)", depts)
            # 12 位医生（每个科室至少一位）
            docs = [("张伟","儿科","主任医师","小儿呼吸/消化"),("李芳","儿科","副主任医师","儿童保健"),
                    ("王强","内科","主任医师","心血管"),("刘洋","外科","副主任医师","普外科"),
                    ("陈静","妇产科","主任医师","产科"),("赵明","骨科","主任医师","关节外科"),
                    ("孙丽","眼科","副主任医师","眼底病"),("周杰","耳鼻喉科","主任医师","耳科"),
                    ("吴敏","皮肤科","副主任医师","过敏"),("郑刚","消化内科","主任医师","胃肠"),
                    ("张建国","口腔科","主任医师","口腔颌面"),("钱华","神经内科","主任医师","脑血管")]
            conn.executemany("INSERT INTO doctors(name,department_id,title,description) "
                             "VALUES(?,(SELECT id FROM departments WHERE name=?),?,?)", docs)
            # 生成未来 7 天的排班（每天上午/下午各 20 个号）
            today = datetime.now().strftime("%Y-%m-%d")
            for doc_id in range(1, len(docs)+1):
                for offset in range(7):
                    d = (datetime.now() + timedelta(days=offset)).strftime("%Y-%m-%d")
                    for slot in [("上午",20),("下午",20)]:
                        conn.execute("INSERT OR IGNORE INTO schedules(doctor_id,date,time_slot,"
                                     "max_patients,current_patients) VALUES(?,?,?,?,?)",
                                     (doc_id, d, slot[0], slot[1], 0))
            # 测试用户（user_id=1）及其 3 个孩子
            conn.execute("INSERT INTO users(id,name,phone) VALUES(1,'张先生','13800000001')")
            conn.execute("INSERT INTO children(id,user_id,name,age,gender) VALUES"
                         "(1,1,'大宝',5,'男'),(2,1,'二宝',2,'女'),(3,1,'小宝',0,'男')")
            # 一条历史已完成挂号（用于"之前挂过XX专家"的测试）
            conn.execute("INSERT INTO appointments(user_id,child_id,doctor_id,schedule_id,"
                         "status,created_at) VALUES(1,1,11,1,'completed','2025-04-20')")
        conn.commit(); conn.close()

# 模块加载时自动初始化
init_db()
