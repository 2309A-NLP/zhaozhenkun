"""
src/api/websocket_endpoint.py - WebSocket 路由挂载器
功能: 将实时语音/文本 WebSocket 入口独立出来，避免 server.py 继续膨胀。
说明: 复用 SignalingHandler 处理文本消息、二进制音频和中断控制。
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""

import logging

from fastapi import WebSocket

from src.api.websocket_handler import SignalingHandler

logger = logging.getLogger(__name__)

_sessions = None
_pipeline = None
_handler = None


def init(session_manager, pipeline) -> None:
    """注入会话管理器和主处理管线，并创建统一的信令处理器。"""
    global _sessions, _pipeline, _handler
    _sessions = session_manager
    _pipeline = pipeline
    _handler = SignalingHandler(session_manager, pipeline)


def register_websocket(app) -> None:
    """向 FastAPI 应用注册统一的 WebSocket 入口。"""

    @app.websocket("/ws/{sid}")
    async def ws_handler(ws: WebSocket, sid: str):
        """将连接直接交给统一处理器，支持文本与语音双模式。"""
        if _handler is None:
            # 依赖未注入时，直接返回明确错误，避免前端长时间挂起。
            await ws.accept()
            await ws.send_json({"type": "error", "message": "WebSocket handler not ready"})
            await ws.close()
            return

        try:
            await _handler.handle(ws, sid)
        finally:
            # WebSocket 断开后沿用原有行为释放会话，避免无效会话长期堆积。
            if _sessions is not None:
                _sessions.destroy_session(sid)
                logger.info(f"WS会话已释放: {sid[:8]}")
