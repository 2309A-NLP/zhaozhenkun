"""工单18：会话管理服务，负责创建会话、保存历史消息和读取上下文。"""
# 工单18：导入时间模块，便于记录会话创建时间。
from datetime import datetime
# 工单18：导入UUID生成器，为每个游客分配唯一会话编号。
from uuid import uuid4

# 工单18：使用内存字典保存会话，适合当前工单演示版本。
SESSION_STORE = {}

# 工单18：创建新会话并返回基础信息。
def create_session() -> dict:
    # 工单18：生成唯一会话ID，避免不同游客的对话串线。
    session_id = str(uuid4())
    # 工单18：初始化会话结构，包含创建时间和消息列表。
    SESSION_STORE[session_id] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "messages": [],
    }
    # 工单18：返回创建结果给前端。
    return {"session_id": session_id, **SESSION_STORE[session_id]}

# 工单18：向指定会话追加一条消息，便于保留上下文。
def append_message(session_id: str, role: str, content: str) -> None:
    # 工单18：如果会话不存在，就先自动创建一个兜底结构。
    SESSION_STORE.setdefault(session_id, {"created_at": datetime.now().isoformat(timespec="seconds"), "messages": []})
    # 工单18：把当前消息按角色写入会话历史。
    SESSION_STORE[session_id]["messages"].append({"role": role, "content": content})

# 工单18：读取会话最近若干轮对话，避免提示词无限增长。
def get_recent_messages(session_id: str, limit: int = 6) -> list:
    # 工单18：如果会话不存在，直接返回空列表。
    if session_id not in SESSION_STORE:
        return []
    # 工单18：只截取最近limit条消息，提高生成速度。
    return SESSION_STORE[session_id]["messages"][-limit:]
