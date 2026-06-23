"""
app.py - RAG工单6 Flask Web应用
需求: 交互友好性+多轮对话 — Web界面，三种检索模式+权重配置+对话记忆
功能: Flask路由(/ /ask /chat /compare /status)，延迟加载模型，多轮对话记忆
"""
import logging, json, os, time

from config import OUTPUT_DIR, PROJECT_DIR, WO_ID

logging.basicConfig(format="%(asctime)s | %(levelname)-7s | %(message)s", level=logging.INFO)
logger = logging.getLogger("app")

_app, _searcher = None, None
_embedder = _milvus = _fulltext = _reranker = None


def get_app():
    global _app
    if _app:
        return _app
    from flask import Flask, request, jsonify, render_template
    from short_term_memory import memory
    app = Flask(__name__, template_folder=str(PROJECT_DIR / "templates"))

    @app.route("/")
    def index():
        return render_template("index.html", work_order_id=WO_ID)

    @app.route("/ask", methods=["POST"])
    def ask():
        """单次问答接口（无记忆）"""
        data = request.get_json(force=True)
        question = data.get("question", "").strip()
        if not question:
            return jsonify({"error": "请输入问题"}), 400
        mode = data.get("mode", "hybrid")
        try:
            searcher = get_searcher()
            search_result = searcher.search(question, mode=mode,
                                            rerank_method=data.get("rerank_method", "llm"),
                                            weight_vector=float(data.get("weight_vector", 0.5)),
                                            weight_fulltext=float(data.get("weight_fulltext", 0.5)))
            if search_result["results"]:
                from qa_generator import generate_answer
                answer = generate_answer(question, search_result["results"])
            else:
                answer = {"question": question, "answer": "未找到相关内容",
                          "confidence": "low", "sources": [], "response_time": 0}
            answer["mode"] = mode
            answer["rerank_method"] = data.get("rerank_method", "llm")
            answer["result_count"] = len(search_result["results"])
            return jsonify(answer)
        except Exception as e:
            import traceback
            logger.error(f"处理失败: {e}\n{traceback.format_exc()}")
            return jsonify({"question": question, "answer": f"处理出错: {str(e)}",
                            "confidence": "low", "sources": [], "response_time": 0}), 500

    @app.route("/chat", methods=["POST"])
    def chat():
        """多轮对话接口（带session记忆）"""
        data = request.get_json(force=True)
        question = data.get("question", "").strip()
        session_id = data.get("session_id", "default")
        if not question:
            return jsonify({"error": "请输入问题"}), 400
        try:
            searcher = get_searcher()
            mode = data.get("mode", "hybrid")
            search_result = searcher.search(question, mode=mode)
            if not search_result["results"]:
                answer = {"question": question, "answer": "未找到相关内容",
                          "confidence": "low", "sources": [], "response_time": 0}
            else:
                history = memory.format_for_prompt(session_id, max_rounds=3)
                memory.add_message(session_id, "user", question)
                from qa_generator import generate_answer
                answer = generate_answer(question, search_result["results"][:3], history=history)
                memory.add_message(session_id, "assistant", answer["answer"][:200])
            answer["mode"] = mode
            answer["session_id"] = session_id
            answer["history_count"] = len(memory.get_history(session_id)) // 2
            answer["result_count"] = len(search_result["results"])
            return jsonify(answer)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/compare", methods=["POST"])
    def compare():
        """对比三种检索模式的结果"""
        data = request.get_json(force=True)
        question = data.get("question", "").strip()
        if not question:
            return jsonify({"error": "请输入问题"}), 400
        try:
            searcher = get_searcher()
            results = {"question": question,
                       "vector": searcher.vector_search(question),
                       "fulltext": searcher.fulltext_search(question),
                       "hybrid": searcher.hybrid_search(question)}
            for m in ["vector", "fulltext", "hybrid"]:
                for r in results[m]["results"]:
                    r["content"] = r["content"][:200]
            return jsonify(results)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/status")
    def status():
        return jsonify({"status": "running", "work_order": WO_ID, "model_loaded": _searcher is not None})

    @app.route("/clear", methods=["POST"])
    def clear_session():
        """清空对话历史"""
        data = request.get_json(force=True)
        from short_term_memory import memory
        memory.clear(data.get("session_id", "default"))
        return jsonify({"status": "cleared"})

    _app = app
    return app


def get_searcher():
    """获取检索器（延迟加载模型）"""
    global _searcher, _embedder, _milvus, _fulltext, _reranker
    if _searcher:
        return _searcher
    logger.info("首次请求，加载模型...")
    start = time.time()
    from embedder import BgeM3Embedder
    from milvus_handler import MilvusHandler
    from fulltext_engine import FullTextEngine
    from reranker import Reranker
    from hybrid_search import HybridSearch
    _embedder = BgeM3Embedder()
    _embedder.load()
    _milvus = MilvusHandler()
    _milvus.connect()
    _milvus.create_collection()
    _fulltext = FullTextEngine()
    fp = os.path.join(str(OUTPUT_DIR), "chunks_full.json")
    if os.path.exists(fp):
        _fulltext.build(json.load(open(fp, encoding="utf-8")))
    _reranker = Reranker()
    _searcher = HybridSearch(_embedder, _milvus, _fulltext, _reranker)
    logger.info(f"模型加载完成! {time.time()-start:.1f}秒")
    return _searcher


if __name__ == "__main__":
    app = get_app()
    app.run(host="0.0.0.0", port=5000, debug=False)
