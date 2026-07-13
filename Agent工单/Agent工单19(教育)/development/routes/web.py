"""工单19：个性化学习推荐项目的 Web 页面与接口路由。"""

# 工单19：导入 JSON 工具，用于解析提交的练习答案。
import json

# 工单19：导入 Flask 的蓝图、请求与模板能力。
from flask import Blueprint, jsonify, redirect, render_template, request, url_for

# 工单19：导入默认学生配置。
from development.config import DEFAULT_STUDENT_ID

# 工单19：导入学生画像聚合服务。
from development.services.portrait_service import get_dashboard_snapshot, import_historical_score

# 工单19：导入自适应练习服务。
from development.services.exercise_service import get_adaptive_questions, submit_practice

# 工单19：创建页面蓝图，统一管理路由。
web_blueprint = Blueprint("web", __name__)


# 工单19：读取请求中的学生编号，没有则回退到默认值。
def parse_student_id():
    student_id = request.args.get("student_id") or request.form.get("student_id") or DEFAULT_STUDENT_ID
    try:
        return int(student_id)
    except (TypeError, ValueError):
        return DEFAULT_STUDENT_ID


# 工单19：渲染首页仪表盘，展示画像、推荐路径、任务和错题本。
@web_blueprint.route("/")
def index():
    student_id = parse_student_id()
    dashboard = get_dashboard_snapshot(student_id)
    questions = get_adaptive_questions(student_id)
    return render_template("dashboard.html", dashboard=dashboard, questions=questions)


# 工单19：提供仪表盘 JSON 数据接口，便于前端动态刷新。
@web_blueprint.route("/api/dashboard")
def dashboard_api():
    student_id = parse_student_id()
    return jsonify(get_dashboard_snapshot(student_id))


# 工单19：提供自适应练习题接口，便于前端切换学生后加载新题目。
@web_blueprint.route("/api/questions")
def questions_api():
    student_id = parse_student_id()
    return jsonify({"items": get_adaptive_questions(student_id)})


# 工单19：提交练习答案，更新画像并把错题写入错题本。
@web_blueprint.route("/api/practice/submit", methods=["POST"])
def submit_practice_api():
    payload = request.get_json(silent=True) or {}
    student_id = int(payload.get("student_id", DEFAULT_STUDENT_ID))
    answers = payload.get("answers", [])
    if not isinstance(answers, list) or not answers:
        return jsonify({"error": "answers 不能为空"}), 400
    if any(not item.get("chosen_answer") for item in answers):
        return jsonify({"error": "每道题都需要提交答案"}), 400
    return jsonify(submit_practice(student_id, answers))


# 工单19：导入历史成绩，快速建立学生初始学习画像。
@web_blueprint.route("/api/portrait/import", methods=["POST"])
def import_portrait_api():
    payload = request.get_json(silent=True) or {}
    student_id = int(payload.get("student_id", DEFAULT_STUDENT_ID))
    score = int(payload.get("score", 60))
    return jsonify(import_historical_score(student_id, score))


# 工单19：兼容传统表单提交练习，便于无脚本场景调试。
@web_blueprint.route("/practice/submit", methods=["POST"])
def submit_practice_form():
    student_id = parse_student_id()
    answers = json.loads(request.form.get("answers", "[]"))
    submit_practice(student_id, answers)
    return redirect(url_for("web.index", student_id=student_id))
