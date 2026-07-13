"""
src/api/route_state.py - API 路由共享状态
功能: 管理 routes 模块依赖注入后的共享对象，供各路由子模块统一访问。
说明: 通过单独状态文件避免 routes.py 过长，同时保持原有初始化方式兼容。
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""

from fastapi import HTTPException

from src.api import schemas

sessions = None
pipeline = None
config = None
router = None


def bind_router(target_router) -> None:
    """绑定主 APIRouter，供子模块注册接口。"""

    global router
    router = target_router


def init_state(session_manager, pipeline_obj, config_obj) -> None:
    """保存依赖注入对象，供所有路由处理函数访问。"""

    global sessions, pipeline, config
    sessions = session_manager
    pipeline = pipeline_obj
    config = config_obj


def ensure_ready() -> None:
    """确保依赖已初始化，未初始化时抛出明确异常。"""

    if sessions is None or pipeline is None or config is None or router is None:
        raise RuntimeError("API 路由依赖未初始化，请先调用 init()")


def get_assistant_reply(session) -> str:
    """从会话历史中提取最近一条 assistant 回复文本。"""

    if not session or not getattr(session, "chat_history", None):
        return ""
    message = session.chat_history[-1]
    if message.get("role") == "assistant":
        return message.get("content", "")
    return ""


def require_session(session_id: str):
    """按会话 ID 获取会话，不存在时抛出 404。"""

    ensure_ready()
    session = sessions.get_session(session_id)
    if not session:
        raise HTTPException(404, "会话不存在")
    return session