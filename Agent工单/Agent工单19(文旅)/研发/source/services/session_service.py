# -*- coding: utf-8 -*-  # 指定源码编码。
# 工单编号：人工智能CV-AIGC-19-文旅Agent任务工单-创意策划与内容生成V1.1-20260306  # 标记工单来源。
"""session_service.py - 会话创建、消息记录与历史读取模块。"""  # 说明当前文件职责。

from datetime import datetime  # 导入时间工具。
from uuid import uuid4  # 导入随机会话编号工具。


_SESSIONS = {}  # 使用进程内字典保存会话。


def _ensure_session(session_id: str) -> dict:  # 确保指定会话存在。
    if session_id not in _SESSIONS:  # 当会话不存在时初始化。
        _SESSIONS[session_id] = {"messages": [], "created_at": datetime.now().isoformat()}  # 创建默认会话结构。
    return _SESSIONS[session_id]  # 返回可用会话对象。


def create_session() -> dict:  # 创建新的会话对象。
    session_id = f"session-{uuid4().hex[:12]}"  # 生成短会话编号。
    session = _ensure_session(session_id)  # 初始化会话容器。
    return {"session_id": session_id, "created_at": session["created_at"]}  # 返回会话元数据。


def append_message(session_id: str, role: str, content: str):  # 向会话中追加一条消息。
    if not session_id:  # 当未传会话编号时直接跳过。
        return  # 结束当前函数。
    session = _ensure_session(session_id)  # 获取目标会话。
    session["messages"].append(  # 追加消息记录。
        {  # 构造消息对象。
            "role": role,  # 记录消息角色。
            "content": content.strip(),  # 记录清洗后的消息正文。
            "created_at": datetime.now().isoformat(),  # 记录消息时间。
        }  # 单条消息对象结束。
    )  # 完成消息追加。


def get_recent_messages(session_id: str, limit: int = 8):  # 获取最近若干条会话消息。
    if not session_id or session_id not in _SESSIONS:  # 当会话不存在时返回空列表。
        return []  # 返回空消息集合。
    return _SESSIONS[session_id]["messages"][-limit:]  # 返回最近消息切片。


def get_session_snapshot(session_id: str) -> dict:  # 获取会话完整快照。
    if not session_id or session_id not in _SESSIONS:  # 当会话不存在时返回空结构。
        return {"session_id": session_id, "messages": []}  # 返回默认快照。
    return {  # 返回完整快照。
        "session_id": session_id,  # 返回会话编号。
        "created_at": _SESSIONS[session_id]["created_at"],  # 返回创建时间。
        "messages": list(_SESSIONS[session_id]["messages"]),  # 返回消息副本。
    }  # 快照构造结束。
