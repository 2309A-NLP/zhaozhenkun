# -*- coding: utf-8 -*-
import uuid
import threading
from datetime import datetime
from typing import Dict, Optional

active_sessions = {}
sessions_lock = threading.RLock()


class SessionManager:
    """会话管理器"""

    @staticmethod
    def build_session(username: str) -> Dict:
        """构建新会话"""
        login_id = uuid.uuid4().hex  # 使用 .hex 获取字符串格式
        with sessions_lock:
            active_sessions[login_id] = {
                "login_id": login_id,
                "username": username,
                "session_id": f"{username}:{login_id}",
                "current_avatar": "doctor",
                "histories": {
                    "doctor": [],
                    "psychologist": [],
                    "marketer": []
                },  # 初始化所有角色的历史记录
                "created_at": datetime.now().isoformat()
            }
        return active_sessions[login_id]

    @staticmethod
    def get_session(login_id: str) -> Optional[Dict]:
        """根据login_id获取会话"""
        with sessions_lock:
            return active_sessions.get(login_id)

    @staticmethod
    def destroy_session(login_id: str):
        """销毁会话"""
        if login_id:
            with sessions_lock:
                active_sessions.pop(login_id, None)

    @staticmethod
    def get_user_session(login_id: str) -> Optional[Dict]:
        """获取用户会话（别名）"""
        return SessionManager.get_session(login_id)

    @staticmethod
    def update_session_history(login_id: str, avatar_id: str, messages: list):
        """更新会话历史"""
        with sessions_lock:
            if login_id in active_sessions:
                active_sessions[login_id]["histories"][avatar_id] = messages
                active_sessions[login_id]["current_avatar"] = avatar_id


# ========== Flask 路由使用的便捷函数 ==========
def get_session():
    """
    获取当前 Flask 会话对应的会话数据
    需要在 Flask 请求上下文中调用
    """
    try:
        from flask import session
        login_id = session.get("login_id")
        if login_id:
            return SessionManager.get_session(login_id)
        return None
    except (ImportError, RuntimeError):
        # 不在 Flask 上下文中时返回 None
        return None


def destroy_session(login_id):
    """销毁指定ID的会话"""
    SessionManager.destroy_session(login_id)


# 导出声明
__all__ = [
    'SessionManager',
    'get_session',
    'destroy_session',
    'active_sessions',
    'sessions_lock'
]