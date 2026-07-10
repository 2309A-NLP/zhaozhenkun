# 这里定义 Flask 应用工厂。
from flask import Flask, jsonify, request, send_from_directory

from config.settings import DATA_FILE
from config.settings import DEEPSEEK_API_KEY
from config.settings import DEEPSEEK_BASE_URL
from config.settings import DEEPSEEK_MODEL
from config.settings import INDEX_FILE
from config.settings import QWEN_API_KEY
from config.settings import QWEN_BASE_URL
from config.settings import QWEN_MODEL
from config.settings import STATIC_DIR
from services.answer_builder import AnswerBuilder
from services.knowledge_base import TourismKnowledgeBase
from services.llm_client import LlmClient
from services.multimodal_tools import extract_ocr_text


def create_app():
    """这里使用延迟初始化创建 Flask 应用。"""
    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
    app.config["JSON_AS_ASCII"] = False
    app.extensions["kb"] = TourismKnowledgeBase(str(DATA_FILE))
    deepseek_client = LlmClient(DEEPSEEK_BASE_URL, DEEPSEEK_API_KEY, DEEPSEEK_MODEL, "deepseek")
    qwen_client = LlmClient(QWEN_BASE_URL, QWEN_API_KEY, QWEN_MODEL, "qwen")
    app.extensions["answer_builder"] = AnswerBuilder(deepseek_client, qwen_client)

    @app.get("/")
    def home():
        # 这里返回独立首页文件。
        return send_from_directory(str(STATIC_DIR), INDEX_FILE)

    @app.get("/api/health")
    def health():
        # 这里返回健康检查信息。
        return jsonify({"status": "ok", "project": "Agent工单17", "task_no": "人工智能CV-AIGC-17", "providers": ["deepseek", "qwen"]})

    @app.post("/api/search")
    def search():
        # 这里读取 JSON 请求体。
        payload = request.get_json(silent=True) or {}
        query = (payload.get("query") or "").strip()
        input_type = payload.get("input_type", "text")
        language = payload.get("language", "zh")
        mode = payload.get("mode", "guide")
        provider = payload.get("provider", "deepseek")
        if not query:
            return jsonify({"error": "query不能为空"}), 400
        results = app.extensions["kb"].search(query)
        best = results[0] if results else None
        if not best:
            return jsonify({"retrieval": {"top_results": []}, "answer": {}})
        template_answer = app.extensions["kb"].build_template_answer(best, mode=mode, language=language)
        answer = app.extensions["answer_builder"].merge_answer(template_answer, best["record"], mode, language, query, provider)
        retrieval = {"input_type": input_type, "query": query, "provider": provider, "top_results": []}
        for item in results:
            retrieval["top_results"].append({"id": item["record"]["id"], "name": item["record"]["name"], "city": item["record"]["city"], "score": item["score"]})
        return jsonify({"retrieval": retrieval, "answer": answer})

    @app.post("/api/image-search")
    def image_search():
        # 这里读取表单和文件。
        query = (request.form.get("query") or "").strip()
        hints = (request.form.get("hints") or "").strip()
        provider = request.form.get("provider", "qwen")
        image_file = request.files.get("image")
        image_bytes = image_file.read() if image_file else b""
        filename = image_file.filename if image_file and image_file.filename else "upload.png"
        ocr_text = extract_ocr_text(image_bytes)
        if not hints and not image_bytes and not query:
            return jsonify({"error": "请提供图片、图片线索或问题"}), 400
        search_text = " ".join([part for part in [hints, query, ocr_text, "文旅图片识别"] if part]).strip()
        results = app.extensions["kb"].multimodal_search(search_text)
        best = results[0] if results else None
        if not best:
            return jsonify({"retrieval": {"top_results": []}, "answer": {}})
        template_answer = app.extensions["kb"].build_template_answer(best, mode="guide", language="zh")
        template_answer["生成内容"] = app.extensions["answer_builder"].build_multimodal_answer(best["record"], query or search_text, provider, image_hint=hints or ocr_text, image_bytes=image_bytes, filename=filename)
        answer = app.extensions["answer_builder"].append_tts_block(template_answer)
        answer["多模态输出"] = app.extensions["answer_builder"].build_multimodal_block(best["record"])
        answer["上传文件名"] = filename if image_bytes else "未上传图片"
        answer["OCR结果"] = ocr_text or "未检测到明显文字"
        retrieval = {"mode": "真实图片上传/图片线索检索", "query": query, "hints": hints, "ocr_text": ocr_text, "provider": provider, "top_results": []}
        for item in results:
            retrieval["top_results"].append({"id": item["record"]["id"], "name": item["record"]["name"], "image_keywords": item["record"].get("image_keywords", []), "video_keywords": item["record"].get("video_keywords", []), "score": item["score"]})
        return jsonify({"retrieval": retrieval, "answer": answer})

    return app
