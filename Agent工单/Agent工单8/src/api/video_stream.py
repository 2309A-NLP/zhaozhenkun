"""
src/api/video_stream.py - MJPEG 视频流端点
功能: 将数字人视频帧以 MJPEG 形式推送到浏览器，并在空闲时提供 idle 画面回退。
说明: 说话时优先输出会话缓存帧；空闲时回退到 idle_player 或黑色兜底帧。
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import asyncio
import logging

import cv2

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from src.core.idle_output import resolve_idle_frame

logger = logging.getLogger(__name__)

router = APIRouter(tags=["视频流"])

_sessions = None
_pipeline = None
_config = None


def init(sm, pipeline, cfg):
    """注入会话管理器、主处理管线和配置对象。"""
    global _sessions, _pipeline, _config
    _sessions = sm
    _pipeline = pipeline
    _config = cfg


@router.get("/session/{sid}/video_stream")
async def video_stream(sid: str):
    """持续输出 MJPEG 视频流，优先显示说话帧，空闲时显示 idle 帧。"""
    session = _sessions.get_session(sid)
    if not session:
        raise HTTPException(404, "会话不存在")

    async def generate_frames():
        last = None
        while True:
            try:
                frame = None
                if session.video_frame_buffer:
                    frame = session.video_frame_buffer[-1]
                if frame is None or frame.size == 0:
                    frame = resolve_idle_frame(
                        _pipeline,
                        _config.pipeline.video_height,
                        _config.pipeline.video_width,
                    )
                ok, jpg = cv2.imencode(".jpg", frame)
                if ok:
                    last = jpg.tobytes()
            except Exception as error:
                logger.warning(f"MJPEG 编码失败: {error}")

            if last is not None:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + last + b"\r\n"
            await asyncio.sleep(0.04)

    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache"},
    )
