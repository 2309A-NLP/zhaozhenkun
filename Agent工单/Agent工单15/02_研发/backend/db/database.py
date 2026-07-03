"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理 V1.1
SQLite 数据库模块 —— 挂号管理系统（用户/孩子/科室/医生/排班/预约）
================================================================================
"""
import sqlite3, threading  # 导入 SQLite 数据库驱动和线程同步模块
from pathlib import Path  # 导入 Path 用于跨平台文件路径处理
from datetime import datetime, timedelta  # 导入日期时间处理和时间差计算

# 数据库文件路径（项目根目录 data/hospital.db —— SQLite 单文件数据库）
DB_PATH = Path(__file__).resolve().parent.parent.parent.parent / "data" / "hospital.db"  # 构建数据库文件绝对路径
DB_PATH.parent.mkdir(parents=True, exist_ok=True)  # 确保 data 目录存在（递归创建，已存在则跳过）

# 写锁：SQLite 单写多读，写操作串行化防止 "database is locked" 错误
_lock = threading.Lock()  # 创建线程互斥锁，确保同一时间只有一个线程执行写操作

def get_conn():  # 获取数据库连接函数
    """获取数据库连接（WAL 模式 + 外键约束）"""
    conn = sqlite3.connect(str(DB_PATH))  # 创建与 SQLite 数据库文件的连接
    conn.row_factory = sqlite3.Row          # 设置行工厂：查询结果可通过字典式列名访问（如 row['name']）
    conn.execute("PRAGMA journal_mode=WAL") # 启用 WAL（Write-Ahead Logging）模式，支持并发读写
    conn.execute("PRAGMA foreign_keys=ON") # 启用外键约束检查（确保数据参照完整性）
    return conn  # 返回配置好的数据库连接对象

from contextlib import contextmanager  # 导入上下文管理器装饰器（用于创建 with 语句）

@contextmanager  # 将 get_db 函数装饰为上下文管理器（支持 with 语句）
def get_db():  # 数据库连接上下文管理器函数
    """
    数据库连接上下文管理器 —— 自动关闭连接，防止泄漏

    用法:
        with get_db() as conn:
            rows = conn.execute("SELECT ...").fetchall()

    """
    conn = get_conn()  # 获取一个新的数据库连接
    try:  # 尝试执行 with 块中的代码
        yield conn  # 将数据库连接交给 with 语句的 as 变量
        conn.commit()  # 正常执行完成后提交事务
    except Exception:  # 如果 with 块中发生任何异常
        conn.rollback()  # 回滚事务（撤销所有未提交的修改）
        raise  # 重新抛出异常（不吞没错误）
    finally:  # 无论成功还是异常都执行
        conn.close()  # 关闭数据库连接（防止连接泄漏）

def init_db():  # 数据库初始化函数
    """初始化数据库：建表 + 插入种子数据（仅在首次调用时执行）"""
    with _lock:                              # 获取写锁，串行化初始化操作
        conn = get_conn()  # 创建数据库连接
        try:  # 尝试执行建表和种子数据插入
            # ====== 建表 ======
            conn.executescript("""
            -- 用户表（存储挂号患者的基本信息）
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            -- 孩子表（一个用户可以登记多个孩子）
            CREATE TABLE IF NOT EXISTS children (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                age INTEGER,
                gender TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
            -- 科室表（医院的临床科室分类）
            CREATE TABLE IF NOT EXISTS departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT
            );
            -- 医生表（医生的基本信息和所属科室）
            CREATE TABLE IF NOT EXISTS doctors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                department_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                FOREIGN KEY(department_id) REFERENCES departments(id)
            );
            -- 排班表（每个医生每天的出诊号源分配情况）
            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doctor_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                time_slot TEXT NOT NULL,
                max_patients INTEGER DEFAULT 20,
                current_patients INTEGER DEFAULT 0,
                FOREIGN KEY(doctor_id) REFERENCES doctors(id),
                UNIQUE(doctor_id, date, time_slot)
            );
            -- 预约表（患者的挂号预约记录）
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                child_id INTEGER,
                doctor_id INTEGER NOT NULL,
                schedule_id INTEGER NOT NULL,
                status TEXT DEFAULT 'confirmed',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY(user_id) REFERENCES users(id),
                FOREIGN KEY(doctor_id) REFERENCES doctors(id),
                FOREIGN KEY(schedule_id) REFERENCES schedules(id)
            );
            """)
            # ====== 种子数据（仅在空库时插入，即 departments 表中无数据时） ======
            if conn.execute("SELECT COUNT(*) FROM departments").fetchone()[0] == 0:  # 检查科室表是否为空
                # 12 个常见医院科室（用于挂号功能的演示数据）
                depts = [("儿科","小儿内科/外科"),("内科","成人内科"),("外科","手术治疗"),  # 儿科、内科、外科
                         ("妇产科","妇女及产科"),("骨科","骨骼关节"),("眼科","眼部疾病"),  # 妇产科、骨科、眼科
                         ("耳鼻喉科","耳鼻喉"),("皮肤科","皮肤病"),("消化内科","消化系统"),  # 耳鼻喉科、皮肤科、消化内科
                         ("口腔科","口腔牙齿"),("神经内科","神经系统"),("心血管内科","心脏血管")]  # 口腔科、神经内科、心血管内科
                conn.executemany("INSERT INTO departments(name,description) VALUES(?,?)", depts)  # 批量插入科室记录
                # 12 位医生（每个科室至少配一位医生，用于演示挂号选择）
                docs = [("张伟","儿科","主任医师","小儿呼吸/消化"),("李芳","儿科","副主任医师","儿童保健"),  # 儿科医生
                        ("王强","内科","主任医师","心血管"),("刘洋","外科","副主任医师","普外科"),  # 内科、外科医生
                        ("陈静","妇产科","主任医师","产科"),("赵明","骨科","主任医师","关节外科"),  # 妇产科、骨科医生
                        ("孙丽","眼科","副主任医师","眼底病"),("周杰","耳鼻喉科","主任医师","耳科"),  # 眼科、耳鼻喉科医生
                        ("吴敏","皮肤科","副主任医师","过敏"),("郑刚","消化内科","主任医师","胃肠"),  # 皮肤科、消化内科医生
                        ("张建国","口腔科","主任医师","口腔颌面"),("钱华","神经内科","主任医师","脑血管")]  # 口腔科、神经内科医生
                conn.executemany("INSERT INTO doctors(name,department_id,title,description) "  # 批量插入医生记录
                                 "VALUES(?,(SELECT id FROM departments WHERE name=?),?,?)", docs)  # 通过科室名称查询对应 ID
                # 生成未来 7 天的排班（每天上午/下午各 20 个号源）
                today = datetime.now().strftime("%Y-%m-%d")  # 获取今天的日期字符串
                for doc_id in range(1, len(docs)+1):  # 遍历每位医生（ID 从 1 开始）
                    for offset in range(7):  # 从今天开始未来 7 天
                        d = (datetime.now() + timedelta(days=offset)).strftime("%Y-%m-%d")  # 计算第 offset 天的日期
                        for slot in [("上午",20),("下午",20)]:  # 每天两个时段各 20 个号
                            conn.execute("INSERT OR IGNORE INTO schedules(doctor_id,date,time_slot,"  # 插入排班记录（忽略已存在的）
                                         "max_patients,current_patients) VALUES(?,?,?,?,?)",
                                         (doc_id, d, slot[0], slot[1], 0))  # 参数：医生ID、日期、时段、号数、已挂号数（初始为0）
                # 测试用户（user_id=1）及其 3 个孩子（用于演示和测试挂号流程）
                conn.execute("INSERT INTO users(id,name,phone) VALUES(1,'张先生','13800000001')")  # 插入测试用户
                conn.execute("INSERT INTO children(id,user_id,name,age,gender) VALUES"  # 批量插入测试用户的三个孩子
                             "(1,1,'大宝',5,'男'),(2,1,'二宝',2,'女'),(3,1,'小宝',0,'男')")  # 三孩子的姓名年龄性别
                # 一条历史已完成挂号记录（用于测试"之前挂过XX专家的号"的功能场景）
                conn.execute("INSERT INTO appointments(user_id,child_id,doctor_id,schedule_id,"  # 插入历史预约记录
                             "status,created_at) VALUES(1,1,11,1,'completed','2025-04-20')")  # 用户1为孩子1预约医生11，状态已完成
            # 每次启动都补上未来7天的排班（INSERT OR IGNORE 避免插入已有记录的重复数据）
            today = datetime.now().strftime("%Y-%m-%d")  # 获取今天的日期字符串
            doctor_count = conn.execute("SELECT COUNT(*) FROM doctors").fetchone()[0]  # 查询医生总人数
            for doc_id in range(1, doctor_count + 1):  # 遍历每位医生
                for offset in range(7):  # 从今天开始未来 7 天
                    d = (datetime.now() + timedelta(days=offset)).strftime("%Y-%m-%d")  # 计算第 offset 天的日期
                    for slot in [("上午", 20), ("下午", 20)]:  # 每天上午和下午两个时段
                        conn.execute("INSERT OR IGNORE INTO schedules(doctor_id,date,time_slot,"  # 插入排班记录
                                     "max_patients,current_patients) VALUES(?,?,?,?,?)",  
                                     (doc_id, d, slot[0], slot[1], 0))  # 参数绑定：医生ID、日期、时段、号源数、已挂号数
            conn.commit()  # 提交所有建表和种子数据事务
        except Exception:  # 捕获初始化过程中的任何异常
            conn.rollback()  # 回滚事务（撤销所有已执行但未提交的修改）
            raise  # 重新抛出异常（让上层调用者知晓初始化失败）
        finally:  # 无论成功或失败都执行
            conn.close()  # 关闭数据库连接释放资源

# 模块加载时自动初始化数据库（建表 + 种子数据 + 补排班）
init_db()  # 调用数据库初始化函数（每次导入时都补上未来7天排班）
