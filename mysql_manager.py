# -*- coding: utf-8 -*-
import json  # 导入JSON模块，用于处理JSON格式的数据（如存储复杂的行为详情）
import logging  # 导入日志模块，用于记录调试和错误信息
from typing import Dict, Optional  # 导入类型提示，用于函数参数和返回值的类型注解

try:
    import pymysql  # 尝试导入PyMySQL库，用于连接MySQL数据库
    from pymysql.cursors import DictCursor  # 导入字典游标，让查询结果返回字典格式

    MYSQL_AVAILABLE = True  # 标记MySQL库可用
except ImportError:  # 捕获导入失败异常（pymysql未安装）
    pymysql = None  # 将pymysql设为None
    MYSQL_AVAILABLE = False  # 标记MySQL库不可用

logger = logging.getLogger(__name__)  # 创建当前模块的日志记录器


class MySQLManager:
    """MySQL 数据库管理器"""  # 类的文档字符串，说明该类用于管理MySQL数据库操作

    def __init__(self, config: dict):
        """初始化MySQL管理器，接收数据库配置"""  # 构造函数文档
        self.config = config  # 保存数据库配置字典，包含host、port、user、password等
        self.connection = None  # 数据库连接对象，初始为None
        self.enabled = MYSQL_AVAILABLE and config.get("enabled", False)  # 是否启用MySQL（需要库可用且配置启用）
        if self.enabled:  # 如果启用MySQL
            self._connect()  # 尝试连接数据库
            if self.connection:  # 如果连接成功
                self._init_tables()  # 初始化数据表

    def _ensure_connection(self) -> bool:
        """确保数据库连接有效，如果断开则重连"""  # 私有方法文档
        if not self.enabled:  # 如果未启用MySQL
            return False  # 返回False
        try:
            if self.connection:  # 如果已有连接对象
                self.connection.ping(reconnect=True)  # 发送ping检查连接，自动重连
                return True  # 连接有效，返回True
            else:  # 没有连接对象
                self._connect()  # 调用_connect方法建立连接
                return self.connection is not None  # 返回是否连接成功
        except Exception as e:  # 捕获检查过程中的异常
            logger.debug(f"MySQL 连接检查失败: {e}")  # 记录调试日志
            self._connect()  # 尝试重新连接
            return self.connection is not None  # 返回是否连接成功

    def _connect(self):
        """建立MySQL数据库连接"""  # 私有连接方法文档
        if not MYSQL_AVAILABLE:  # 如果pymysql库不可用
            self.enabled = False  # 禁用MySQL功能
            return  # 提前返回

        try:
            self.connection = pymysql.connect(  # 创建数据库连接
                host=self.config["host"],  # 数据库主机地址
                port=self.config["port"],  # 数据库端口
                user=self.config["user"],  # 数据库用户名
                password=self.config["password"],  # 数据库密码
                database=self.config["database"],  # 数据库名称
                charset='utf8mb4',  # 字符集，支持emoji等四字节字符
                cursorclass=DictCursor,  # 使用字典游标，返回字典格式的结果
                autocommit=False,  # 关闭自动提交，手动控制事务
                connect_timeout=5  # 连接超时时间（秒）
            )
            print(f"[OK] MySQL 连接成功: {self.config['host']}:{self.config['port']}/{self.config['database']}")  # 打印成功信息
        except Exception as e:  # 捕获连接异常
            print(f"[WARN] MySQL 连接失败: {e}")  # 打印失败信息
            self.enabled = False  # 禁用MySQL功能
            self.connection = None  # 清空连接对象

    def _init_tables(self):
        """初始化数据库表结构"""  # 私有初始化方法文档
        if not self.connection:  # 如果没有有效的数据库连接
            return  # 直接返回

        try:
            cursor = self.connection.cursor()  # 创建游标对象
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self.config['database']}")  # 创建数据库（如果不存在）
            cursor.execute(f"USE {self.config['database']}")  # 切换到指定数据库

            # 聊天历史表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,  # 自增主键ID
                    session_id VARCHAR(128) NOT NULL,  # 会话ID，不为空
                    username VARCHAR(64) NOT NULL,  # 用户名，不为空
                    avatar_id VARCHAR(32) NOT NULL,  # 角色ID（如doctor、nurse等），不为空
                    role VARCHAR(16) NOT NULL,  # 消息角色（user/assistant/system），不为空
                    content TEXT NOT NULL,  # 消息内容（文本）
                    tokens_used INT DEFAULT 0,  # 使用的token数量，默认为0
                    response_time_ms INT DEFAULT 0,  # 响应时间（毫秒），默认为0
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  # 创建时间，默认当前时间戳
                    INDEX idx_session (session_id),  # 会话ID索引，用于快速查询
                    INDEX idx_user (username),  # 用户名索引
                    INDEX idx_created (created_at)  # 创建时间索引
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4  # InnoDB引擎，支持事务；utf8mb4字符集
            """)

            # 用户行为日志表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_actions (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,  # 自增主键ID
                    username VARCHAR(64) NOT NULL,  # 用户名，不为空
                    action_type VARCHAR(32) NOT NULL,  # 行为类型（如登录、提问、反馈等）
                    action_detail JSON,  # 行为详情（JSON格式，存储灵活的结构化数据）
                    ip_address VARCHAR(45),  # IP地址（支持IPv6，最长45字符）
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  # 创建时间，默认当前时间戳
                    INDEX idx_user (username),  # 用户名索引
                    INDEX idx_action (action_type),  # 行为类型索引
                    INDEX idx_created (created_at)  # 创建时间索引
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4  # InnoDB引擎，utf8mb4字符集
            """)

            # 会话记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,  # 自增主键ID
                    session_id VARCHAR(128) UNIQUE NOT NULL,  # 会话ID（唯一），不为空
                    username VARCHAR(64) NOT NULL,  # 用户名，不为空
                    avatar_id VARCHAR(32) DEFAULT 'doctor',  # 当前使用的角色ID，默认为'doctor'
                    message_count INT DEFAULT 0,  # 消息总数，默认为0
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  # 创建时间
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,  # 更新时间，自动更新
                    INDEX idx_session (session_id),  # 会话ID索引
                    INDEX idx_user (username)  # 用户名索引
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4  # InnoDB引擎，utf8mb4字符集
            """)

            self.connection.commit()  # 提交事务，使表创建生效
            cursor.close()  # 关闭游标
            print("[OK] MySQL 数据表初始化完成")  # 打印成功信息
        except Exception as e:  # 捕获表创建异常
            print(f"[WARN] MySQL 表初始化失败: {e}")  # 打印失败信息
            self.enabled = False  # 禁用MySQL功能

    def save_chat_message(self, session_id: str, username: str, avatar_id: str,
                          role: str, content: str, response_time_ms: int = 0) -> bool:
        """保存聊天消息到数据库，返回是否保存成功"""  # 保存聊天消息方法文档
        if not self._ensure_connection():  # 确保数据库连接有效
            return False  # 连接失败，返回False
        try:
            cursor = self.connection.cursor()  # 创建游标
            cursor.execute("""
                INSERT INTO chat_history (session_id, username, avatar_id, role, content, response_time_ms)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (session_id, username, avatar_id, role, content, response_time_ms))  # 执行插入，使用参数化查询防止SQL注入
            self.connection.commit()  # 提交事务
            cursor.close()  # 关闭游标
            return True  # 保存成功
        except Exception as e:  # 捕获保存异常
            logger.debug(f"保存聊天记录失败: {e}")  # 记录调试日志
            return False  # 返回False

    def log_user_action(self, username: str, action_type: str,
                        action_detail: Dict = None, ip: str = None) -> bool:
        """记录用户行为日志，返回是否记录成功"""  # 用户行为日志方法文档
        if not self._ensure_connection():  # 确保数据库连接有效
            return False  # 连接失败，返回False
        try:
            cursor = self.connection.cursor()  # 创建游标
            cursor.execute("""
                INSERT INTO user_actions (username, action_type, action_detail, ip_address)
                VALUES (%s, %s, %s, %s)
            """, (username, action_type, json.dumps(action_detail) if action_detail else None, ip))  # 将字典转为JSON字符串存储
            self.connection.commit()  # 提交事务
            cursor.close()  # 关闭游标
            return True  # 记录成功
        except Exception as e:  # 捕获记录异常
            logger.debug(f"记录用户行为失败: {e}")  # 记录调试日志
            return False  # 返回False

    def update_session(self, session_id: str, username: str, avatar_id: str) -> bool:
        """更新会话信息（如果会话不存在则创建），返回是否更新成功"""  # 更新会话方法文档
        if not self._ensure_connection():  # 确保数据库连接有效
            return False  # 连接失败，返回False
        try:
            cursor = self.connection.cursor()  # 创建游标
            cursor.execute("""
                INSERT INTO sessions (session_id, username, avatar_id, message_count)
                VALUES (%s, %s, %s, 1)
                ON DUPLICATE KEY UPDATE   # 如果主键或唯一索引冲突则执行更新
                    updated_at = CURRENT_TIMESTAMP,  # 更新时间为当前时间
                    message_count = message_count + 1  # 消息计数加1
            """, (session_id, username, avatar_id))  # 执行插入或更新
            self.connection.commit()  # 提交事务
            cursor.close()  # 关闭游标
            return True  # 更新成功
        except Exception as e:  # 捕获更新异常
            logger.debug(f"更新会话失败: {e}")  # 记录调试日志
            return False  # 返回False

    def close(self):
        """关闭数据库连接"""  # 关闭连接方法文档
        if self.connection:  # 如果连接存在
            self.connection.close()  # 关闭连接
            print("[OK] MySQL 连接已关闭")  # 打印关闭信息
