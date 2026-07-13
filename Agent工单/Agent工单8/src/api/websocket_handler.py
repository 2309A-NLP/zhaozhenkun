"""
src/api/websocket_handler.py - WebSocket 信令与语音处理器
功能: 统一处理文本聊天、二进制音频上传、打断控制和基础信令消息。
说明: 主服务只负责挂载入口，本文件负责把浏览器消息送入数字人主处理链路。
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import json
import logging
import subprocess

import numpy as np

from fastapi import WebSocket
from fastapi import WebSocketDisconnect

logger = logging.getLogger(__name__)


class SignalingHandler:
    """统一的 WebSocket 处理器，支持文本消息和二进制音频消息。"""

    def __init__(self, session_manager, pipeline):
        self.sessions = session_manager
        self.pipeline = pipeline

    async def handle(self, ws: WebSocket, session_id: str) -> None:
        """处理单个连接的消息循环，支持 JSON 文本和二进制音频。"""
        session = self.sessions.get_session(session_id)
        if not session:
            await ws.accept()
            await ws.send_json({"type": "error", "message": "Session not found"})
            await ws.close()
            return

        await ws.accept()
        logger.info(f"WS connected: {session_id[:8]}")

        try:
            while True:
                raw = await ws.receive()
                if raw.get("type") == "websocket.disconnect":
                    break
                if raw.get("text") is not None:
                    await self._handle_text(ws, session, raw["text"])
                    continue
                if raw.get("bytes") is not None:
                    await self._handle_binary_audio(ws, session, raw["bytes"])
        except WebSocketDisconnect:
            logger.info(f"WS disconnected: {session_id[:8]}")
        except Exception as error:
            logger.error(f"WS error: {error}")
            try:
                await ws.send_json({"type": "error", "message": str(error)})
            except Exception:
                pass

    async def _handle_text(self, ws: WebSocket, session, raw_text: str) -> None:
        """处理 JSON 文本消息，兼容文本聊天、ping 和中断。"""
        try:
            message = json.loads(raw_text)
        except json.JSONDecodeError:
            return

        message_type = message.get("type", "")
        if message_type == "offer":
            # 当前仅保留实验性信令占位，避免前端等待无响应。
            await ws.send_json({"type": "answer", "sdp": "v=0"})
            return

        if message_type == "ice_candidate":
            # 目前未真正启用 WebRTC 协商，候选信息只做兼容接收。
            return

        if message_type == "chat_message":
            text = message.get("text", "")
            if text.strip():
                await self.pipeline.process_text(session, text)
            await ws.send_json(
                {
                    "type": "llm_response",
                    "text": self._get_last_reply(session),
                    "partial": False,
                }
            )
            return

        if message_type == "audio_input":
            # 前端会在发送二进制音频后补一个元信息通知，这里只做日志记录。
            fmt = message.get("format", "unknown")
            size = message.get("size", 0)
            logger.debug(f"收到音频输入通知: format={fmt}, size={size}")
            return

        if message_type == "ping":
            await ws.send_json({"type": "pong"})
            return

        if message_type == "interrupt":
            session.trigger_interrupt()
            await ws.send_json({"type": "interrupted"})

    async def _handle_binary_audio(self, ws: WebSocket, session, audio_bytes: bytes) -> None:
        """处理浏览器发送的 WebM/Opus 二进制音频，并驱动整轮语音对话。"""
        try:
            pcm_audio = self._decode_webm_to_pcm(audio_bytes)
            if pcm_audio is None or len(pcm_audio) == 0:
                await ws.send_json({"type": "audio_error", "message": "音频解码失败"})
                return

            result = await self.pipeline.process_turn_with_output(session, pcm_audio)
            await ws.send_json(
                {
                    "type": "llm_response",
                    "text": self._get_last_reply(session),
                    "partial": False,
                    "frames": len(result.get("video", [])),
                }
            )
        except Exception as error:
            logger.error(f"二进制音频处理失败: {error}")
            await ws.send_json({"type": "audio_error", "message": str(error)})

    def _decode_webm_to_pcm(self, webm_bytes: bytes) -> np.ndarray:
        """使用 FFmpeg 管道把 WebM/Opus 音频解码为 16kHz 单声道 PCM。"""
        command = [
            "ffmpeg",
            "-loglevel",
            "error",
            "-i",
            "pipe:0",
            "-f",
            "s16le",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            "pipe:1",
        ]
        try:
            completed = subprocess.run(
                command,
                input=webm_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=10,
            )
            pcm_bytes = completed.stdout
            if len(pcm_bytes) == 0:
                return np.array([], dtype=np.float32)
            samples = np.frombuffer(pcm_bytes, dtype=np.int16)
            return samples.astype(np.float32) / 32768.0
        except subprocess.TimeoutExpired:
            logger.error("WebM解码超时")
            return np.array([], dtype=np.float32)
        except subprocess.CalledProcessError as error:
            stderr_text = error.stderr.decode("utf-8", errors="ignore")
            logger.error(f"WebM解码失败: {stderr_text}")
            return np.array([], dtype=np.float32)

    def _get_last_reply(self, session) -> str:
        """从会话历史中提取最近一条助手回复文本。"""
        if not session.chat_history:
            return ""
        last_message = session.chat_history[-1]
        if last_message.get("role") == "assistant":
            return last_message.get("content", "")
        return ""
