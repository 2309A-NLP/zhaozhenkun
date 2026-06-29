# -*- coding: utf-8 -*-
"""
main.py — 医疗挂号 Agent Web 应用入口
--------------------------------------------------------------
功能: Flask Web 应用, 提供聊天 UI + API 端点。
      文本对话: 意图识别→工具路由→挂号业务处理。

工单编号: 人工智能NLP-Agent数字人项目-医疗智能体-挂号管理任务
"""
import json, time, os, sys, logging
from datetime import date

from flask import Flask, request, jsonify, render_template

import config
from agent_core import process_query, recognize_intent

# ================================================================
# 日志配置
# ================================================================
_fmt = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S"
)
_ch = logging.StreamHandler(sys.stdout)
_ch.setLevel(logging.INFO); _ch.setFormatter(_fmt)
_root = logging.getLogger(); _root.setLevel(logging.INFO)
for h in list(_root.handlers): _root.removeHandler(h)
_root.addHandler(_ch)
for _name in ["agent", "agent.core", "agent.tools"]:
    logging.getLogger(_name).setLevel(logging.DEBUG)
for _noisy in ["werkzeug", "urllib3"]:
    logging.getLogger(_noisy).setLevel(logging.WARNING)

logger = logging.getLogger("agent")

# ================================================================
# Flask 应用
# ================================================================
RND_DIR = os.path.dirname(os.path.abspath(__file__))  # 研发/目录
PROJECT_ROOT = os.path.normpath(os.path.join(RND_DIR, ".."))  # 项目根目录
app = Flask(__name__,
            template_folder=os.path.join(PROJECT_ROOT, "部署", "templates"),
            static_folder=os.path.join(PROJECT_ROOT, "static"))
sessions = {}  # sid → history


@app.after_request
def no_cache(r):
    r.headers['Cache-Control'] = 'no-cache'
    return r


@app.route('/')
def index():
    """首页 — 医疗挂号 Agent 聊天界面。"""
    return render_template('index.html')


@app.route('/api/chat', methods=['POST'])
def api_chat():
    """文本对话端点: 接收用户问题 → Agent处理 → 返回答案。"""
    q, sid = "", "default"

    if request.is_json:
        data = request.get_json()
        if not data: return jsonify({"error": "请求体为空"}), 400
        q = data.get('question', '').strip()
        sid = data.get('session', 'default')
    else:
        q = request.form.get('question', '').strip()
        sid = request.form.get('session', 'default')

    if not q:
        return jsonify({"error": "问题不能为空"}), 400

    if sid not in sessions:
        sessions[sid] = []
    history = sessions[sid]

    logger.info("📩 [%s] %s", sid[:8], q[:120])

    # 调用 Agent (带异常兜底, 返回JSON而非500)
    try:
        result = process_query(q, history)
    except Exception as e:
        logger.error("Agent处理异常: %s", e)
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"error": f"处理异常: {str(e)[:200]}",
                       "tool": "error", "elapsed": 0}), 500

    # 更新对话历史
    history.append({"role": "user", "content": q})
    history.append({"role": "assistant", "content": result['answer'][:500]})
    if len(history) > config.MAX_HISTORY * 2:
        history = history[-config.MAX_HISTORY * 2:]
    sessions[sid] = history

    response = {
        "answer": result['answer'],
        "tool": result['tool'],
        "elapsed": result['elapsed'],
        "_v": 1
    }

    return jsonify(response)


@app.route('/api/departments')
def api_departments():
    """获取所有科室列表(供前端挂号向导使用)。"""
    from tool_query import get_dept_list
    depts = get_dept_list()
    return jsonify({"departments": depts})


@app.route('/api/doctors')
def api_doctors():
    """获取指定科室的医生+号源信息(供前端挂号向导使用)。
    参数: dep_id (科室ID), date (可选日期), period (可选时段)"""
    from tool_query import query_schedule
    dep_id = request.args.get('dep_id', type=int)
    target_date = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    period = request.args.get('period')
    if not dep_id:
        return jsonify({"error": "请提供dep_id"}), 400
    schedules = query_schedule(target_date=target_date, period=period)
    # 按dep_id筛选
    doctors = {}
    for s in schedules:
        if s.get('dep_ID') == dep_id:
            d_name = s['d_Name']
            if d_name not in doctors:
                doctors[d_name] = {
                    "d_ID": s['d_ID'], "d_Name": d_name,
                    "d_Profession": s['d_Profession'], "dep_Name": s['dep_Name'],
                    "slots": []
                }
            doctors[d_name]['slots'].append({
                "sch_ID": s['sch_ID'], "sch_Date": s['sch_Date'],
                "sch_Period": s['sch_Period'], "sch_Remain": s['sch_Remain'],
                "sch_Fee": s['sch_Fee']
            })
    return jsonify({"doctors": list(doctors.values())})


@app.route('/api/register', methods=['POST'])
def api_register():
    """直接挂号接口(供前端挂号向导使用)。
    参数: user_id, patient_name, dep_name, doctor_name, target_date, period, title_filter"""
    from tool_register import make_registration
    data = request.get_json() or {}
    result = make_registration(
        user_id=data.get('user_id', 1),
        patient_name=data.get('patient_name'),
        dep_name=data.get('dep_name'),
        doctor_name=data.get('doctor_name'),
        target_date=data.get('target_date'),
        period=data.get('period'),
        title_filter=data.get('title_filter'),
    )
    return jsonify(result)


@app.route('/api/health')
def health():
    """健康检查。"""
    import sqlite3
    db_ok = False
    try:
        conn = sqlite3.connect(config.DB_PATH)
        conn.execute("SELECT 1  FROM department LIMIT 1")
        db_ok = True
        conn.close()
    except Exception:
        pass

    return jsonify({
        "status": "ok" if db_ok else "degraded",
        "agent": "医疗挂号Agent v1.0",
        "database": "connected" if db_ok else "error",
        "model": config.DEEPSEEK_MODEL,
    })


def main():
    """启动医疗挂号Agent Web服务。"""
    logger.info("=" * 50)
    logger.info("🏥 医疗挂号Agent已启动 v1.0")
    logger.info("🌐 http://127.0.0.1:%d", config.PORT)
    logger.info("🤖 模型: %s", config.DEEPSEEK_MODEL)
    logger.info("📋 API: POST /api/chat | GET /api/health")
    logger.info("=" * 50)
    app.run(host='0.0.0.0', port=config.PORT, debug=False, threaded=True)


if __name__ == "__main__":
    main()
