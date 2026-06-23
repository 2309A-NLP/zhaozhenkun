"""
app.py - RAG工单13 Web对话服务模块
需求: 提供Web交互界面，每个会话用户输入query后返回检索结果 — 工单"验收标准"要求
功能: 1.Flask Web服务器(延迟初始化) 2./ask问答接口 3.会话记忆 4.5阶段计时显示 5.系统监控 6.监控API
"""
import logging
import os, json                                          # 文件/JSON操作
from flask import Flask, request, jsonify, render_template  # 需求：Web框架
from 研发.timer import Timer                                  # 需求：各阶段计时
from 研发.logger import RagLogger                             # 需求：结构化日志+请求ID追踪
from 研发.rag_pipeline import load_or_build_index, rag_query  # 需求：RAG流水线(含查询增强+后处理)
from 优化.bottleneck_analyzer import analyze_bottlenecks      # 需求：瓶颈分析
from 优化.system_monitor import get_monitor, save_monitoring_snapshot  # 需求：系统资源监控
import 研发.config as config                                   # 需求：测试问题等配置

app = Flask(__name__, template_folder="部署/templates")       # 需求：创建Flask应用
app.config['JSON_AS_ASCII'] = False                      # 支持中文JSON输出

# 需求：全局系统监控器
_sys_monitor = get_monitor()

# 需求：延迟初始化（避免Flask启动时卡住）
_chunks = None     # 文本块列表
_vectors = None    # 向量矩阵
_chunk_meta = None # 向量元数据
_index_timer = Timer()  # 索引构建计时

def _init_index():
    """延迟加载索引——需求：首次请求时初始化，不阻塞Flask启动"""
    global _chunks, _vectors, _chunk_meta
    if _chunks is None:
        print("🔨 首次请求，加载索引...")
        _chunks, _vectors, _chunk_meta = load_or_build_index(_index_timer)
        print(f"  ✅ 加载完成: {len(_chunks)}块")


@app.route("/")
def index():
    """需求：聊天页面入口"""
    return render_template("index.html")


@app.route("/ask", methods=["POST"])
def ask():
    """需求：问答API接口，返回答案+各阶段耗时"""
    data = request.get_json(force=True)                 # 解析JSON请求体
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "请输入问题"}), 400

    _init_index()                                       # 需求：确保索引已加载

    # 需求：创建结构化日志器（带请求ID追踪）
    rag_log = RagLogger()
    rag_log.log_stage_start("total_query")

    q_timer = Timer()
    result = rag_query(question, _chunks, _vectors, _chunk_meta, q_timer)
    stages = result["stage_timings"]                    # 需求：5阶段原始耗时

    # 需求：记录业务指标（检索文档数、上下文长度、置信度）
    rag_log.log_metric("context_preview", result.get("context", "")[:100])
    rag_log.log_metric("answer_length", len(result.get("answer", "")))
    rag_log.log_metric("top_pages", result.get("top_pages", []))
    post_proc = result.get("post_processing", {})
    rag_log.log_metric("confidence", post_proc.get("confidence", {}).get("level", "N/A"))

    # 需求：记录到系统监控器
    total_time = q_timer.get_total_time()
    _sys_monitor.record_request(success=True, latency_seconds=total_time)

    # 需求：格式化为前端可读的耗时数据
    stage_times = {}
    q_summary = q_timer.get_summary()
    for name, s in q_summary.items():
        stage_times[name] = {
            "seconds": round(s["total"], 3),
            "percent": round(s["total"] / max(total_time, 0.001) * 100, 1)
        }

    # 需求：输出结构化日志（请求ID+5阶段耗时+指标）
    rag_log.print_summary()

    return jsonify({
        "answer": result["answer"],
        "context": result["context"],
        "stages": stage_times,                          # 5阶段耗时（前端展示用）
        "total_time": round(total_time, 3),              # 总耗时
        "request_id": rag_log.request_id,               # 需求：请求ID追踪
        "confidence": post_proc.get("confidence", {}),  # 需求：置信度评估
        "pages": result.get("top_pages", [])            # 需求：检索到的页码
    })


@app.route("/benchmark", methods=["POST"])
def run_benchmark():
    """需求：运行基准测试（10道题批量跑），返回优化前后对比"""
    _init_index()

    from 测试.benchmark import run_baseline, run_optimized, compare
    print("📊 运行基准测试...")
    baseline = run_baseline(config.TEST_QUESTIONS)
    optimized = run_optimized(config.TEST_QUESTIONS)
    comparison = compare(baseline, optimized)

    # 分析瓶颈
    btl_timer = Timer()
    for stage_name, stats in baseline.get("bottleneck_analysis", {}).get("stages", []):
        for _ in range(stats["count"]):
            btl_timer._records[stage_name].append(stats["avg"])
    analysis = analyze_bottlenecks(btl_timer)

    return jsonify({
        "comparison": comparison,
        "analysis": analysis,
        "baseline_per_question": [
            {"q": r["question"][:30], "time": r["total_time"]}
            for r in baseline["results"]
        ],
        "optimized_per_question": [
            {"q": r["question"][:30], "time": r["total_time"]}
            for r in optimized["results"]
        ]
    })


@app.route("/monitor", methods=["GET"])
def monitor_snapshot():
    """需求：系统监控API — 返回CPU/内存/GPU/延迟/吞吐量/告警"""
    snapshot = _sys_monitor.snapshot()
    return jsonify(snapshot)

if __name__ == "__main__":
    """需求：直接启动Web服务（端口5008，绑定0.0.0.0适配WSL+Windows）"""
    print("🚀 RAG对话服务启动: http://localhost:5008")
    print("📊 监控API: http://localhost:5008/monitor")
    app.run(host="0.0.0.0", port=5008, debug=False)
