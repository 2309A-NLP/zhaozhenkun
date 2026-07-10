"""工单18：REST API 蓝图 — 会话、文本、图片、语音、视频、行为、Agent调度接口。"""
from pathlib import Path
from flask import Blueprint, current_app, jsonify, request, Response
from services.session_service import append_message, create_session, get_recent_messages
from services.knowledge_service import load_spots
from services.guide_service import handle_behavior_chat, handle_image_chat, handle_text_chat, handle_video_chat
from services.realtime_route_service import handle_realtime_behavior
from services.yolo_behavior_service import detect_from_frame as yolo_detect_from_frame
from services.audio_service import transcribe_audio
from services.digital_human_service import get_digital_human_config
from services.agent_service import agent_plan_and_execute

api_bp = Blueprint("api_bp", __name__)

# 工单18：预加载 HTML 内容，绕过 Jinja2 模板缓存
_HTML_PATH = Path(__file__).resolve().parent.parent / "web" / "templates" / "index.html"

def fail(message: str, status: int = 400):
    return jsonify({"ok": False, "error": message}), status

@api_bp.get("/")
def index():
    # 工单18：每次都直接从磁盘读取 HTML，绝不缓存
    html = _HTML_PATH.read_text(encoding="utf-8")
    return Response(html, mimetype="text/html")

@api_bp.get("/ping")
def ping():
    return jsonify({"ok": True, "message": "service alive"})

@api_bp.get("/api/digital-human/config")
def digital_human_config():
    return jsonify({"ok": True, "config": get_digital_human_config()})

@api_bp.post("/api/session/create")
def create_session_api():
    return jsonify({"ok": True, **create_session()})

@api_bp.get("/api/knowledge/spots")
def list_spots():
    return jsonify({"ok": True, "spots": load_spots()})

@api_bp.post("/api/chat/text")
def text_chat():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "")
    question = data.get("question", "").strip()
    language = data.get("language", "zh")
    if not question:
        return fail("问题不能为空")
    append_message(session_id, "user", question)
    result = handle_text_chat(current_app.config, question, language, get_recent_messages(session_id))
    append_message(session_id, "assistant", result["answer"])
    return jsonify({"ok": True, **result, "language": language, "digital_human_state": "speaking"})

@api_bp.post("/api/chat/audio")
def audio_chat():
    session_id = request.form.get("session_id", "")
    language = request.form.get("language", "zh")
    audio = request.files.get("audio")
    if audio is None:
        return fail("未上传语音文件")
    transcript = transcribe_audio(audio.read(), ".wav")
    append_message(session_id, "user", transcript)
    result = handle_text_chat(current_app.config, transcript, language, get_recent_messages(session_id))
    append_message(session_id, "assistant", result["answer"])
    return jsonify({"ok": True, **result, "transcript": transcript, "language": language, "digital_human_state": "speaking"})

@api_bp.post("/api/chat/image")
def image_chat():
    session_id = request.form.get("session_id", "")
    question = request.form.get("question", "请讲解这张图片")
    language = request.form.get("language", "zh")
    image = request.files.get("image")
    if image is None:
        return fail("未上传图片")
    append_message(session_id, "user", question)
    result = handle_image_chat(current_app.config, question, language, get_recent_messages(session_id), image.read())
    append_message(session_id, "assistant", result["answer"])
    return jsonify({"ok": True, **result, "language": language, "digital_human_state": "speaking"})

@api_bp.post("/api/chat/video")
def video_chat():
    session_id = request.form.get("session_id", "")
    question = request.form.get("question", "请讲解这段视频")
    language = request.form.get("language", "zh")
    video = request.files.get("video")
    if video is None:
        return fail("未上传视频")
    suffix = ".mp4" if not video.filename else "." + video.filename.split(".")[-1]
    append_message(session_id, "user", question)
    result = handle_video_chat(current_app.config, question, language, get_recent_messages(session_id), video.read(), suffix)
    append_message(session_id, "assistant", result["answer"])
    return jsonify({"ok": True, **result, "language": language, "digital_human_state": "speaking"})

@api_bp.post("/api/chat/behavior")
def behavior_chat():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "")
    behavior = data.get("behavior", "unknown")
    language = data.get("language", "zh")
    append_message(session_id, "user", f"行为事件：{behavior}")
    result = handle_behavior_chat(current_app.config, behavior, language, get_recent_messages(session_id))
    append_message(session_id, "assistant", result["answer"])
    return jsonify({"ok": True, **result, "language": language, "digital_human_state": behavior})

@api_bp.post("/api/realtime/behavior")
def realtime_behavior_chat():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "")
    language = data.get("language", "zh")
    result = handle_realtime_behavior(current_app.config, data, language, get_recent_messages(session_id))
    if result.get("detected"):
        append_message(session_id, "user", f"实时识别动作：{result['behavior']}")
        append_message(session_id, "assistant", result["answer"])
    return jsonify({"ok": True, **result, "language": language, "digital_human_state": result.get("behavior", "idle")})


# 工单18：YOLO11n+ByteTrack 实时摄像头行为识别 (HTTP fallback)
@api_bp.post("/api/realtime/yolo-behavior")
def yolo_behavior_chat():
    data = request.get_json(silent=True) or {}
    session_id = data.get("session_id", "")
    language = data.get("language", "zh")
    image_b64 = data.get("image", "")
    if not image_b64:
        return fail("未收到图像数据")
    # 工单18：帧率节流 — 跳过过于频繁的请求，避免积压
    from services.yolo_behavior_service import get_detector as _get_yolo
    detector = _get_yolo()
    if not detector.should_process():
        return jsonify({"ok": True, "detected": False, "behavior": "throttled",
                        "confidence": 0, "source": "yolo", "language": language,
                        "subtitle": "帧率节流中...", "diag": ["throttled"]})
    try:
        result = yolo_detect_from_frame(image_b64)
    except Exception as exc:
        return fail(f"YOLO 处理异常: {exc}", 500)
    if result.get("detected"):
        append_message(session_id, "user", f"实时识别动作：{result['behavior']}")
        guide_result = handle_behavior_chat(current_app.config, result["behavior"], language, get_recent_messages(session_id))
        append_message(session_id, "assistant", guide_result["answer"])
        result.update({
            "answer": guide_result.get("answer"),
            "subtitle": guide_result.get("subtitle", ""),
            "audio_base64": guide_result.get("audio_base64"),
            "audio_mime": guide_result.get("audio_mime"),
            "lip_sync": guide_result.get("lip_sync"),
        })
    return jsonify({"ok": True, **result, "language": language})


# 工单18：Agent 调度接口 — PDF 要求的 LangChain/CrewAI 等效实现。
@api_bp.post("/api/agent/task")
def agent_task():
    data = request.get_json(silent=True) or {}
    task = data.get("task", "").strip()
    language = data.get("language", "zh")
    if not task:
        return fail("任务描述不能为空")
    result = agent_plan_and_execute(current_app.config, task, language)
    return jsonify({"ok": True, **result})

def register_api_routes(app):
    app.register_blueprint(api_bp)
