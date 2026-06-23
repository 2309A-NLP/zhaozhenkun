# -*- coding: utf-8 -*-
"""
main.py — 招股书RAG问答系统（命令行 + Flask Web双模式）
功能：python main.py → Web模式(端口5001)
      python main.py --cli → 命令行交互
工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务
"""

import json, time, os, sys, re, logging  # 标准库
import config  # 配置
from indexer import get_or_build_index  # 索引
from generator import generate_answer  # RAG
from retriever import extract_company_name  # 公司名

# ============================================================
# 日志配置
# ============================================================
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server.log")  # 日志文件
_fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S")  # 格式
_fh = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')  # 文件输出
_fh.setLevel(logging.DEBUG); _fh.setFormatter(_fmt)  # 设置
_ch = logging.StreamHandler(sys.stdout)  # 控制台
_ch.setLevel(logging.INFO); _ch.setFormatter(_fmt)  # 设置
_root = logging.getLogger(); _root.setLevel(logging.DEBUG)  # 根日志器
for h in list(_root.handlers): _root.removeHandler(h)  # 清空
_root.addHandler(_fh); _root.addHandler(_ch)  # 添加
logger = logging.getLogger("rag")  # 应用日志器
logging.getLogger("werkzeug").setLevel(logging.WARNING)  # 降噪
logging.getLogger("sklearn").setLevel(logging.WARNING)  # 降噪

PORT = 5001  # 端口（换5001避免旧进程残留冲突）


def sanitize_question(question):
    """清洗输入"""
    json_qs = re.findall(r'"question"\s*:\s*"([^"]*?)(?:"\s*[}\]]|\s*$)', question)  # 提取JSON
    if not json_qs: json_qs = re.findall(r'"question"\s*:\s*"(.+)', question)  # 宽松
    if json_qs: question = ' '.join(q.strip() for q in json_qs)  # 替换
    question = re.sub(r'[{}"\\]', ' ', question)  # 去JSON符号
    question = re.sub(r'\b(id|question|answer)\s*:\s*', '', question)  # 去字段名
    question = re.sub(r'^[\d,，\s]+', '', question)  # 去开头数字
    question = re.sub(r'^.*?北京八维信息集团\s*', '', question)  # 去前缀
    return re.sub(r'\s+', ' ', question).strip()[:500]  # 合并+截断


def load_index():
    """加载索引"""
    logger.info("加载招股书索引...")  # 进度
    t0 = time.time()  # 计时
    idx = get_or_build_index(config.PDF_TXT_DIR, config.INDEX_CACHE_DIR, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
    vec, cv, chunks, meta, cmap = idx  # 解包
    logger.info("索引: %d块 | %d词汇 | %d公司 | %.1fs", len(chunks), len(vec.vocabulary_), len(cmap), time.time()-t0)
    return vec, cv, chunks, meta, cmap  # 返回


def answer_question(question, vec, cv, chunks, meta, cmap):
    """单次问答"""
    clean_q = sanitize_question(question)  # 清洗
    logger.info("📩 问题: %s", clean_q[:100])  # 问题
    companies = extract_company_name(clean_q)  # 公司名
    logger.info("🔍 公司名: %s | 映射: %d条", companies, len(cmap))  # 诊断
    if companies and cmap:  # 有映射
        for name in companies:  # 遍历
            if name in cmap:  # 命中
                logger.info("🎯 映射命中: %s", name); break  # 日志
        else: logger.warning("⚠ 映射未命中! 公司名=%s", companies)  # 警告
    t0 = time.time()  # 计时
    answer = generate_answer(clean_q, vec, cv, chunks, meta, config.TOP_K, company_map=cmap)  # RAG
    logger.info("✅ 回答(%.1fs): %s", time.time()-t0, answer[:150])  # 答案
    return answer  # 返回


# ============================================================
# 命令行模式
# ============================================================
def cli_mode():
    """命令行交互"""
    logger.info("命令行模式启动")  # 日志
    vec, cv, chunks, meta, cmap = load_index()  # 索引
    print("\n" + "=" * 50)  # 分隔
    print("  招股书智能问答 - 命令行模式")  # 标题
    print("  输入问题回车，输入 quit 退出")  # 提示
    print("=" * 50 + "\n")  # 分隔
    while True:  # 循环
        try: q = input("👤 ").strip()  # 读取
        except (EOFError, KeyboardInterrupt): print("\n再见！"); break  # 退出
        if not q: continue  # 空
        if q.lower() in ('quit', 'exit', 'q'): print("再见！"); break  # 退出
        answer = answer_question(q, vec, cv, chunks, meta, cmap)  # 回答
        print(f"\n🤖 {answer}\n")  # 打印


# ============================================================
# Web模式
# ============================================================
def web_mode():
    """Flask Web"""
    from flask import Flask, request, jsonify, render_template  # Flask
    # 模板路径: 部署/templates/
    _tpl = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "部署", "templates")
    if not os.path.isdir(_tpl):
        _tpl = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "部署", "templates")
    app = Flask(__name__, template_folder=_tpl)  # 应用
    vec, cv, chunks, meta, cmap = load_index()  # 索引

    @app.after_request  # 禁止缓存
    def no_cache(response):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'  # HTTP/1.1
        response.headers['Pragma'] = 'no-cache'  # HTTP/1.0
        response.headers['Expires'] = '0'  # Proxies
        return response  # 返回

    @app.route('/')  # 首页
    def index():
        return render_template('index.html')  # HTML

    @app.route('/api/chat', methods=['POST'])  # API
    def api_chat():
        data = request.get_json()  # 解析
        if not data: return jsonify({"error": "请求体为空"}), 400  # 错误
        q = data.get('question', '').strip()  # 取问题
        if not q: return jsonify({"error": "问题为空"}), 400  # 错误
        logger.info("📩 API收到: %s", q[:100])  # 日志
        answer = answer_question(q, vec, cv, chunks, meta, cmap)  # 回答
        logger.info("📤 API返回: %s", answer[:80])  # 返回日志
        return jsonify({"answer": answer, "_v": 3})  # 带版本号

    @app.route('/api/health')  # 健康检查
    def health():
        return jsonify({"status": "ok", "chunks": len(chunks), "companies": len(cmap)})

    logger.info("🚀 http://127.0.0.1:%d (端口%d)", PORT, PORT)  # 提示
    app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)  # 启动


# ============================================================
# 批量模式（处理question.jsonl → answer_result.jsonl）
# ============================================================
def batch_mode(questions_path=None, output_dir=None, resume=True):
    """批量处理question.jsonl，输出answer_result.jsonl，支持断点续传"""
    if questions_path is None:
        questions_path = config.QUESTION_PATH
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(__file__))
    # 加载索引
    vec, cv, chunks, meta, cmap = load_index()
    # 加载题目
    if not os.path.exists(questions_path):
        alt = os.path.join(config.DATASET_DIR, "question.json")
        if os.path.exists(alt):
            questions_path = alt
        else:
            logger.error("题目文件不存在: %s", questions_path)
            logger.error("请下载: git clone https://www.modelscope.cn/datasets/BJQW14B/bs_challenge_financial_14b_dataset.git")
            return None
    qs = []
    with open(questions_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    qs.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    logger.info("加载 %d 道题目", len(qs))
    # 断点续传
    progress_file = os.path.join(output_dir, "batch_progress.txt")
    done = set()
    if resume and os.path.exists(progress_file):
        with open(progress_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        done.add(int(line))
                    except ValueError:
                        pass
        logger.info("断点续传: 已完成 %d 题，将跳过", len(done))
    # 输出文件
    output_file = os.path.join(output_dir, "answer_result.jsonl")
    total = len(qs)
    ok = len(done)
    fail = 0
    t0 = time.time()
    for i, q in enumerate(qs):
        qid = q.get("id", i)
        if qid in done:
            continue
        question = q.get("question", "")
        logger.info("[%d/%d] ID=%s: %s", i + 1, total, qid, question[:80])
        try:
            t1 = time.time()
            answer = answer_question(question, vec, cv, chunks, meta, cmap)
            elapsed = time.time() - t1
        except Exception as e:
            logger.error("✗ ID=%s 异常: %s", qid, str(e))
            answer = f"（处理出错: {e}）"
            elapsed = 0
        record = {"id": qid, "question": question, "answer": answer, "elapsed": round(elapsed, 2)}
        with open(output_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        done.add(qid)
        with open(progress_file, "a", encoding="utf-8") as f:
            f.write(f"{qid}\n")
        if answer and not answer.startswith("（处理出错"):
            ok += 1
        else:
            fail += 1
        logger.info("  ✓ (%.1fs) → %s", elapsed, answer[:100] if answer else "空")
        # 进度报告
        processed = ok + fail
        if processed > 0 and processed % 10 == 0:
            elapsed = time.time() - t0
            rate = processed / elapsed if elapsed > 0 else 0
            eta = (total - len(done)) / rate / 60 if rate > 0 else 0
            logger.info("--- 进度: %d/%d | 速率: %.1f题/分 | 预计剩余: %.0f分钟 ---",
                       processed, total, rate * 60, eta)
    total_elapsed = time.time() - t0
    logger.info("=" * 50)
    logger.info("批量完成: 成功%d | 跳过%d | 失败%d | 共%d题 | %.1f分钟",
               ok, len(done) - ok - fail + ok, fail, total, total_elapsed / 60)
    logger.info("输出: %s", output_file)
    return {"total": total, "ok": ok, "failed": fail, "elapsed": round(total_elapsed, 2), "output": output_file}


# ============================================================
# 入口
# ============================================================
if __name__ == "__main__":
    if "--batch" in sys.argv:
        batch_mode()
    elif "--cli" in sys.argv:
        cli_mode()
    else:
        web_mode()
