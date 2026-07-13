"""工单19：数据库连接与路径解析模块。"""

# 工单19：导入环境变量工具，支持测试与本地切换数据库文件。
import os

# 工单19：导入 SQLite 作为轻量数据库方案。
import sqlite3

# 工单19：导入路径工具，统一处理数据库文件位置。
from pathlib import Path

# 工单19：导入默认数据库配置。
from development.config import DEFAULT_DATABASE_PATH


# 工单19：解析数据库文件路径，优先读取显式参数，其次读取环境变量。
def resolve_database_path(database_path=None):
    target = database_path or os.getenv("APP_DATABASE_PATH", str(DEFAULT_DATABASE_PATH))
    return Path(target)


# 工单19：获取数据库连接，并启用字典式结果访问。
def get_connection(database_path=None):
    database_file = resolve_database_path(database_path)
    database_file.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_file)
    connection.row_factory = sqlite3.Row
    return connection
