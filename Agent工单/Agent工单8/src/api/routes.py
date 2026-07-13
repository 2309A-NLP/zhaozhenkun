"""
src/api/routes.py - REST API 路由主入口
功能: 统一创建 APIRouter、注入共享依赖，并注册各子模块中的接口。
说明: 具体接口实现已拆分到多个 routes_* 文件，便于控制单文件长度。
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""

from fastapi import APIRouter

from src.api import route_state
from src.api.routes_runtime import register_routes as register_runtime_routes
from src.api.routes_session import register_routes as register_session_routes

router = APIRouter(prefix="/api/v1", tags=["数字人API"])
route_state.bind_router(router)


_def_registered = False


def _register_all_routes() -> None:
    """注册全部子模块路由，避免重复注册。"""

    global _def_registered
    if _def_registered:
        return
    register_session_routes()
    register_runtime_routes()
    _def_registered = True


_register_all_routes()


def init(session_manager, pipeline, config) -> None:
    """注入 SessionManager、Pipeline 和 Config 依赖。"""

    route_state.init_state(session_manager, pipeline, config)
