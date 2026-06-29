# -*- coding: utf-8 -*-
"""
main.py — Agent 智能体 Web 应用入口（文本对话 + 路由注册）
--------------------------------------------------------------
功能: Flask Web 应用主入口。负责日志配置、文本对话管线、健康检查、启动。
      语音/头像/视频/指标路由通过 voice_pipeline 和 avatar_pipeline 模块注册。

工单编号: 人工智能NLP-Agent数字人项目-数字人与智能体的集成任务
所属目录: 研发
"""
import json, time, os, sys, logging, base64, re, uuid  # 标准库
import numpy as np                                      # 数值计算
from flask import Flask, request, jsonify, render_template  # Flask
from collections import deque                           # 视频帧缓冲

import config                      # 全局配置
from agent_core import process_query, recognize_intent  # Agent 核心

# ================================================================
# 日志配置 — 控制台 INFO + 文件 DEBUG
# ================================================================
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agent.log")
_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S")
_fh = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')  # 文件日志
_fh.setLevel(logging.DEBUG); _fh.setFormatter(_fmt)
_ch = logging.StreamHandler(sys.stdout)                          # 控制台日志
_ch.setLevel(logging.INFO); _ch.setFormatter(_fmt)
_root = logging.getLogger(); _root.setLevel(logging.INFO)         # 根日志器
for h in list(_root.handlers): _root.removeHandler(h)
_root.addHandler(_fh); _root.addHandler(_ch)
# 我们自己模块的日志器 DEBUG，第三方库 WARNING
for _name in ["agent", "agent.core", "agent.tools", "asr", "tts",
              "digital_human", "metrics"]:
    logging.getLogger(_name).setLevel(logging.DEBUG)
for _noisy in ["werkzeug", "urllib3", "PIL", "asyncio", "git", "wandb",
               "matplotlib", "imageio", "imageio_ffmpeg", "tensorflow",
               "torch", "transformers"]:
    logging.getLogger(_noisy).setLevel(logging.WARNING)

logger = logging.getLogger("agent")  # 主日志器

# ================================================================
# 文本清洗 — 共享函数（被 voice_pipeline 导入复用）
# ================================================================
_NOISE_WORDS = ['北京八维信息集团', '人工智能 NLP 方向', '任务工单', '八维文化与产业研究院']

def _clean_query(text: str) -> str:
    """清洗用户输入: 去除工单模板碎片、修复PDF汉字间多余空格。返回≤500字。"""
    for noise in _NOISE_WORDS:
        text = text.replace(noise, '')
    text = re.sub(r'(?<=[一-鿿])\s+(?=[一-鿿])', '', text)       # 汉字间空格
    text = re.sub(r'(?<=[一-鿿])\s+(?=[A-Za-z0-9])', '', text)   # 汉字+英文间空格
    text = re.sub(r'(?<=[A-Za-z0-9])\s+(?=[一-鿿])', '', text)   # 英文+汉字间空格
    return re.sub(r'\s+', ' ', text).strip()[:500]

# ================================================================
# Flask 应用初始化
# ================================================================
PORT = 5002
BASE_DIR = os.path.dirname(os.path.abspath(__file__))             # 研发目录
OUTPUT_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "static", "output"))
os.makedirs(OUTPUT_DIR, exist_ok=True)                            # 确保视频输出目录存在
app = Flask(__name__,
            template_folder=os.path.join(BASE_DIR, "..", "部署", "templates"),
            static_folder=os.path.join(BASE_DIR, "..", "static"))
sessions = {}                # 多轮对话 session 存储 (sid → history)
_video_frame_buffer = {}     # 数字人视频帧缓冲 (sid → deque of BGR frames)

@app.after_request
def no_cache(r):
    """Flask 后置钩子 — 为所有响应禁用浏览器缓存。

    参数: r — Flask Response 对象
    返回: 添加了 Cache-Control: no-cache 头的 Response

    目的: 数字人视频流和实时对话响应不应被浏览器缓存，确保每次请求都获取最新数据。
    """
    r.headers['Cache-Control'] = 'no-cache'
    return r


def _try_match_demo_db(q: str) -> dict | None:
    """尝试从 demo_qa.db 快速匹配答案（意图不明确时使用）。
    返回 None 表示未命中；命中时返回 {"answer":..., "tool":"", "elapsed":...}。"""
    DEMO_DB = os.path.join(BASE_DIR, "..", "部署", "demo_qa.db")
    if not os.path.exists(DEMO_DB):
        return None
    import sqlite3 as _sql
    _dc = _sql.connect(DEMO_DB); _dc.row_factory = _sql.Row; _cur = _dc.cursor()
    q_clean = q.rstrip('？?。，,. !！')
    _cur.execute("SELECT question, answer, keywords FROM demo_answers")
    best_score, best_answer = 0, None
    for row in _cur.fetchall():
        dq, da, dk = row['question'], row['answer'], row['keywords']
        score = sum(1 for kw in dk.split() if kw in q_clean)  # 关键词命中
        if dq in q_clean or q_clean in dq:
            score += 10  # 精确匹配加分
        if score > best_score:
            best_score, best_answer = score, da
    if best_score >= 5 and best_answer:
        logger.info("🎯 Demo命中(得分%d): %s", best_score, q_clean[:40])
        t1 = time.time()
        import requests as _req
        _msg = [{"role": "system", "content": "根据参考信息自然回答用户问题，简洁直接。"},
                {"role": "user", "content": f"参考信息:\n{best_answer}\n\n用户问题: {q}\n\n自然回答:"}]
        _url = f"{config.DEEPSEEK_BASE_URL}/chat/completions"
        _hd = {"Authorization": f"Bearer {config.DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
        _pl = {"model": config.DEEPSEEK_MODEL, "messages": _msg, "temperature": 0.0, "max_tokens": 1024, "stream": False}
        try:
            _r = _req.post(_url, headers=_hd, json=_pl, timeout=10)
            if _r.status_code == 200:
                ans = _r.json()["choices"][0]["message"].get("content", "").strip()
                if ans:
                    _dc.close()
                    return {"answer": ans, "tool": "快速匹配", "elapsed": round(time.time() - t1, 2)}
        except Exception:
            pass
    _dc.close()
    return None


def _try_generate_video(answer: str, tts_audio: np.ndarray, sid: str) -> dict:
    """尝试生成数字人视频帧并保存MP4。返回 {"video_url"?: str, "dh_engine"?: str, ...}。"""
    info = {}
    try:
        from digital_human import get_digital_human
        dh = get_digital_human()
        vf = dh.generate_video(tts_audio, answer[:200])
        info["video_frames"] = len(vf); info["dh_engine"] = dh.engine_type
        info["avatar_set"] = dh.has_avatar
        # 唇形同步诊断: 记录帧数 vs 音频时长
        audio_dur = len(tts_audio) / 16000.0
        expected_frames = int(audio_dur * 25)
        if abs(len(vf) - expected_frames) > 1:
            logger.warning("唇形同步警告: 视频%d帧 vs 音频%.2fs(期望%d帧) 偏差%+d帧",
                         len(vf), audio_dur, expected_frames, len(vf) - expected_frames)
        # 存入全局帧缓冲（MJPEG流）
        if sid not in _video_frame_buffer:
            _video_frame_buffer[sid] = deque(maxlen=60)
        for f in vf[-30:]:
            _video_frame_buffer[sid].append(f)
        # 合成MP4
        if vf:
            video_name = f"reply_{uuid.uuid4().hex[:8]}.mp4"
            video_path = os.path.join(OUTPUT_DIR, video_name)
            if dh.composite_audio_video(vf, tts_audio, video_path):
                # 确保文件完全写入磁盘 (防止浏览器请求到半写文件)
                import time as _time
                _time.sleep(0.05)
                info["video_url"] = f"/static/output/{video_name}"
            else:
                info["dh_error"] = "视频合成失败，仅提供音频"
    except Exception as e:
        logger.error("数字人视频生成异常: %s", e)
        info["dh_error"] = f"视频生成失败: {str(e)[:100]}"
    return info


# ================================================================
# 路由: 首页
# ================================================================
@app.route('/')
def index():
    """首页路由 — 渲染聊天 UI 页面。

    返回: 部署/templates/index.html 渲染后的 HTML 页面。
          页面提供完整的对话交互界面：文本聊天、🎤语音输入、📷图片上传、📹数字人视频。
    """
    return render_template('index.html')


# ================================================================
# POST /api/chat — 文本对话端点（主对话接口）
# ================================================================
@app.route('/api/chat', methods=['POST'])
def api_chat():
    """文本对话: 接收文本+图片→意图识别→工具路由→回复（可选TTS+视频）。"""
    q, img_b64, sid = "", None, "default"

    # 解析请求参数（支持JSON和Form两种模式）
    if request.is_json:
        data = request.get_json()
        if not data: return jsonify({"error": "请求体为空"}), 400
        q = data.get('question', '').strip(); img_b64 = data.get('image', None)
        sid = data.get('session', 'default')
    else:
        q = request.form.get('question', '').strip()
        sid = request.form.get('session', 'default')
        if 'image' in request.files:
            img_b64 = base64.b64encode(request.files['image'].read()).decode('utf-8')

    if not q and not img_b64: return jsonify({"error": "问题或图片不能都为空"}), 400
    if not q: q = "请处理这张图片"
    q = _clean_query(q)  # 清洗输入

    # Session初始化
    if sid not in sessions: sessions[sid] = []
    history = sessions[sid]
    logger.info("📩 [%s] %s (图=%s)", sid[:8], q[:80], "有" if img_b64 else "无")

    # 意图预判（无图片时，只调用一次DeepSeek）
    intent_tool = None
    if not img_b64:
        intent_tool, _, _ = recognize_intent(q, history)
        logger.info("🎯 意图预判: %s", intent_tool)

    # Demo数据库快速匹配（意图不明确时）
    demo_result = None
    if not intent_tool or intent_tool == 'unknown':
        demo_result = _try_match_demo_db(q)

    # 路由决策: Demo > 图片 > 工具
    if demo_result:
        result = demo_result
        # 确保 demo 结果有正确的 tool 标识（用于前端追踪）
        if not result.get("tool"):
            result["tool"] = "快速匹配"
    elif img_b64:
        from tool_text2image import tool_text2image
        r = tool_text2image(q, img_b64)
        result = {"answer": r['result'], "tool": r['tool'], "elapsed": 0}
        if r.get("images"): result["images"] = r["images"]
    else:
        result = process_query(q, history, pre_recognized_tool=intent_tool)

    # 更新对话历史
    history.append({"role": "user", "content": q})
    history.append({"role": "assistant", "content": result['answer'][:500]})
    if len(history) > config.MAX_HISTORY * 2:
        history = history[-config.MAX_HISTORY * 2:]
    sessions[sid] = history

    # 构建响应
    response = {"answer": result['answer'], "tool": result['tool'],
                "elapsed": result['elapsed'], "_v": 5}
    if result.get("images"): response["images"] = result["images"]

    # TTS语音合成+数字人视频（可选，前端传tts=true）
    tts_requested = ((request.is_json and data.get('tts')) or
                     (not request.is_json and request.form.get('tts')))
    if tts_requested:
        try:
            from tts_engine import get_tts_engine
            tts_e = get_tts_engine()
            # ★ 性能优化: TTS 文本上限 200 字（约 30-40 秒音频，避免 3 分钟+ 的视频渲染）
            tts_text = result['answer'][:200]
            if len(result['answer']) > 200:
                tts_text = tts_text.rsplit('。', 1)[0] + '。'  # 在最后一个句号处截断，保证完整句子
            tts_a = tts_e.synthesize_sync(tts_text)
            if len(tts_a) > 0:
                response["audio"] = tts_e.audio_to_base64_wav(tts_a)
                response["audio_format"] = "wav"
                response.update(_try_generate_video(result['answer'], tts_a, sid))
        except Exception as e:
            logger.warning("TTS附加失败: %s", e)
            response["tts_error"] = str(e)[:100]

    return jsonify(response)


# ================================================================
# GET /api/health — 健康检查
# ================================================================
@app.route('/api/health')
def health():
    """健康检查（含ASR/TTS/DH状态）。"""
    status = {"status": "ok", "agent": "ready"}
    try:
        from asr_engine import get_asr_engine
        asr = get_asr_engine()
        status["asr"] = {"engine": asr.engine_type, "loaded": asr.is_loaded}
    except Exception as e: status["asr"] = {"error": str(e)[:80]}
    try:
        from tts_engine import get_tts_engine
        tts = get_tts_engine()
        status["tts"] = {"available": tts.check_available(), "api": tts.api_url}
    except Exception as e: status["tts"] = {"error": str(e)[:80]}
    try:
        from digital_human import get_digital_human
        dh = get_digital_human()
        status["digital_human"] = {"loaded": dh.is_loaded, "has_avatar": dh.has_avatar}
    except Exception as e: status["digital_human"] = {"error": str(e)[:80]}
    return jsonify(status)


# ================================================================
# 主入口 — 注册子路由 + 启动服务
# ================================================================
def main():
    """启动Agent智能体Web服务。"""
    # 注册语音管线路由
    from voice_pipeline import register_voice_routes
    register_voice_routes(app, sessions, _video_frame_buffer, OUTPUT_DIR, BASE_DIR)
    # 注册头像/视频/指标路由
    from avatar_pipeline import register_avatar_routes
    register_avatar_routes(app, sessions, _video_frame_buffer, OUTPUT_DIR, BASE_DIR)

    logger.info("=" * 50)
    logger.info("🚀 Agent智能体已启动 (含语音管线v09)")
    logger.info("🌐 http://127.0.0.1:%d", PORT)
    logger.info("🎤 ASR: FunASR | 🔊 TTS: GPT-SoVITS+EdgeTTS | 🎬 DH: SadTalker")
    logger.info("📋 API: /api/chat | /api/voice/chat | /api/tts | /api/voice/clone | /api/avatar/upload")
    try:
        from digital_human import get_digital_human
        dh = get_digital_human()
        logger.info("🎬 数字人引擎: %s (头像=%s)", dh.engine_type, "已设置" if dh.has_avatar else "未设置")
    except Exception as e:
        logger.error("数字人引擎加载失败: %s", e)
    logger.info("=" * 50)
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)

if __name__ == "__main__":
    main()
