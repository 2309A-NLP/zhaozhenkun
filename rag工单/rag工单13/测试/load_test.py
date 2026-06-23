"""
load_test.py - RAG工单13 负载测试模块
需求: 并发负载测试，分析延迟和吞吐量随负载的变化 — 工单"识别瓶颈的工具"第5类"负载测试"
功能: 1.run_load_test(多线程并发) 2.统计P50/P95/P99延迟 3.吞吐量计算 4.结果保存
"""
import logging
import time                 # 需求：计时
import threading            # 需求：并发请求（Python GIL下I/O密集型仍有效）
import json                 # 需求：结果序列化
import statistics           # 需求：P50/P95/P99百分位计算
import os                   # 需求：路径操作

import 研发.config as config          # 需求：测试问题、输出路径

logger = logging.getLogger(__name__)


def run_load_test(query_func, questions, concurrency=3, repeat=1):
    """
    并发负载测试——需求：工单"负载测试"——分析延迟和吞吐量随负载的变化
    query_func: 接受question参数并返回结果的函数
    questions: 测试问题列表
    concurrency: 并发线程数（默认3，模拟3个并发用户）
    repeat: 每个问题重复次数（默认1）
    返回：延迟统计+吞吐量+每题详情
    """
    # 构建测试任务列表
    tasks = []
    for q in questions:
        for _ in range(repeat):
            tasks.append(q)

    results = []                # 存储每个请求的结果
    lock = threading.Lock()     # 线程安全锁
    errors = []                 # 错误记录
    all_start = time.time()     # 全局起始时间

    def worker(question, idx):
        """单个工作线程——需求：记录每个请求的耗时"""
        t0 = time.time()
        try:
            result = query_func(question)
            elapsed = time.time() - t0
            with lock:
                results.append({
                    "index": idx,
                    "question": question[:30],
                    "elapsed": round(elapsed, 4),
                    "success": True
                })
        except Exception as e:
            elapsed = time.time() - t0
            with lock:
                results.append({
                    "index": idx,
                    "question": question[:30],
                    "elapsed": round(elapsed, 4),
                    "success": False,
                    "error": str(e)
                })
                errors.append(str(e))

    # 使用线程池执行——需求：模拟并发用户
    threads = []
    for i, q in enumerate(tasks):
        t = threading.Thread(target=worker, args=(q, i))
        threads.append(t)
        t.start()
        # 控制并发度：每启动concurrency个线程后等待完成
        if len(threads) >= concurrency:
            for th in threads:
                th.join()
            threads = []
    # 等待剩余线程
    for th in threads:
        th.join()

    total_time = time.time() - all_start

    # 统计延迟——需求：P50/P95/P99百分位
    latencies = [r["elapsed"] for r in results if r["success"]]
    latency_stats = {}
    if latencies:
        sorted_lat = sorted(latencies)
        latency_stats = {
            "min": round(min(sorted_lat), 3),
            "max": round(max(sorted_lat), 3),
            "avg": round(statistics.mean(sorted_lat), 3),
            "median_p50": round(sorted_lat[len(sorted_lat) // 2], 3),
            "p95": round(sorted_lat[int(len(sorted_lat) * 0.95)], 3) if len(sorted_lat) >= 2 else round(max(sorted_lat), 3),
            "p99": round(sorted_lat[int(len(sorted_lat) * 0.99)], 3) if len(sorted_lat) >= 2 else round(max(sorted_lat), 3),
        }

    # 吞吐量——需求：工单"吞吐量由处理能力最低的阶段决定"
    throughput = len(latencies) / total_time if total_time > 0 else 0

    return {
        "concurrency": concurrency,
        "total_tasks": len(tasks),
        "successful": len(latencies),
        "failed": len(errors),
        "total_time_seconds": round(total_time, 3),
        "throughput_qps": round(throughput, 2),
        "latency_stats": latency_stats,
        "per_request": sorted(results, key=lambda x: x["index"]),
        "errors": errors[:5]     # 只保留前5个错误
    }


def print_load_test_report(load_result):
    """打印负载测试报告——需求：可视化展示并发性能数据"""
    print("\n" + "=" * 60)
    print("🚀 负载测试报告")
    print("=" * 60)
    print(f"  并发数:     {load_result['concurrency']}")
    print(f"  总任务:     {load_result['total_tasks']}")
    print(f"  成功/失败:  {load_result['successful']}/{load_result['failed']}")
    print(f"  总耗时:     {load_result['total_time_seconds']:.2f}s")
    print(f"  吞吐量:     {load_result['throughput_qps']:.2f} QPS")

    stats = load_result.get("latency_stats", {})
    if stats:
        print(f"\n📊 延迟分布:")
        print(f"  最小:  {stats['min']:.3f}s")
        print(f"  P50:   {stats['median_p50']:.3f}s")
        print(f"  P95:   {stats['p95']:.3f}s")
        print(f"  P99:   {stats['p99']:.3f}s")
        print(f"  最大:  {stats['max']:.3f}s")
        print(f"  平均:  {stats['avg']:.3f}s")

        # 需求：验收标准——3秒阈值
        if stats["p95"] < 3.0:
            print(f"\n  ✅ P95延迟 < 3s，满足验收标准")
        else:
            print(f"\n  ❌ P95延迟 = {stats['p95']:.2f}s > 3s，未达验收标准")

    print("=" * 60)
