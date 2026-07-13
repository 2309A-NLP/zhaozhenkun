"""
src/api/routes_session.py - 会话与对话路由
功能: 注册会话创建、状态查询、文本对话、打断、音频获取等接口。
说明: 将高频基础路由拆出，减少主 routes.py 长度并提升可维护性。
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""

import traceback

from fastapi import HTTPException
from fastapi.responses import Response

from src.api import route_state
from src.api.schemas import (
    InterruptResponse,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionStatusResponse,
    TextInputRequest,
    TextInputResponse,
)
from src.utils.audio_utils import float32_to_wav_bytes


def register_routes() -> None:
    """注册会话与文本对话相关路由。"""

    router = route_state.router

    @router.post("/session/create", response_model=SessionCreateResponse)
    async def create_session(req: SessionCreateRequest):
        """创建新数字人会话，返回会话 ID 与 WebSocket 地址。"""
        del req
        route_state.ensure_ready()
        try:
            session = route_state.sessions.create_session()
            ws_url = (
                f"ws://{route_state.config.server.host}:"
                f"{route_state.config.server.port}/ws/{session.session_id}"
            )
            return SessionCreateResponse(session_id=session.session_id, ws_url=ws_url)
        except RuntimeError as error:
            raise HTTPException(503, str(error)) from error

    @router.delete("/session/{sid}")
    async def destroy_session(sid: str):
        """销毁会话并释放资源。"""
        route_state.ensure_ready()
        if not route_state.sessions.destroy_session(sid):
            raise HTTPException(404, "会话不存在")
        return {"status": "destroyed", "session_id": sid}

    @router.get("/session/{sid}/status", response_model=SessionStatusResponse)
    async def get_status(sid: str):
        """查询会话状态和累计轮次。"""
        session = route_state.require_session(sid)
        return SessionStatusResponse(
            session_id=sid,
            state=session.state.value,
            total_turns=session.total_turns,
        )

    @router.post("/session/{sid}/text", response_model=TextInputResponse)
    async def send_text(sid: str, req: TextInputRequest):
        """发送文本输入并返回数字人最新回复。"""
        session = route_state.require_session(sid)
        try:
            await route_state.pipeline.process_text(session, req.text)
            reply = route_state.get_assistant_reply(session)
            if not reply:
                reply = "(AI未返回内容)"
            return TextInputResponse(status="completed", response_text=reply)
        except Exception as error:
            detail = traceback.format_exc()
            route_state.ensure_ready()
            route_state.pipeline.config  # 仅用于确保上下文仍可访问
            import logging

            logging.getLogger(__name__).error(f"文本处理失败:\n{detail}")
            raise HTTPException(500, str(error)) from error

    @router.post("/session/{sid}/interrupt", response_model=InterruptResponse)
    async def interrupt(sid: str):
        """强制中断数字人当前说话状态。"""
        session = route_state.require_session(sid)
        session.trigger_interrupt()
        return InterruptResponse(status="interrupted")

    @router.get("/session/{sid}/audio")
    async def get_audio(sid: str):
        """获取会话最近一次 TTS 生成的 WAV 音频。"""
        session = route_state.require_session(sid)
        audio = getattr(session, "last_tts_audio", None)
        if audio is None or len(audio) == 0:
            raise HTTPException(404, "暂无音频")
        wav = float32_to_wav_bytes(audio)
        return Response(
            content=wav,
            media_type="audio/wav",
            headers={"Content-Disposition": "inline"},
        )