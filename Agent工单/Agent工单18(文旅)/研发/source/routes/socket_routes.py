"""工单18：WebSocket 实时通信路由 — 处理摄像头帧、语音流、行为事件推送。"""
import base64
import json
from flask import current_app
from flask_socketio import SocketIO, emit, disconnect

from services.session_service import append_message, get_recent_messages
from services.guide_service import handle_text_chat, handle_image_chat, handle_behavior_chat
from services.audio_service import transcribe_audio, synthesize_speech
from services.realtime_vision_service import detect_behavior
from services.realtime_route_service import handle_realtime_behavior
from services.yolo_behavior_service import get_detector as get_yolo_detector
from services.common_service import guess_mime_type, validate_image_bytes

# 工单18：在线用户追踪
online_users = {}

def register_socket_events(sio: SocketIO, app):
    @sio.on("connect")
    def on_connect():
        online_users[id] = True
        emit("connected", {"status": "ok", "message": "WebSocket 已连接"})

    @sio.on("disconnect")
    def on_disconnect():
        online_users.pop(id, None)

    # 工单18：实时文本对话
    @sio.on("chat:text")
    def on_chat_text(data):
        session_id = data.get("session_id", "")
        question = (data.get("question", "") or "").strip()
        language = data.get("language", "zh")
        if not question:
            emit("chat:error", {"error": "问题不能为空"})
            return
        append_message(session_id, "user", question)
        result = handle_text_chat(current_app.config, question, language, get_recent_messages(session_id))
        append_message(session_id, "assistant", result["answer"])
        emit("chat:response", {
            "type": "text",
            "answer": result["answer"],
            "subtitle": result.get("subtitle", ""),
            "references": result.get("references", []),
            "audio_base64": result.get("audio_base64"),
            "audio_mime": result.get("audio_mime"),
            "lip_sync": result.get("lip_sync"),
            "duration": result.get("duration"),
            "route_tip": result.get("route_tip"),
        })

    # 工单18：实时语音流处理
    @sio.on("chat:audio")
    def on_chat_audio(data):
        session_id = data.get("session_id", "")
        language = data.get("language", "zh")
        audio_b64 = data.get("audio", "")
        if not audio_b64:
            emit("chat:error", {"error": "未收到语音数据"})
            return
        try:
            audio_bytes = base64.b64decode(audio_b64)
        except Exception:
            emit("chat:error", {"error": "语音数据解码失败"})
            return
        transcript = transcribe_audio(audio_bytes, ".webm" if data.get("format") == "webm" else ".wav")
        emit("chat:transcript", {"transcript": transcript})
        if not transcript or transcript.startswith("语音已接收"):
            return
        append_message(session_id, "user", transcript)
        result = handle_text_chat(current_app.config, transcript, language, get_recent_messages(session_id))
        append_message(session_id, "assistant", result["answer"])
        emit("chat:response", {
            "type": "audio_reply",
            "answer": result["answer"],
            "subtitle": result.get("subtitle", ""),
            "references": result.get("references", []),
            "audio_base64": result.get("audio_base64"),
            "audio_mime": result.get("audio_mime"),
            "lip_sync": result.get("lip_sync"),
            "duration": result.get("duration"),
            "route_tip": result.get("route_tip"),
        })

    # 工单18：实时图片分析
    @sio.on("chat:image")
    def on_chat_image(data):
        session_id = data.get("session_id", "")
        question = data.get("question", "请讲解这张图片")
        language = data.get("language", "zh")
        image_b64 = data.get("image", "")
        if not image_b64:
            emit("chat:error", {"error": "未收到图片数据"})
            return
        try:
            image_bytes = base64.b64decode(image_b64)
        except Exception:
            emit("chat:error", {"error": "图片数据解码失败"})
            return
        err = validate_image_bytes(image_bytes)
        if err:
            emit("chat:error", {"error": err})
            return
        append_message(session_id, "user", question)
        result = handle_image_chat(current_app.config, question, language, get_recent_messages(session_id), image_bytes)
        append_message(session_id, "assistant", result["answer"])
        emit("chat:response", {
            "type": "image_reply",
            "answer": result["answer"],
            "subtitle": result.get("subtitle", ""),
            "references": result.get("references", []),
            "image_summary": result.get("image_summary", ""),
            "ocr_text": result.get("ocr_text", ""),
            "audio_base64": result.get("audio_base64"),
            "audio_mime": result.get("audio_mime"),
            "lip_sync": result.get("lip_sync"),
            "duration": result.get("duration"),
            "route_tip": result.get("route_tip"),
        })

    # 工单18：实时摄像头行为识别
    @sio.on("realtime:frame")
    def on_realtime_frame(data):
        session_id = data.get("session_id", "")
        language = data.get("language", "zh")
        payload = data.get("payload", {})
        result = handle_realtime_behavior(current_app.config, payload, language, get_recent_messages(session_id))
        if result.get("detected"):
            append_message(session_id, "user", f"实时识别动作：{result['behavior']}")
            append_message(session_id, "assistant", result["answer"])
        emit("realtime:result", {
            "detected": result.get("detected", False),
            "behavior": result.get("behavior", "unknown"),
            "confidence": result.get("confidence", 0),
            "source": result.get("source", "none"),
            "answer": result.get("answer") if result.get("detected") else None,
            "subtitle": result.get("subtitle", ""),
            "audio_base64": result.get("audio_base64") if result.get("detected") else None,
            "audio_mime": result.get("audio_mime"),
            "lip_sync": result.get("lip_sync") if result.get("detected") else None,
        })

    # 工单18：YOLO11n + ByteTrack 实时摄像头帧处理 (服务端视觉识别)
    @sio.on("realtime:yolo_frame")
    def on_realtime_yolo_frame(data):
        session_id = data.get("session_id", "")
        language = data.get("language", "zh")
        image_b64 = data.get("image", "")
        if not image_b64:
            emit("realtime:result", {
                "detected": False, "behavior": "unknown", "confidence": 0,
                "source": "yolo_error", "error": "未收到图像数据"
            })
            return

        detector = get_yolo_detector()
        # 节流控制：每 0.5 秒处理一帧
        if not detector.should_process():
            emit("realtime:result", {
                "detected": False, "behavior": "throttled", "confidence": 0,
                "source": "yolo", "subtitle": "帧率节流中..."
            })
            return

        try:
            yolo_result = detector.process_base64(image_b64)
        except Exception as exc:
            logger = __import__("logging").getLogger(__name__)
            logger.exception("YOLO 帧处理异常")
            emit("realtime:result", {
                "detected": False, "behavior": "unknown", "confidence": 0,
                "source": "yolo_error", "error": str(exc)
            })
            return

        # 打印完整诊断信息到服务器控制台
        diag = yolo_result.get('diag', ['无诊断'])
        import logging
        _log = logging.getLogger("yolo_behavior")
        _log.info("%s (%sms)", " | ".join(diag), yolo_result['time_ms'])

        if yolo_result["detected"]:
            behavior = yolo_result["behavior"]
            from services.guide_service import handle_behavior_chat
            guide_result = handle_behavior_chat(current_app.config, behavior, language, get_recent_messages(session_id))
            append_message(session_id, "user", f"实时识别动作：{behavior}")
            append_message(session_id, "assistant", guide_result["answer"])
            emit("realtime:result", {
                "detected": True,
                "behavior": behavior,
                "confidence": yolo_result["confidence"],
                "source": yolo_result["source"],
                "persons": yolo_result.get("persons", []),
                "answer": guide_result.get("answer"),
                "subtitle": guide_result.get("subtitle", ""),
                "audio_base64": guide_result.get("audio_base64"),
                "audio_mime": guide_result.get("audio_mime"),
                "lip_sync": guide_result.get("lip_sync"),
                "time_ms": yolo_result.get("time_ms", 0),
                "diag": yolo_result.get("diag", []),
            })
        else:
            # 未检测到行为时也返回诊断信息，帮助排查
            emit("realtime:result", {
                "detected": False,
                "behavior": "unknown",
                "confidence": yolo_result["confidence"],
                "source": yolo_result["source"],
                "persons": yolo_result.get("persons", []),
                "time_ms": yolo_result.get("time_ms", 0),
                "diag": yolo_result.get("diag", []),
                "person_count": yolo_result.get("person_count", 0),
            })

    # 工单18：TTS 请求（单独触发，不需要完整对话）
    @sio.on("tts:speak")
    def on_tts_speak(data):
        text = data.get("text", "")
        if not text.strip():
            return
        speech = synthesize_speech(text)
        emit("tts:audio", {
            "audio_base64": speech.get("audio_base64"),
            "audio_mime": speech.get("audio_mime"),
            "lip_sync": speech.get("lip_sync"),
            "duration": speech.get("duration"),
        })
