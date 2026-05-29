# -*- coding: utf-8 -*-
"""
ADSD 在线服务 - 会话管理器模块
负责管理用户会话的生命周期，包括创建、获取、更新和销毁会话
主要功能：
1. 构建新会话：为用户创建唯一会话ID并初始化会话数据
2. 获取会话：根据login_id查找活跃会话
3. 更新会话历史：保存对话历史和当前使用的角色信息
4. 销毁会话：清除指定会话
5. Flask路由兼容：提供便捷函数供Flask路由调用
"""
import uuid  # 导入uuid模块，用于生成全局唯一的会话ID
import threading  # 导入线程模块，用于实现线程安全的会话操作
from datetime import datetime  # 导入datetime模块，用于记录会话创建时间
from typing import Dict, Optional  # 导入类型提示，用于函数参数和返回值的类型注解

active_sessions = {}  # 全局活跃会话字典，存储所有当前在线的会话
sessions_lock = threading.RLock()  # 全局会话锁（可重入锁），保证多线程环境下的会话数据安全


class SessionManager:
    """会话管理器"""  # 类的文档字符串

    @staticmethod  # 声明为静态方法，无需实例化即可调用
    def build_session(username: str) -> Dict:
        """构建新会话"""  # 方法文档
        login_id = uuid.uuid4().hex  # 使用 .hex 获取字符串格式（32位十六进制字符串）
        with sessions_lock:  # 获取线程锁，保证操作原子性
            active_sessions[login_id] = {  # 在全局字典中创建新会话
                "login_id": login_id,  # 登录ID，会话的唯一标识
                "username": username,  # 用户名
                "session_id": f"{username}:{login_id}",  # 组合会话ID（用户名:登录ID）
                "current_avatar": "doctor",  # 当前使用的角色，默认为"doctor"
                "histories": {  # 各角色的对话历史记录
                    "doctor": [],  # 医生角色的历史记录
                    "psychologist": [],  # 心理师角色的历史记录
                    "marketer": []  # 营销员角色的历史记录
                },  # 初始化所有角色的历史记录
                "created_at": datetime.now().isoformat()  # 会话创建时间（ISO格式字符串）
            }
        return active_sessions[login_id]  # 返回新创建的会话数据

    @staticmethod  # 声明为静态方法
    def get_session(login_id: str) -> Optional[Dict]:
        """根据login_id获取会话"""  # 方法文档
        with sessions_lock:  # 获取线程锁
            return active_sessions.get(login_id)  # 从全局字典中获取会话，不存在则返回None

    @staticmethod  # 声明为静态方法
    def destroy_session(login_id: str):
        """销毁会话"""  # 方法文档
        if login_id:  # 如果login_id不为空
            with sessions_lock:  # 获取线程锁
                active_sessions.pop(login_id, None)  # 从全局字典中移除指定会话（不存在时不报错）

    @staticmethod  # 声明为静态方法
    def get_user_session(login_id: str) -> Optional[Dict]:
        """获取用户会话（别名）"""  # 方法文档
        return SessionManager.get_session(login_id)  # 调用get_session方法，作为别名使用

    @staticmethod  # 声明为静态方法
    def update_session_history(login_id: str, avatar_id: str, messages: list):
        """更新会话历史"""  # 方法文档
        with sessions_lock:  # 获取线程锁
            if login_id in active_sessions:  # 检查会话是否存在
                active_sessions[login_id]["histories"][avatar_id] = messages  # 更新指定角色的历史记录
                active_sessions[login_id]["current_avatar"] = avatar_id  # 更新当前使用的角色


# ========== Flask 路由使用的便捷函数 ==========
def get_session():
    """
    获取当前 Flask 会话对应的会话数据
    需要在 Flask 请求上下文中调用
    """
    try:  # 尝试获取Flask中的会话
        from flask import session  # 导入Flask的session对象
        login_id = session.get("login_id")  # 从Flask会话中获取login_id
        if login_id:  # 如果login_id存在
            return SessionManager.get_session(login_id)  # 返回对应的会话数据
        return None  # login_id不存在则返回None
    except (ImportError, RuntimeError):  # 捕获导入错误或运行时错误
        # 不在 Flask 上下文中时返回 None
        return None  # 不在Flask上下文中时返回None


def destroy_session(login_id):
    """销毁指定ID的会话"""  # 函数文档
    SessionManager.destroy_session(login_id)  # 委托SessionManager执行销毁操作


# 导出声明
__all__ = [  # 定义模块的公开接口，仅在导入*时可见
    'SessionManager',  # 会话管理器类
    'get_session',  # 获取当前会话的便捷函数
    'destroy_session',  # 销毁会话的便捷函数
    'active_sessions',  # 全局活跃会话字典
    'sessions_lock'  # 全局会话锁
]
