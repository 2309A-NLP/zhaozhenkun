"""
Web 对话模块（部署层）
功能：Flask Web 对话界面，支持 RAG / LightRAG 双模式实时问答
完成：延迟加载模型和缓存（启动秒开）、多线程安全、RAG/LightRAG 一键切换
"""
import logging

logger = logging.getLogger(__name__)
logger.info("Web服务启动")
import sys, os
# 将项目根目录加入路径，支持从任意子目录导入其他模块
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _sub in ["设计", "研发", "测试", "部署", "优化"]:
    _p = os.path.join(_root, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import os, json, threading          # 文件操作 / JSON解析 / 线程安全
import numpy as np                  # 向量运算
from flask import Flask, request, jsonify, render_template  # Flask Web 框架

import config                       # 全局配置
from retriever import rag_retrieve, lightrag_retrieve  # 双模式检索
from qa_generator import build_context, generate_answer  # 上下文拼接 + 问答生成
from graph_builder import load_graph  # 图谱加载

# ======================== Flask 应用初始化 ========================

app = Flask(__name__, template_folder="templates")  # 模板目录在部署/templates/

# ======================== 全局缓存（延迟加载 + 线程安全） ========================

_loaded = False               # 缓存是否已加载标记
_load_lock = threading.Lock() # 线程锁：确保大规模模型只加载一次
_cache = {}                   # 全局缓存字典：存放 chunks/vectors/meta/graph/model


def _lazy_load():
    """
    延迟加载所有缓存数据（chunks、向量、图谱等）
    仅在首次 API 请求时触发加载，确保 Flask 启动秒开
    使用双重检查锁定模式保证多线程安全
    """
    global _loaded, _cache
    if _loaded:
        return  # 快速路径：已加载直接返回
    with _load_lock:  # 获取线程锁
        if _loaded:
            return  # 双重检查：避免并发重复加载
        print("🔄 延迟加载缓存数据...")

        # 1. 加载文本块（JSON 格式）
        if os.path.exists(config.CHUNKS_CACHE):
            with open(config.CHUNKS_CACHE, "r", encoding="utf-8") as f:
                _cache["chunks"] = json.load(f)
            print(f"  ✅ {len(_cache['chunks'])} chunks")
        else:
            raise FileNotFoundError(f"缺少缓存: {config.CHUNKS_CACHE}，请先运行 run.py --rebuild")

        # 2. 加载 BGE-M3 向量（numpy 数组）
        if os.path.exists(config.VECTORS_CACHE):
            _cache["vectors"] = np.load(config.VECTORS_CACHE)
        else:
            raise FileNotFoundError(f"缺少向量: {config.VECTORS_CACHE}")
        # 加载向量元数据（chunk_id / source_pdf / page_num）
        if os.path.exists(config.EMBEDDINGS_META):
            with open(config.EMBEDDINGS_META, "r", encoding="utf-8") as f:
                _cache["chunk_meta"] = json.load(f)
        print(f"  ✅ 向量: {_cache['vectors'].shape}")

        # 3. 加载知识图谱（NetworkX 有向图）
        graph = load_graph(config.GRAPH_CACHE)
        _cache["graph"] = graph
        if graph:
            print(f"  ✅ 图谱: {graph.number_of_nodes()} 节点, {graph.number_of_edges()} 边")

        # 4. BGE-M3 嵌入模型设为 None（问答时按需加载，避免启动耗时过长）
        _cache["bge_model"] = None

        _loaded = True
        print("✅ 缓存加载完成")


def _get_bge_model():
    """
    获取 BGE-M3 嵌入模型实例（按需加载，进程级单例）
    首次调用时加载模型到 GPU，后续复用
    返回：SentenceTransformer 实例
    """
    if _cache.get("bge_model") is None:
        from sentence_transformers import SentenceTransformer
        import torch


        print("📦 延迟加载 BGE-M3 模型...")
        model = SentenceTransformer(
            config.BGE_MODEL_PATH,     # 本地 BGE-M3 路径
            device="cuda",             # GPU 加速
            trust_remote_code=True     # 允许自定义模型代码
        )
        if torch.cuda.is_available():
            model.half()               # FP16 半精度，显存使用减半
            print(f"  ✅ FP16, GPU: {torch.cuda.get_device_name(0)}")
        _cache["bge_model"] = model    # 缓存进程级单例
    return _cache["bge_model"]


def _encode_query(query: str) -> np.ndarray:
    """
    将用户问题编码为归一化向量
    参数：query - 用户输入的问题文本
    返回：(hidden_dim,) 的 float32 numpy 数组
    """
    model = _get_bge_model()
    vec = model.encode(query, normalize_embeddings=True)  # 归一化后可直接点积算余弦相似度
    return np.array(vec, dtype=np.float32)


# ======================== API 路由 ========================

@app.route("/")
def index():
    """首页路由：渲染对话界面 HTML"""
    return render_template("dialogue.html")


@app.route("/api/status")
def api_status():
    """
    系统状态接口（页面加载时自动调用）
    返回缓存统计信息：chunks 数量 / 实体数 / 关系数 / 图谱节点边数
    """
    try:
        _lazy_load()  # 触发延迟加载
        chunks = _cache.get("chunks", [])
        graph = _cache.get("graph")
        # 读取实体提取结果统计
        merged_path = os.path.join(config.CACHE_DIR, "entity_extractions.json")
        merged = {}
        if os.path.exists(merged_path):
            with open(merged_path, "r", encoding="utf-8") as f:
                merged = json.load(f).get("merged", {})
        return jsonify({
            "ready": True,
            "stats": {
                "chunks": len(chunks),
                "entities": len(merged.get("entities", [])),
                "relations": len(merged.get("relations", [])),
                "graph_nodes": graph.number_of_nodes() if graph else 0,
                "graph_edges": graph.number_of_edges() if graph else 0,
            }
        })
    except Exception as e:
        return jsonify({"ready": False, "error": str(e)})


@app.route("/api/ask", methods=["POST"])
def api_ask():
    """
    核心问答接口
    请求体 JSON: {"question": "问题文本", "mode": "RAG" | "LightRAG"}
    返回 JSON: {"answer": str, "context": [...来源信息...], "mode": str, "question": str}
    """
    # ── 1. 延迟加载所有缓存 ──
    try:
        _lazy_load()
    except Exception as e:
        return jsonify({"error": f"缓存加载失败: {e}"}), 500

    # ── 2. 解析请求参数 ──
    data = request.get_json()
    question = data.get("question", "").strip()  # 用户问题
    mode = data.get("mode", "RAG")               # 检索模式（默认 RAG）
    if not question:
        return jsonify({"error": "问题不能为空"}), 400  # 空问题直接拒绝

    try:
        # ── 3. 问题编码为向量 ──
        q_vec = _encode_query(question)

        # ── 4. 双模式检索 ──
        chunks = _cache["chunks"]           # 文本块列表
        vectors = _cache["vectors"]         # 向量矩阵 (N, dim)
        chunk_meta = _cache["chunk_meta"]   # 向量元数据
        graph = _cache.get("graph")         # 知识图谱

        if mode == "RAG":
            results = rag_retrieve(q_vec, vectors, chunk_meta)  # 纯向量检索
        else:
            results = lightrag_retrieve(      # 向量 + 图谱增强检索
                q_vec, vectors, chunk_meta, chunks, graph, question
            )

        # ── 5. 补充检索结果的 text 字段（retriever 不直接返回 text） ──
        for r in results:
            if not r.get("text"):
                for c in chunks:
                    if c["chunk_id"] == r["chunk_id"]:
                        r["text"] = c["text"]  # 从 chunks 中匹配文本
                        break

        # ── 6. 拼接上下文 → LLM 生成回答 ──
        context_text = build_context(results)  # 格式化的上下文字符串
        answer_obj = generate_answer(question, context_text, mode=mode)
        answer = answer_obj.get("answer", "")

        # ── 7. 构造返回结果 ──
        context_list = []  # 前端展示用的检索来源信息
        for r in results[:8]:  # 最多展示前 8 条，避免前端过长
            context_list.append({
                "source_pdf": r.get("source_pdf", ""),
                "page_num": r.get("page_num", 0),
                "score": r.get("score", 0),
                "source": r.get("source", "vector"),     # 标记来源：vector/graph
                "text": (r.get("text", "") or "")[:300]  # 截取前300字符展示
            })
        return jsonify({
            "answer": answer,
            "context": context_list,
            "mode": mode,
            "question": question
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ======================== Web 服务启动入口 ========================

def run_server(host="0.0.0.0", port=5000, debug=False):
    """
    启动 Flask Web 服务器
    参数：
        host:  监听地址（默认 0.0.0.0 允许局域网访问）
        port:  监听端口（默认 5000）
        debug: 是否调试模式（生产环境应关闭）
    """
    # 启动前校验必要缓存文件存在（但不加载模型，保持秒开）
    checks = [config.CHUNKS_CACHE, config.VECTORS_CACHE,
              config.EMBEDDINGS_META, config.GRAPH_CACHE]
    missing = [p for p in checks if not os.path.exists(p)]
    if missing:
        print("❌ 缺少缓存文件，请先运行 run.py --rebuild 初始化数据")
        for m in missing:
            print(f"   {m}")
        return  # 不启动服务器

    print(f"🌐 LightRAG 对话系统已启动")
    print(f"   地址: http://{host}:{port}")
    print(f"   首次问答会自动加载 BGE-M3 模型（约10-30秒）")
    app.run(host=host, port=port, debug=debug, threaded=True)  # threaded=True 支持并发


if __name__ == "__main__":
    """直接运行 web_app.py 时启动服务器"""
    run_server(debug=True)
