"""工单19：数据库初始化与基础读写聚合模块。"""

# 工单19：导入数据库连接模块。
from development.db_connection import get_connection

# 工单19：导入数据库种子写入模块。
from development.db_seed import seed_database

# 工单19：导入数据库表结构初始化模块。
from development.db_schema import initialize_schema


# 工单19：初始化数据库表结构并写入演示数据。
def initialize_database(database_path=None):
    connection = get_connection(database_path)
    initialize_schema(connection)
    seed_database(connection)
    connection.close()


# 工单19：提供统一查询方法，便于服务层复用。
def fetch_all(query, params=None, database_path=None):
    connection = get_connection(database_path)
    rows = connection.execute(query, params or ()).fetchall()
    connection.close()
    return [dict(row) for row in rows]


# 工单19：提供统一单条查询方法。
def fetch_one(query, params=None, database_path=None):
    connection = get_connection(database_path)
    row = connection.execute(query, params or ()).fetchone()
    connection.close()
    return dict(row) if row else None


# 工单19：提供统一写入方法。
def execute_write(query, params=None, database_path=None):
    connection = get_connection(database_path)
    cursor = connection.execute(query, params or ())
    connection.commit()
    last_row_id = cursor.lastrowid
    connection.close()
    return last_row_id
