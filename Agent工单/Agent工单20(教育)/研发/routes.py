# 工单20：本文件用于注册页面路由与接口路由。
# 工单20：导入JSON处理工具。
import json  # 工单20：代码语句。
# 工单20：导入蓝图与请求工具。
from flask import Blueprint, jsonify, redirect, render_template, request, url_for  # 工单20：代码语句。
# 工单20：导入仓储服务。
from services.repository import InterviewRepository  # 工单20：代码语句。
# 工单20：导入模型服务。
from services.llm_service import LLMService  # 工单20：代码语句。
# 工单20：导入音频服务。
from services.audio_service import AudioService  # 工单20：代码语句。
# 工单20：导入复盘服务。
from services.review_service import ReviewService  # 工单20：代码语句。

# 工单20：定义蓝图构建函数。
def create_web_blueprint(settings: dict) -> Blueprint:  # 工单20：代码语句。
    # 工单20：初始化页面蓝图。
    web = Blueprint("web", __name__)  # 工单20：代码语句。
    # 工单20：实例化仓储服务。
    repository = InterviewRepository(settings.get("data_dir"))  # 工单20：代码语句。
    # 工单20：实例化模型服务。
    llm_service = LLMService(settings)  # 工单20：代码语句。
    # 工单20：实例化音频服务。
    audio_service = AudioService(settings)  # 工单20：代码语句。
    # 工单20：实例化复盘服务。
    review_service = ReviewService(repository, llm_service)  # 工单20：代码语句。

    # 工单20：定义首页路由。
    @web.route("/")  # 工单20：代码语句。
    def index():  # 工单20：代码语句。
        # 工单20：读取面试记录列表。
        interviews = repository.list_interviews()  # 工单20：代码语句。
        # 工单20：读取查询关键词。
        keyword = (request.args.get("keyword") or "").strip()  # 工单20：代码语句。
        # 工单20：读取来源筛选条件。
        source_type = (request.args.get("source_type") or "all").strip()  # 工单20：代码语句。
        # 工单20：按关键词筛选记录。
        if keyword:  # 工单20：代码语句。
            interviews = [item for item in interviews if keyword.lower() in json.dumps(item, ensure_ascii=False).lower()]  # 工单20：代码语句。
        # 工单20：按来源筛选记录。
        if source_type in {"teacher_import", "student_report"}:  # 工单20：代码语句。
            interviews = [item for item in interviews if item.get("source_type") == source_type]  # 工单20：代码语句。
        # 工单20：统计总记录数。
        total_count = len(interviews)  # 工单20：代码语句。
        # 工单20：统计有录音记录数。
        audio_count = sum(1 for item in interviews if item.get("audio_file_name"))  # 工单20：代码语句。
        # 工单20：统计待完善记录数。
        pending_count = sum(1 for item in interviews if item.get("status") == "待完善")  # 工单20：代码语句。
        # 工单20：统计学生填报记录数。
        student_count = sum(1 for item in interviews if item.get("source_type") == "student_report")  # 工单20：代码语句。
        # 工单20：渲染首页。
        return render_template("index.html", interviews=interviews, model_status=llm_service.get_status(), keyword=keyword, source_type=source_type, total_count=total_count, audio_count=audio_count, pending_count=pending_count, student_count=student_count)  # 工单20：代码语句。

    # 工单20：定义学生记录详情页路由。
    @web.route("/interviews/<interview_id>")  # 工单20：代码语句。
    def interview_detail(interview_id: str):  # 工单20：代码语句。
        # 工单20：读取单条记录。
        interview = repository.get_interview(interview_id)  # 工单20：代码语句。
        # 工单20：目标不存在时跳回首页。
        if not interview:  # 工单20：代码语句。
            return redirect(url_for("web.index"))  # 工单20：代码语句。
        # 工单20：渲染详情页面。
        return render_template("detail.html", interview=interview, can_edit=repository.can_edit(interview))  # 工单20：代码语句。

    # 工单20：定义AI复盘详情页路由。
    @web.route("/reviews/<interview_id>")  # 工单20：代码语句。
    def review_detail(interview_id: str):  # 工单20：代码语句。
        # 工单20：读取提供方参数。
        provider = request.args.get("provider") or settings.get("default_provider", "deepseek")  # 工单20：代码语句。
        # 工单20：读取缓存或生成复盘。
        result = review_service.get_or_create_review(interview_id, provider)  # 工单20：代码语句。
        # 工单20：失败时跳回首页。
        if not result.get("ok"):  # 工单20：代码语句。
            return redirect(url_for("web.index"))  # 工单20：代码语句。
        # 工单20：渲染复盘详情页面。
        return render_template("review.html", interview=result["interview"], review=result["review"], provider=provider)  # 工单20：代码语句。

    # 工单20：定义健康检查接口。
    @web.route("/api/health")  # 工单20：代码语句。
    def health():  # 工单20：代码语句。
        # 工单20：返回当前服务状态。
        return jsonify({"ok": True, "app_name": settings.get("app_name"), "model_status": llm_service.get_status()})  # 工单20：代码语句。

    # 工单20：定义模型状态接口。
    @web.route("/api/models")  # 工单20：代码语句。
    def models():  # 工单20：代码语句。
        # 工单20：返回前端切换模型所需状态。
        return jsonify({"ok": True, "data": llm_service.get_status()})  # 工单20：代码语句。

    # 工单20：定义面试列表接口。
    @web.route("/api/interviews")  # 工单20：代码语句。
    def list_interviews_api():  # 工单20：代码语句。
        # 工单20：返回全部面试记录。
        return jsonify({"ok": True, "data": repository.list_interviews()})  # 工单20：代码语句。

    # 工单20：定义批量导入接口。
    @web.route("/api/interviews/import", methods=["POST"])  # 工单20：代码语句。
    def import_interviews():  # 工单20：代码语句。
        # 工单20：读取JSON请求体。
        payload = request.get_json(silent=True) or {}  # 工单20：代码语句。
        # 工单20：读取导入记录列表。
        rows = payload.get("rows") or []  # 工单20：代码语句。
        # 工单20：读取上报人名称。
        reporter_name = payload.get("reporter_name") or "就业指导老师"  # 工单20：代码语句。
        # 工单20：执行批量导入。
        imported = repository.import_rows(rows, reporter_name)  # 工单20：代码语句。
        # 工单20：返回导入结果。
        return jsonify({"ok": True, "message": f"成功导入 {imported} 条面试记录。", "count": imported})  # 工单20：代码语句。

    # 工单20：定义录音上传接口。
    @web.route("/api/interviews/<interview_id>/audio", methods=["POST"])  # 工单20：代码语句。
    def upload_audio(interview_id: str):  # 工单20：代码语句。
        # 工单20：读取目标记录。
        interview = repository.get_interview(interview_id)  # 工单20：代码语句。
        # 工单20：校验记录存在。
        if not interview:  # 工单20：代码语句。
            return jsonify({"ok": False, "message": "未找到面试记录。"}), 404  # 工单20：代码语句。
        # 工单20：校验当前记录是否允许编辑。
        if not repository.can_edit(interview):  # 工单20：代码语句。
            return jsonify({"ok": False, "message": "当前记录不在可编辑周期内，无法补传录音。"}), 400  # 工单20：代码语句。
        # 工单20：读取上传文件对象。
        file_storage = request.files.get("audio")  # 工单20：代码语句。
        # 工单20：保存上传文件。
        success, stored_name, message = audio_service.save_upload(file_storage)  # 工单20：代码语句。
        # 工单20：保存失败时返回错误。
        if not success:  # 工单20：代码语句。
            return jsonify({"ok": False, "message": message}), 400  # 工单20：代码语句。
        # 工单20：生成当前版本转写文本。
        audio_text = audio_service.transcribe_audio(stored_name)  # 工单20：代码语句。
        # 工单20：写回记录。
        ok, update_message = repository.update_interview(interview_id, {"audio_file_name": stored_name, "audio_text": audio_text}, interview.get("student_name", "学生"))  # 工单20：代码语句。
        # 工单20：记录更新失败时返回错误。
        if not ok:  # 工单20：代码语句。
            return jsonify({"ok": False, "message": update_message}), 400  # 工单20：代码语句。
        # 工单20：返回成功结果。
        return jsonify({"ok": True, "message": "录音上传成功。", "audio_file_name": stored_name, "audio_text": audio_text})  # 工单20：代码语句。

    # 工单20：定义学生记录更新接口。
    @web.route("/api/interviews/<interview_id>", methods=["POST"])  # 工单20：代码语句。
    def update_interview(interview_id: str):  # 工单20：代码语句。
        # 工单20：读取JSON或表单数据。
        payload = request.get_json(silent=True) or request.form.to_dict()  # 工单20：代码语句。
        # 工单20：尝试解析问答列表字符串。
        question_answers = payload.get("question_answers")  # 工单20：代码语句。
        # 工单20：字符串格式时转成JSON列表。
        if isinstance(question_answers, str) and question_answers.strip():  # 工单20：代码语句。
            payload["question_answers"] = json.loads(question_answers)  # 工单20：代码语句。
        # 工单20：读取编辑者名称。
        editor_name = payload.get("editor_name") or payload.get("student_name") or "学生"  # 工单20：代码语句。
        # 工单20：执行记录更新。
        ok, message = repository.update_interview(interview_id, payload, editor_name)  # 工单20：代码语句。
        # 工单20：返回更新结果。
        return jsonify({"ok": ok, "message": message})  # 工单20：代码语句。

    # 工单20：定义AI复盘生成接口。
    @web.route("/api/reviews/<interview_id>", methods=["POST"])  # 工单20：代码语句。
    def create_review(interview_id: str):  # 工单20：代码语句。
        # 工单20：读取请求体。
        payload = request.get_json(silent=True) or {}  # 工单20：代码语句。
        # 工单20：读取模型提供方。
        provider = payload.get("provider") or settings.get("default_provider", "deepseek")  # 工单20：代码语句。
        # 工单20：读取是否强制重生成。
        refresh = bool(payload.get("refresh"))  # 工单20：代码语句。
        # 工单20：按需清理复盘缓存。
        if refresh:  # 工单20：代码语句。
            repository.clear_review_cache(interview_id)  # 工单20：代码语句。
        # 工单20：执行复盘生成。
        result = review_service.generate_review(interview_id, provider)  # 工单20：代码语句。
        # 工单20：按结果返回状态码。
        status_code = 200 if result.get("ok") else 404  # 工单20：代码语句。
        # 工单20：返回JSON结构。
        return jsonify(result), status_code  # 工单20：代码语句。

    # 工单20：返回注册完成的蓝图。
    return web  # 工单20：代码语句。
