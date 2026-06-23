"""
report_generator.py - RAG工单13 报告生成模块
需求: 将基准测试和瓶颈分析生成为Markdown格式的优化报告 — 工单"产出物"(出现瓶颈原因+优化方案+对比)
功能: 1.系统架构图 2.基线性能数据表 3.瓶颈分析 4.优化方案表 5.前后对比数据 6.结论建议
"""
import logging
import os                       # 需求：文件路径操作
from datetime import datetime   # 需求：报告时间戳
import 研发.config as config              # 需求：输出路径、分块参数

logger = logging.getLogger(__name__)


def generate_report(baseline, optimized, comparison, bottleneck_analysis, output_path):
    """生成完整的性能优化Markdown报告——需求：产出物要求的所有内容"""
    sections = []

    # 标题区——需求：报告元数据
    sections.append(f"# RAG性能瓶颈识别与优化报告\n")
    sections.append(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    sections.append(f"**测试数据**: {config.PDF_PATH.split('/')[-1]}")
    sections.append(f"\n**测试问题数**: {baseline['question_count']}个\n")
    sections.append(f"**BGE-M3参数**: batch_size={config.ENCODE_KWARGS['batch_size']}, "
                    f"max_length={config.ENCODE_KWARGS['max_length']}\n")
    sections.append("---\n")

    # 1. 系统架构——需求：描述RAG流水线的5个阶段
    sections.append("## 1.RAG系统架构\n")
    sections.append("```\n用户Query → [查询处理与增强] → [查询嵌入] → [向量检索] → [上下文组装] → [LLM生成] → [后处理与响应格式化] → 回答\n```\n")
    sections.append("- **查询处理与增强**: Query清洗/关键词提取/短问题扩展\n")
    sections.append("- **查询嵌入**: BGE-M3编码为1024维向量（FP16半精度）\n")
    sections.append("- **向量检索**: 余弦相似度暴力搜索，Top-5\n")
    sections.append("- **上下文组装**: 检索结果拼接为提示词\n")
    sections.append("- **LLM生成**: 小米MiMo(mimo-v2.5-pro)生成回答\n")
    sections.append("- **后处理与响应格式化**: 格式清洗/参考来源标注/置信度评估\n")

    # 2. 基线性能——需求：展示优化前的各阶段耗时分布
    sections.append("## 2.基线性能数据\n")
    sections.append(f"**总耗时**: {baseline['total_time']:.2f}s\n")
    sections.append(f"**平均每查询**: {baseline['avg_time_per_query']:.2f}s\n\n")
    sections.append("### 各阶段耗时分布\n\n")
    sections.append("| 阶段 | 平均耗时 | 调用次数 | 占比 |\n")
    sections.append("|------|---------|---------|------|\n")
    q_timings = baseline.get("bottleneck_analysis", {}).get("stages", [])
    total = baseline["total_time"]
    # 从bottleneck_analysis中提取阶段数据（已有排序）
    for name, stats in q_timings:
        pct = (stats["total"] / total * 100) if total > 0 else 0
        sections.append(f"| {name} | {stats['avg']:.2f}s | {stats['count']} | {pct:.1f}% |\n")

    # 3. 瓶颈分析——需求：识别出的瓶颈及优化建议
    sections.append("\n## 3.瓶颈分析\n\n")
    sections.append(f"**结论**: {bottleneck_analysis.get('conclusion', 'N/A')}\n\n")
    if bottleneck_analysis.get("bottlenecks"):
        sections.append("### 识别到的瓶颈\n\n")
        for b in bottleneck_analysis["bottlenecks"]:
            sev = "🔴" if b["percentage"] > 50 else "⚠️"
            sections.append(f"- {sev} **{b['stage']}**: 占比{b['percentage']}%，平均{b['avg_seconds']:.2f}s\n")
            sections.append(f"  - 建议: {b['suggestion']}\n")

    # 4. 优化方案——需求：工单"优化方案"表格
    sections.append("\n## 4.优化方案\n\n")
    sections.append("| 优化项 | 说明 | 预期效果 |\n")
    sections.append("|-------|------|---------|\n")
    sections.append("| 查询嵌入缓存 | 相同问题缓存嵌入向量，避免重复编码 | 减少耗时50%+ |\n")
    sections.append("| 预归一化索引 | 提前归一化向量，减少检索计算量 | 减少检索耗时30%+ |\n")
    sections.append("| 模型单次加载 | BGE-M3只加载一次，所有查询共享 | 消除重复加载开销 |\n")
    sections.append("| LLM参数调优 | 根据瓶颈分析调整max_tokens等 | 减少LLM生成耗时 |\n")

    # 5. 优化前后对比——需求：验收标准——3秒阈值是否达标
    sections.append("\n## 5.优化前后性能对比\n\n")
    bt = comparison["baseline_avg_seconds"]
    ot = comparison["optimized_avg_seconds"]
    imp = comparison["improvement_percent"]
    under3 = comparison["under_3s_threshold"]
    sections.append(f"| 指标 | 优化前 | 优化后 | 提升 |\n")
    sections.append(f"|------|--------|--------|------|\n")
    sections.append(f"| 平均响应时间 | {bt:.2f}s | {ot:.2f}s | **↑{imp}%** |\n")
    sections.append(f"| 总耗时 | {comparison['baseline_total']:.2f}s | {comparison['optimized_total']:.2f}s | "
                    f"快{comparison['baseline_total'] - comparison['optimized_total']:.2f}s |\n")
    sections.append(f"| 3秒阈值 | {'❌未达标' if bt >= 3 else '✅达标'} | "
                    f"{'✅达标' if ot < 3 else '❌未达标'} | "
                    f"{'🎉达成3秒目标' if under3 else '仍需优化'} |\n")
    sections.append("\n### 各查询耗时对比\n\n")
    sections.append("| # | 问题 | 优化前(s) | 优化后(s) | 提升 |\n")
    sections.append("|---|------|----------|----------|------|\n")
    for i in range(min(len(baseline["results"]), len(optimized["results"]))):
        bt_i = baseline["results"][i]["total_time"]
        ot_i = optimized["results"][i]["total_time"]
        imp_i = ((bt_i - ot_i) / bt_i * 100) if bt_i > 0 else 0
        q_short = baseline["results"][i]["question"][:25] + ("..." if len(baseline["results"][i]["question"]) > 25 else "")
        sections.append(f"| {i+1} | {q_short} | {bt_i:.2f} | {ot_i:.2f} | {'↑' if imp_i > 0 else '↓'}{abs(imp_i):.1f}% |\n")

    # 6. 结论与建议——需求：产出物——出现瓶颈的原因+进一步优化方向
    sections.append("\n## 6.结论与建议\n\n")
    if under3:
        sections.append("🎉 **优化后满足3秒验收标准！**\n\n")
    else:
        sections.append("⚠️ **仍高于3秒阈值，建议进一步优化：**\n\n")
        sections.append("- 使用FAISS IVF索引替代暴力搜索\n")
        sections.append("- 部署专用向量数据库（Milvus/Qdrant）\n")
        sections.append("- 使用更轻量的嵌入模型\n")
    sections.append("\n### 进一步优化方向\n\n")
    sections.append("1. **向量检索**: FAISS IVF/IVFPQ，检索时间降低10-100倍\n")
    sections.append("2. **LLM推理**: 流式输出、降低max_tokens、换更小模型\n")
    sections.append("3. **系统级**: 异步处理、请求批处理、连接池复用\n")
    sections.append("4. **数据级**: 优化分块策略、减少向量维度、量化\n")

    # 写入文件——需求：产出物——保存报告
    report_text = "\n".join(sections)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_text)
    print(f"💾 报告已保存: {output_path}")
    return report_text
