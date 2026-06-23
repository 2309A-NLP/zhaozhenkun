# -*- coding: utf-8 -*-
"""
main.py — Agent智能体Web应用（文本+图片，5工具路由）
工单编号：人工智能NLP-Agent数字人项目-智能体任务
"""

import json, time, os, sys, logging, base64, re  # 标准库
from flask import Flask, request, jsonify, render_template  # Flask
import config  # 配置
from agent_core import process_query  # Agent引擎

# 日志
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent.log")
_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S")
_fh = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8'); _fh.setLevel(logging.DEBUG); _fh.setFormatter(_fmt)
_ch = logging.StreamHandler(sys.stdout); _ch.setLevel(logging.INFO); _ch.setFormatter(_fmt)
_root = logging.getLogger(); _root.setLevel(logging.DEBUG)
for h in list(_root.handlers): _root.removeHandler(h)
_root.addHandler(_fh); _root.addHandler(_ch)
logger = logging.getLogger("agent")
logging.getLogger("werkzeug").setLevel(logging.WARNING)

PORT = 5002
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "..", "部署", "templates"))
sessions = {}

@app.after_request
def no_cache(r): r.headers['Cache-Control'] = 'no-cache'; return r

@app.route('/')
def index(): return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def api_chat():
    q, img_b64, sid = "", None, "default"
    if request.is_json:
        data = request.get_json()
        if not data: return jsonify({"error": "请求体为空"}), 400
        q = data.get('question', '').strip()
        img_b64 = data.get('image', None)
        sid = data.get('session', 'default')
    else:
        q = request.form.get('question', '').strip()
        sid = request.form.get('session', 'default')
        if 'image' in request.files: img_b64 = base64.b64encode(request.files['image'].read()).decode('utf-8')
    if not q and not img_b64: return jsonify({"error": "问题或图片不能都为空"}), 400
    if not q: q = "请处理这张图片"

    # 清洗输入：去乱码碎片
    for noise in ['北京八维信息集团', '人工智能 NLP 方向', '任务工单', '八维文化与产业研究院']:
        q = q.replace(noise, '')
    # 修复PDF复制导致的汉字间多余空格（景 顺 长 城 → 景顺长城，债券 C 基金 → 债券C基金）
    q = re.sub(r'(?<=[一-鿿])\s+(?=[一-鿿])', '', q)
    q = re.sub(r'(?<=[一-鿿])\s+(?=[A-Za-z0-9])', '', q)
    q = re.sub(r'(?<=[A-Za-z0-9])\s+(?=[一-鿿])', '', q)
    q = re.sub(r'\s+', ' ', q).strip()[:500]

    if sid not in sessions: sessions[sid] = []
    history = sessions[sid]
    full_q = q + (" [附带图片]" if img_b64 else "")
    logger.info("📩 [%s] %s (图=%s)", sid[:8], q[:80], "有" if img_b64 else "无")

    # 优先识别意图（只调用一次，避免重复）
    intent_tool = None
    if not img_b64:
        from agent_core import recognize_intent
        intent_tool, _, _ = recognize_intent(q, history if sid in sessions else None)
        logger.info("🎯 意图预判: %s", intent_tool)

    # 优先查演示数据库（仅在意图不明确时使用）
    demo_result = None
    DEMO_DB = os.path.join(BASE_DIR, "..", "部署", "demo_qa.db")
    if os.path.exists(DEMO_DB) and (not intent_tool or intent_tool == 'unknown'):
        import sqlite3 as _sql
        _dc = _sql.connect(DEMO_DB); _dc.row_factory = _sql.Row; _cur = _dc.cursor()
        q_clean = q.rstrip('？?。，,. !！')
        _cur.execute("SELECT question, answer, keywords FROM demo_answers")
        best_score, best_answer = 0, None
        for row in _cur.fetchall():
            dq, da, dk = row['question'], row['answer'], row['keywords']
            kws = dk.split()
            score = sum(1 for kw in kws if kw in q_clean)
            if dq in q_clean or q_clean in dq: score += 10
            if score > best_score: best_score, best_answer = score, da
        if best_score >= 5 and best_answer:
            logger.info("🎯 Demo命中(得分%d): %s", best_score, q_clean[:40])
            t1 = time.time()
            import requests as _req
            _msg = [{"role":"system","content":"根据参考信息自然回答用户问题，简洁直接。"},
                    {"role":"user","content":f"参考信息:\n{best_answer}\n\n用户问题: {q}\n\n自然回答:"}]
            _url = f"{config.DEEPSEEK_BASE_URL}/chat/completions"
            _hd = {"Authorization": f"Bearer {config.DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
            _pl = {"model": config.DEEPSEEK_MODEL, "messages": _msg, "temperature": 0.0, "max_tokens": 1024, "stream": False}
            try:
                _r = _req.post(_url, headers=_hd, json=_pl, timeout=10)
                if _r.status_code == 200:
                    resp_content = _r.json()["choices"][0]["message"].get("content", "").strip()
                    if resp_content:
                        demo_result = {"answer": resp_content, "tool": "", "elapsed": round(time.time() - t1, 2)}
            except: pass
        else:
            logger.info("Demo未命中: %s", q_clean[:40])
        _dc.close()

    # 路由决策：demo结果 > 图片处理 > 工具路由
    if demo_result:
        result = demo_result
    elif img_b64:
        from tools import tool_text2image
        r = tool_text2image(q, img_b64)
        result = {"answer": r['result'], "tool": r['tool'], "elapsed": 0}
        if isinstance(r, dict) and r.get("images"):
            result["images"] = r["images"]
    else:
        result = process_query(q, history, pre_recognized_tool=intent_tool)

    history.append({"role": "user", "content": q})
    history.append({"role": "assistant", "content": result['answer'][:500]})
    if len(history) > config.MAX_HISTORY * 2: history = history[-config.MAX_HISTORY * 2:]
    sessions[sid] = history
    response = {"answer": result['answer'], "tool": result['tool'], "elapsed": result['elapsed'], "_v": 3}
    if result.get("images"):
        response["images"] = result["images"]
    return jsonify(response)

@app.route('/api/health')
def health(): return jsonify({"status": "ok"})
 
def main():
    logger.info("=" * 50)
    logger.info("🚀 Agent智能体已启动")
    logger.info("🌐 http://127.0.0.1:%d", PORT)
    logger.info("=" * 50)
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)

if __name__ == "__main__": main()
