"""
profiler.py - RAG工单13 性能分析模块
需求: 使用Python cProfile对RAG各阶段做函数级性能分析 — 工单"识别瓶颈的工具和技术"第1类"性能分析"
功能: 1.ProfileStage包装器(对任意函数做cProfile) 2.profile_pipeline(全流水线分析) 3.输出热点函数排行
"""
import logging
import cProfile         # 需求：Python内置性能分析器，统计每个函数的调用次数和耗时
import pstats           # 需求：格式化cProfile输出为可读报告
import io               # 需求：捕获pstats的文本输出
import time             # 需求：简单计时（cProfile的补充）

logger = logging.getLogger(__name__)
logger.info("性能分析模块加载")



def profile_function(func, *args, **kwargs):
    """
    对单个函数做cProfile性能分析
    需求：工单"应用级性能分析工具——Python cProfile"
    返回：(函数返回值, 分析报告文本)
    """
    profiler = cProfile.Profile()       # 创建分析器实例
    profiler.enable()                   # 开始记录
    result = func(*args, **kwargs)      # 执行目标函数
    profiler.disable()                  # 停止记录

    # 格式化报告——需求：按累计耗时排序，取前20个热点函数
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.sort_stats("cumulative")      # 按累计耗时排序
    stats.print_stats(20)              # 只显示前20个热点
    report = stream.getvalue()
    return result, report


def profile_pipeline(rag_query_func, question, chunks, vectors, chunk_meta):
    """
    对完整RAG查询做cProfile分析
    需求：工单"分析检索性能慢的原因"——函数级热点定位
    返回：{result, report_text, hotspots}
    """
    from 研发.timer import Timer
    timer = Timer()

    def _run():
        return rag_query_func(question, chunks, vectors, chunk_meta, timer)

    result, report_text = profile_function(_run)

    # 提取top5热点函数——需求：快速定位最耗时的函数
    hotspots = []
    for line in report_text.split("\n"):
        line = line.strip()
        if line and not line.startswith("ncalls") and not line.startswith("-"):
            parts = line.split()
            if len(parts) >= 6:
                try:
                    float(parts[1])  # 验证是数字行
                    hotspots.append({
                        "calls": parts[0],
                        "tottime": parts[1],
                        "percall": parts[2],
                        "cumtime": parts[3],
                        "function": " ".join(parts[5:])
                    })
                except ValueError:
                    continue
        if len(hotspots) >= 5:
            break

    return {
        "result": result,
        "report": report_text,
        "hotspots": hotspots,
        "timer_summary": timer.get_summary()
    }


def print_profile_report(profile_data):
    """打印格式化的性能分析报告——需求：可视化展示各阶段热点"""
    print("\n" + "=" * 60)
    print("🔍 cProfile 函数级性能分析")
    print("=" * 60)

    # 计时器摘要
    summary = profile_data.get("timer_summary", {})
    if summary:
        print("\n📊 各阶段耗时:")
        for name, stats in sorted(summary.items(), key=lambda x: -x[1]["total"]):
            print(f"  {name:<25} {stats['total']:>8.3f}s  (×{stats['count']})")

    # Top热点函数
    hotspots = profile_data.get("hotspots", [])
    if hotspots:
        print("\n🔥 Top-5 热点函数:")
        print(f"  {'调用次数':<12} {'总耗时':<10} {'函数':<50}")
        print(f"  {'-'*12} {'-'*10} {'-'*50}")
        for h in hotspots:
            print(f"  {h['calls']:<12} {h['tottime']:<10} {h['function'][:50]}")

    print("=" * 60)

