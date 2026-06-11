"""
run.py - RAG工单13 全流程主入口（调用全部12个模块）
需求: 支持命令行基准测试(默认)和Web对话(--web)两种模式 — 工单"验收标准"每个会话返回结果
功能: 1.--pipeline 6步基准测试 2.--web 启动Flask对话服务 3.--profile cProfile分析 4.--load 并发负载测试
"""
import logging
import sys, os, json, time, argparse  # 需求：系统路径、结果保存、计时、命令行参数
import 研发.config as config              # 需求：测试问题、路径配置
from 研发.timer import Timer              # 需求：计时器
from 研发.rag_pipeline import load_or_build_index, rag_query  # 需求：RAG流水线
from 测试.benchmark import run_baseline, run_optimized, compare  # 需求：基准测试
from 优化.bottleneck_analyzer import analyze_bottlenecks  # 需求：瓶颈分析
from 优化.report_generator import generate_report  # 需求：报告生成

logger = logging.getLogger(__name__)
logger.info("RAG工单13 性能分析启动")



def main():
    """完整6步流程——需求：工单"产出物"——过程跟踪+瓶颈原因+优化方案+性能对比"""
    print("=" * 60)
    print("🚀 RAG性能瓶颈识别与优化 — 全流程")
    print("=" * 60)

    # Step 1: 构建/加载索引——需求：离线准备阶段
    print("\n📦 Step 1/6: 构建/加载索引...")
    index_timer = Timer()
    chunks, vectors, chunk_meta = load_or_build_index(index_timer)
    index_timer.print_summary()

    # Step 2: 基线测试——需求：测量优化前的原始性能
    print("\n🔬 Step 2/6: 基线性能测试...")
    baseline = run_baseline(config.TEST_QUESTIONS)
    print(f"\n  基线平均耗时: {baseline['avg_time_per_query']:.2f}s")

    # Step 3: 瓶颈分析——需求：找出影响响应时间的原因
    print("\n🔍 Step 3/6: 瓶颈分析...")
    btl_timer = Timer()
    for stage_name, stats in baseline.get("bottleneck_analysis", {}).get("stages", []):
        for _ in range(stats["count"]):
            btl_timer._records[stage_name].append(stats["avg"])
    analysis = analyze_bottlenecks(btl_timer)
    print(f"  结论: {analysis['conclusion']}")

    # Step 4: 优化——需求：应用优化策略
    print("\n⚡ Step 4/6: 优化后性能测试...")
    optimized = run_optimized(config.TEST_QUESTIONS)
    print(f"\n  优化后平均耗时: {optimized['avg_time_per_query']:.2f}s")

    # Step 5: 对比分析——需求：量化优化前后的性能提升
    print("\n📊 Step 5/6: 对比分析...")
    comparison = compare(baseline, optimized)

    print(f"\n{'='*60}")
    print(f"📊 优化前后对比")
    print(f"{'='*60}")
    print(f"  优化前平均: {comparison['baseline_avg_seconds']:.2f}s")
    print(f"  优化后平均: {comparison['optimized_avg_seconds']:.2f}s")
    print(f"  提升:       ↑{comparison['improvement_percent']}%")
    print(f"  3秒达标:    {'✅是' if comparison['under_3s_threshold'] else '❌否'}")
    print(f"{'='*60}")

    # 保存基准测试结果
    result_data = {"baseline": baseline, "optimized": optimized,
                   "comparison": comparison, "bottleneck_analysis": analysis,
                   "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}
    with open(config.BENCHMARK_OUTPUT, "w", encoding="utf-8") as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)
    print(f"\n💾 基准数据: {config.BENCHMARK_OUTPUT}")

    # Step 6: 报告生成——需求：产出物
    report = generate_report(baseline, optimized, comparison, analysis, config.REPORT_OUTPUT)
    print(f"📝 优化报告: {config.REPORT_OUTPUT}")

    print("\n📋 报告预览:")
    for line in report.split("\n")[:15]:
        print(f"  {line}")
    return result_data


def run_profile():
    """cProfile函数级性能分析——需求：工单"性能分析工具"（cProfile）"""
    from 优化.profiler import profile_pipeline, print_profile_report

    print("=" * 60)
    print("🔍 RAG cProfile 性能分析")
    print("=" * 60)

    chunks, vectors, chunk_meta = load_or_build_index()
    q = config.TEST_QUESTIONS[0]  # 用第一题做分析
    print(f"\n📝 分析问题: {q}")

    profile_data = profile_pipeline(rag_query, q, chunks, vectors, chunk_meta)
    print_profile_report(profile_data)

    # 保存分析结果
    profile_path = os.path.join(config.OUTPUT_DIR, "profile_report.txt")
    with open(profile_path, "w", encoding="utf-8") as f:
        f.write(profile_data["report"])
    print(f"\n💾 详细报告: {profile_path}")
    return profile_data


def run_load():
    """并发负载测试——需求：工单"负载测试"（延迟和吞吐量随负载变化）"""
    from 测试.load_test import run_load_test, print_load_test_report

    print("=" * 60)
    print("🚀 RAG 并发负载测试")
    print("=" * 60)

    chunks, vectors, chunk_meta = load_or_build_index()

    # 包装查询函数
    def query_func(question):
        result = rag_query(question, chunks, vectors, chunk_meta)
        return result

    # 需求：分别测试不同并发度
    for conc in [1, 3, 5]:
        print(f"\n--- 并发数={conc} ---")
        result = run_load_test(query_func, config.TEST_QUESTIONS[:5],
                               concurrency=conc, repeat=1)
        print_load_test_report(result)

        # 保存结果
        load_path = os.path.join(config.OUTPUT_DIR, f"load_test_c{conc}.json")
        with open(load_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"💾 {load_path}")


if __name__ == "__main__":
    """命令行入口——需求：支持多种模式"""
    parser = argparse.ArgumentParser(description="RAG工单13 性能瓶颈识别与优化")
    parser.add_argument("--web", action="store_true", help="启动Web对话服务")
    parser.add_argument("--pipeline", action="store_true", help="运行6步基准测试流水线")
    parser.add_argument("--profile", action="store_true", help="cProfile函数级性能分析")
    parser.add_argument("--load", action="store_true", help="并发负载测试")
    args = parser.parse_args()

    if args.web:
        print("🚀 启动Web对话服务...")
        print("🌐 打开浏览器访问: http://localhost:5008")
        from 部署.app import app
        app.run(host="0.0.0.0", port=5008, debug=False)
    elif args.profile:
        try:
            run_profile()
            print("\n✅ 性能分析完成！")
        except Exception as e:
            print(f"\n❌ 失败: {e}")
            import traceback; traceback.print_exc()
            sys.exit(1)
    elif args.load:
        try:
            run_load()
            print("\n✅ 负载测试完成！")
        except Exception as e:
            print(f"\n❌ 失败: {e}")
            import traceback; traceback.print_exc()
            sys.exit(1)
    else:
        # 默认或--pipeline跑基准测试
        try:
            result = main()
            print("\n✅ 全流程完成！")
            print(f"📁 产出物: {config.OUTPUT_DIR}/")
        except KeyboardInterrupt:
            print("\n\n⚠️ 用户中断")
            sys.exit(1)
        except Exception as e:
            print(f"\n❌ 失败: {e}")
            import traceback; traceback.print_exc()
            sys.exit(1)

