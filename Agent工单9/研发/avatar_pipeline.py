# -*- coding: utf-8 -*-
"""
avatar_pipeline.py — 数字人头像/视频/指标路由
--------------------------------------------------------------
功能: 注册数字人头像管理、MJPEG 视频流、性能和状态相关的 Flask 路由。

端点:
  POST /api/avatar/upload    — 上传数字人头像（含人物的静态图片）
  GET  /api/avatar/current   — 获取当前数字人头像信息
  POST /api/dh/reload        — 手动重载数字人引擎（占位→SadTalker恢复）
  GET  /api/video/stream     — MJPEG 数字人视频流
  GET  /api/voice/status     — 语音管线状态（ASR/TTS/DH/SLA）
  GET  /api/metrics          — SLA 性能指标

被 main.py 的 main() 函数调用 register_avatar_routes() 注册路由。

工单编号: 人工智能NLP-Agent数字人项目-数字人与智能体的集成任务
所属目录: 研发
"""
import os          # 文件路径操作
import time        # 帧率控制（MJPEG 流）
import uuid        # 唯一文件名生成
import logging     # 日志记录
import base64      # Base64 编解码

import numpy as np # 数值计算（视频帧处理）

from flask import request, jsonify, Response  # Flask 请求/响应/流式

# 模块日志器
logger = logging.getLogger("agent")


def register_avatar_routes(app, sessions, video_frame_buffer, output_dir, base_dir):
    """注册数字人头像/视频/指标相关的 Flask 路由

    参数:
        app: Flask 应用实例
        sessions: 多轮对话 session 字典（shared with main.py）
        video_frame_buffer: 数字人视频帧缓冲字典（sid → deque）
        output_dir: 视频输出目录
        base_dir: 研发目录路径
    """

    # ================================================================
    # POST /api/avatar/upload — 数字人头像上传
    # ================================================================
    @app.route('/api/avatar/upload', methods=['POST'])
    def api_avatar_upload():
        """上传数字人头像（含人物的静态图片）。
        上传后所有后续数字人视频都将使用该形象。"""
        avatar_data = None
        avatar_name = "avatar"

        # 解析上传的头像数据
        if 'avatar' in request.files:                    # multipart 文件上传
            f = request.files['avatar']
            avatar_data = f.read()
            avatar_name = request.form.get('name', 'avatar')
        elif request.is_json:                             # JSON + base64
            data = request.get_json() or {}
            b64 = data.get('avatar', '')
            if b64:
                avatar_data = base64.b64decode(b64)
            avatar_name = data.get('name', 'avatar')
        else:
            return jsonify({"error": "请上传头像图片（字段名: avatar）"}), 400

        if not avatar_data:
            return jsonify({"error": "头像数据为空"}), 400

        # 保存头像到 static/avatars/ 目录
        avatars_dir = os.path.normpath(
            os.path.join(base_dir, "..", "static", "avatars")
        )
        os.makedirs(avatars_dir, exist_ok=True)
        avatar_filename = f"{avatar_name}_{uuid.uuid4().hex[:8]}.png"
        avatar_path = os.path.join(avatars_dir, avatar_filename)
        with open(avatar_path, "wb") as f:
            f.write(avatar_data)

        # 注册到数字人引擎（激活新头像）
        dh_updated = False
        try:
            from digital_human import get_digital_human
            dh = get_digital_human()
            dh_updated = dh.set_avatar(avatar_path)  # 设置并持久化
        except Exception as\
                e:
            logger.warning("数字人引擎注册头像失败: %s", e)

        logger.info("📷 数字人头像已上传: %s (%dKB, 数字人=%s)",
                     avatar_filename, len(avatar_data) / 1024,
                     "已激活" if dh_updated else "已保存")

        return jsonify({
            "status": "ok",
            "avatar_url": f"/static/avatars/{avatar_filename}",
            "avatar_path": avatar_path,
            "size_kb": round(len(avatar_data) / 1024, 1),
            "digital_human_active": dh_updated,
            "message": (
                "头像已激活！现在数字人将使用该形象回答问题。"
                if dh_updated
                else "头像已保存。请重启服务以激活数字人形象。"
            ),
            "usage": {
                "chat_with_video": "POST /api/chat {\"question\":\"...\", \"tts\":true}",
                "voice_chat": "POST /api/voice/chat (上传音频)",
            },
        })


    # ================================================================
    # GET /api/avatar/current — 获取当前数字人头像信息
    # ================================================================
    @app.route('/api/avatar/current')
    def api_avatar_current():
        """获取当前数字人头像信息（含路径、URL、引擎类型、分辨率等）。"""
        try:
            from digital_human import get_digital_human
            dh = get_digital_human()

            # 将绝对路径转为前端可访问的 static URL
            avatar_url = None
            avatar_path = dh.avatar_path
            # 懒加载: avatar_path 为空时从持久化文件恢复
            if not avatar_path:
                try:
                    if os.path.exists(dh.LAST_AVATAR_FILE):
                        with open(dh.LAST_AVATAR_FILE, 'r') as f:
                            avatar_path = f.read().strip()
                except Exception:
                    pass

            if avatar_path:
                rel = avatar_path.replace('\\', '/')  # Windows→URL 兼容
                if '/static/' in rel:
                    avatar_url = '/static/' + rel.split('/static/', 1)[1]

            return jsonify({
                "has_avatar": dh.has_avatar,
                "avatar_path": avatar_path,
                "avatar_url": avatar_url,
                "engine_type": dh.engine_type,
                "is_loaded": dh.is_loaded,
                "resolution": f"{dh.width}x{dh.height}",
            })
        except Exception as e:
            return jsonify({"error": str(e)[:100]}), 500


    # ================================================================
    # POST /api/dh/reload — 手动重载数字人引擎
    # ================================================================
    @app.route('/api/dh/reload', methods=['POST'])
    def api_dh_reload():
        """手动重载数字人引擎（从占位模式恢复到 SadTalker）。
        用于处理启动时 GPU 显存不足导致的瞬时加载失败。"""
        try:
            from digital_human import get_digital_human
            dh = get_digital_human()
            ok = dh.try_recover_sadtalker()  # 尝试恢复
            return jsonify({
                "recovered": ok,
                "engine_type": dh.engine_type,
                "message": (
                    "SadTalker 已恢复！现在可以使用唇形同步。"
                    if ok
                    else "恢复失败，请检查 GPU 显存。可尝试重启服务。"
                ),
            })
        except Exception as e:
            return jsonify({"error": str(e)[:200]}), 500


    # ================================================================
    # GET /api/video/stream — MJPEG 数字人视频流
    # ================================================================
    @app.route('/api/video/stream')
    def api_video_stream():
        """MJPEG 视频流端点。
        前端 <img> 标签指向此 URL 即可显示数字人唇形视频。
        对应工单需求: "生成回复视频"、"音视频同步对话" """
        sid = request.args.get('session', 'default')

        def generate():
            """MJPEG 流生成器（~25fps）。"""
            import cv2
            # 默认占位帧（深色背景 + 提示文字）
            empty = np.zeros((720, 1280, 3), dtype=np.uint8)
            cv2.putText(empty, "AI Digital Human", (400, 360),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 2)
            _, default_jpg = cv2.imencode('.jpg', empty)
            last = default_jpg.tobytes()  # 当前要发送的帧

            while True:
                try:
                    frames = video_frame_buffer.get(sid, None)
                    if frames and len(frames) > 0:
                        frame = frames[-1]  # 取最新帧
                        if frame is not None and frame.size > 0:
                            _, jpg = cv2.imencode('.jpg', frame)
                            last = jpg.tobytes()
                except Exception:
                    pass  # 出错保持上一帧

                # 发送 MJPEG 帧（multipart/x-mixed-replace 格式）
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'
                       + last + b'\r\n')
                time.sleep(0.04)  # ~25fps

        return Response(
            generate(),
            mimetype='multipart/x-mixed-replace; boundary=frame',
            headers={'Cache-Control': 'no-cache'}
        )


    # ================================================================
    # GET /api/voice/status — 语音管线全状态检查
    # ================================================================
    @app.route('/api/voice/status')
    def api_voice_status():
        """语音管线状态检查: ASR / TTS / 数字人 / SLA。"""
        status = {"voice_pipeline": "09-数字人与智能体的集成"}

        # ASR 状态
        try:
            from asr_engine import get_asr_engine
            asr = get_asr_engine()
            status["asr"] = {
                "engine": asr.engine_type,
                "model": asr.model_name,
                "loaded": asr.is_loaded,
            }
        except Exception as e:
            status["asr"] = {"error": str(e)[:100]}

        # TTS 状态
        try:
            from tts_engine import get_tts_engine
            tts = get_tts_engine()
            status["tts"] = {
                "engine": "gptsovits",
                "available": tts.check_available(),
                "api_url": tts.api_url,
                "has_ref_audio": bool(tts.ref_audio_path),
            }
        except Exception as e:
            status["tts"] = {"error": str(e)[:100]}

        # 数字人状态
        try:
            from digital_human import get_digital_human
            dh = get_digital_human()
            status["digital_human"] = {
                "engine": "livetalking",
                "loaded": dh.is_loaded,
                "has_avatar": dh.has_avatar,
                "resolution": f"{dh.width}x{dh.height}",
            }
        except Exception as e:
            status["digital_human"] = {"error": str(e)[:100]}

        # SLA 指标
        try:
            from metrics import get_metrics
            m = get_metrics()
            status["sla"] = m.check_sla()
            status["sla_summary"] = m.summary()
        except Exception as e:
            status["sla"] = {"error": str(e)[:100]}

        return jsonify(status)


    # ================================================================
    # GET /api/metrics — SLA 性能指标
    # ================================================================
    @app.route('/api/metrics')
    def api_metrics():
        """SLA性能指标端点。对照工单: 数字人响应≤3S。"""
        try:
            from metrics import get_metrics
            m = get_metrics()
            return jsonify({
                "stages": {name: {"last_ms": round(s.last_ms, 1), "avg_ms": round(s.avg_ms, 1),
                                   "p95_ms": round(s.p95_ms, 1), "count": s.count}
                           for name, s in m.stages.items()},
                "sla": m.check_sla(), "summary": m.summary(),
                "all_ok": all(v["ok"] for v in m.check_sla().values()),
            })
        except ImportError:
            return jsonify({"error": "metrics模块不可用"}), 503
