"""
app.py - RAG工单8 Flask Web展示模块（延迟初始化）
工单编号: 人工智能NLP-RAG-基于Graph RAG 实现金融问答
功能: 提供Web界面展示GraphRAG问答结果和知识图谱可视化，
      支持中英文双语问答切换
"""

import logging, json, os, sys

# Flask延迟初始化
_flask_app = None

logging.basicConfig(
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S", level=logging.INFO)
logger = logging.getLogger("app")


def get_app():
    """延迟初始化Flask应用"""
    global _flask_app
    if _flask_app is not None:
        return _flask_app

    from flask import Flask, request, jsonify, render_template
    from flask_cors import CORS

    app = Flask(__name__, template_folder="templates")
    CORS(app)
    _flask_app = app

    # 全局状态：问答结果和图谱数据
    _state = {
        "qa_pairs": [],
        "graph_data": {"nodes": [], "edges": []},
        "summary": {},
    }

    @app.route("/")
    def index():
        """首页：问答界面"""
        return render_template("index.html")

    @app.route("/api/qa_results")
    def get_qa_results():
        """返回问答结果列表"""
        return jsonify(_state.get("qa_pairs", []))

    @app.route("/api/graph_data")
    def get_graph_data():
        """返回知识图谱数据（用于前端可视化）"""
        return jsonify(_state.get("graph_data", {"nodes": [], "edges": []}))

    @app.route("/api/summary")
    def get_summary():
        """返回评估摘要"""
        return jsonify(_state.get("summary", {}))

    @app.route("/api/question", methods=["POST"])
    def ask_question():
        """
        单问题问答API（供前端交互使用）
        请求体: {"question": "问题文本", "use_graph": true/false}
        返回: {"answer": "...", "sources": [...], "response_time": 0.0}
        """
        data = request.get_json(force=True)
        question = data.get("question", "")
        use_graph = data.get("use_graph", True)
        lang = data.get("lang", "zh")

        if not question:
            return jsonify({"error": "请输入问题"}), 400

        try:
            from embedder import BgeM3Embedder
            from graph_retriever import GraphRetriever
            from qa_generator import QAGenerator
            import time

            t0 = time.time()
            embedder = BgeM3Embedder()
            q_vec = embedder.encode_query(question)["dense_vecs"][0]

            # 尝试加载已保存的图谱
            graph_data_path = os.path.join(
                os.path.dirname(__file__), "output", "knowledge_graph.json")
            graph_builder = None
            from entity_graph_builder import GraphBuilder
            if os.path.exists(graph_data_path):
                import networkx as nx
                from collections import defaultdict
                graph_builder = GraphBuilder()
                graph_builder.graph = nx.Graph()
                with open(graph_data_path, "r", encoding="utf-8") as f:
                    gdata = json.load(f)
                for n in gdata.get("nodes", []):
                    graph_builder.graph.add_node(
                        n["name"], type=n.get("type", ""), source_pdf=n.get("source_pdf", ""))
                for e in gdata.get("edges", []):
                    graph_builder.graph.add_edge(
                        e["source"], e["target"], relation=e.get("relation", "相关"))
                graph_builder.entity_to_chunks = defaultdict(
                    set, {k: set(v) for k, v in gdata.get("entity_to_chunks", {}).items()})
                graph_builder._built = True

            retriever = GraphRetriever(graph_builder)
            # 加载chunks
            chunks_path = os.path.join(
                os.path.dirname(__file__), "output", "chunks_data.json")
            if os.path.exists(chunks_path):
                with open(chunks_path, "r", encoding="utf-8") as f:
                    retriever.set_chunks(json.load(f))

            chunks = retriever.retrieve(q_vec.tolist(), question, use_graph=use_graph)
            qa = QAGenerator()
            result = qa.generate(question, chunks, use_graph=use_graph, lang=lang)
            result["response_time"] = round(time.time() - t0, 2)
            retriever.close()
            return jsonify(result)
        except Exception as e:
            logger.error(f"问答失败: {e}")
            return jsonify({"error": str(e), "answer": f"处理失败: {e}"}), 500

    @app.route("/api/graph_viz")
    def graph_viz():
        """返回图谱数据的可视化版本（包含颜色分组）"""
        gd = _state.get("graph_data", {"nodes": [], "edges": []})
        type_colors = {
            "公司": "#4CAF50", "人物": "#2196F3", "产品": "#FF9800",
            "指标": "#9C27B0", "事件": "#F44336", "时间": "#00BCD4",
        }
        for node in gd.get("nodes", []):
            node["color"] = type_colors.get(node.get("type", ""), "#999")
        return jsonify(gd)

    # 从文件加载数据
    output_dir = os.path.join(os.path.dirname(__file__), "output")
    qa_path = os.path.join(output_dir, "qa_results.json")
    graph_path = os.path.join(output_dir, "knowledge_graph.json")
    summary_path = os.path.join(output_dir, "evaluation_summary.json")

    if os.path.exists(qa_path):
        with open(qa_path, "r", encoding="utf-8") as f:
            _state["qa_pairs"] = json.load(f)
    if os.path.exists(graph_path):
        with open(graph_path, "r", encoding="utf-8") as f:
            _state["graph_data"] = json.load(f)
    if os.path.exists(summary_path):
        with open(summary_path, "r", encoding="utf-8") as f:
            _state["summary"] = json.load(f)

    return app


if __name__ == "__main__":
    """启动Web服务"""
    app = get_app()
    logger.info("启动Web服务 http://0.0.0.0:5008")
    app.run(host="0.0.0.0", port=5008, debug=False)
