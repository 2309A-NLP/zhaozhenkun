"""
bottleneck_analyzer.py - RAG工单13 瓶颈分析模块
需求: 分析RAG各阶段耗时数据，定位性能瓶颈原因 — 工单"识别缓慢之处的工具和技术"部分
功能: 1.耗时占比分析 2.瓶颈判定(占比>30%或平均>5s) 3.各阶段优化建议生成
"""
import logging
from 研发.timer import Timer  # 需求：读取计时器的统计数据

logger = logging.getLogger(__name__)


def analyze_bottlenecks(timer):
    """分析RAG各阶段耗时，标记瓶颈并生成建议——需求：找出导致响应慢的原因"""
    summary = timer.get_summary()
    if not summary:
        return {"error": "无计时数据", "bottlenecks": [], "suggestions": []}
    total_time = timer.get_total_time()
    if total_time == 0:
        return {"error": "总耗时为0", "bottlenecks": [], "suggestions": []}

    sorted_stages = sorted(summary.items(), key=lambda x: x[1]["total"], reverse=True)
    bottlenecks, suggestions = [], []

    for name, stats in sorted_stages:
        pct = stats["total"] / total_time * 100      # 需求：计算耗时占比
        avg = stats["avg"]
        is_bottleneck = pct > 30 or avg > 5.0        # 需求：阈值判定（>30%或>5s=瓶颈）
        suggestion = _get_suggestion(name, stats, pct)
        stage_info = {"stage": name, "total_seconds": stats["total"],
                      "avg_seconds": avg, "call_count": stats["count"],
                      "percentage": round(pct, 1), "is_bottleneck": is_bottleneck,
                      "suggestion": suggestion}
        if is_bottleneck:
            bottlenecks.append(stage_info)

    # 需求：生成汇总结论（方便报告使用）
    bc = len(bottlenecks)
    if bc == 0:
        conclusion = "✅ 无明显瓶颈"
    elif bc == 1:
        conclusion = f"⚠️ 发现1个瓶颈:{bottlenecks[0]['stage']}"
    else:
        conclusion = f"🔴 发现{bc}个瓶颈，首要:{bottlenecks[0]['stage']}"
    return {"total_time_seconds": round(total_time, 3), "stages": sorted_stages,
            "bottlenecks": bottlenecks, "conclusion": conclusion,
            "suggestions": [b["suggestion"] for b in bottlenecks]}


def _get_suggestion(name, stats, pct):
    """根据阶段名生成针对性优化建议——需求：指导如何优化每个瓶颈"""
    avg = stats["avg"]
    suggestions = {
        "pdf_parse": "PDF解析是离线步骤。如重复解析，建议缓存结果。",
        "chunking": "分块是离线步骤。可调整chunk_size平衡精度和速度。",
        "embedding": f"嵌入耗时{avg:.2f}s/次({pct}%)。建议：①FP16 ②增batch_size ③ONNX加速",
        "query_enhancement": f"查询增强耗时{avg:.2f}s。建议：纯文本处理，性能良好。",
        "query_embedding": f"查询嵌入耗时{avg:.2f}s。建议：①模型复用（已实现）②FP16 ③缓存相同问题",
        "vector_search": f"向量检索耗时{avg:.2f}s。建议：①FAISS IVF ②减小top_k ③GPU加速",
        "context_assembly": f"上下文组装{avg:.2f}s，纯文本拼接性能良好。",
        "llm_generation": f"LLM生成耗时{avg:.2f}s({pct}%)。建议：①减小max_tokens ②流式输出 ③换更小模型",
        "post_processing": f"后处理耗时{avg:.2f}s。建议：纯文本处理，性能良好。"
    }
    return suggestions.get(name, f"{name}阶段耗时{avg:.2f}s，建议进一步分析。")
