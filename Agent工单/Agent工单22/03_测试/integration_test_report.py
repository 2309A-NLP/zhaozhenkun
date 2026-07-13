#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
03_测试 — 集成测试报告 + 性能基准测试
==============================================================================
产出物4：集成与测试报告
- 三个领域的端到端测试验证
- 记忆检索延迟测量（目标 <200ms）
- 记忆写入延迟测量（目标 <2000ms）
- 并发请求稳定性测试
- LLM调用延迟测量
运行: python integration_test_report.py (需要先启动 agent_bridge.py)
==============================================================================
"""

import json, sys, os, time, statistics, threading  # 标准库
from concurrent.futures import ThreadPoolExecutor  # 并发测试

import requests  # HTTP客户端

# 桥接API地址
API = os.getenv("BRIDGE_URL", "http://localhost:8008")

# ============================================================
# 工具函数
# ============================================================
def now_ms():
    """获取当前时间戳（毫秒）。"""
    return time.time() * 1000


def measure(action_name, func, *args, **kwargs):
    """测量一个函数的执行时间，返回 (结果, 延迟ms)。"""
    start = now_ms()
    result = func(*args, **kwargs)
    elapsed = now_ms() - start
    print(f"  [计时] {action_name}: {elapsed:.1f}ms")
    return result, elapsed


def call_get(path, params=None):
    """GET 请求封装。"""
    return requests.get(f"{API}{path}", params=params or {}, timeout=30)


def call_post(path, body):
    """POST 请求封装。"""
    return requests.post(f"{API}{path}", json=body,
                         headers={"Content-Type": "application/json"}, timeout=60)


def call_delete(path, params=None):
    """DELETE 请求封装。"""
    return requests.delete(f"{API}{path}", params=params or {}, timeout=10)


# ============================================================
# 测试数据
# ============================================================
# 测试对话数据（医疗3轮/文旅2轮/教育3轮）
MEDICAL_CONVERSATIONS = [
    "医生：您好，请问今天哪里不舒服？\n患者：最近总是头痛，下午严重，有时恶心。\n医生：持续多久了？\n患者：大概一周了。以前偶尔也有。\n医生：先开布洛芬，三天没好再来复诊。",
    "医生：上次布洛芬效果如何？\n患者：还是头痛，今早站起来晕了一次，眼前一黑。\n医生：可能不是普通头痛，开CT检查。\n患者：对了，我对青霉素过敏，之前忘了说。\n医生：已记录过敏信息。",
    "医生：CT结果出来了，没有器质性病变，紧张性头痛。\n患者：需要注意什么？\n医生：放松别熬夜，继续吃药，再加改善睡眠的药。\n患者：谢谢医生。",
]
TOURISM_CONVERSATIONS = [
    "用户：想找个地方度假。\n助手：喜欢海边还是山？\n用户：海边，温暖，预算舒适，一家人带两个小孩。\n助手：三亚或厦门适合亲子游。\n用户：三亚！我喜欢海鲜。",
    "用户：上次三亚很棒，这次想出国看看。\n助手：东南亚海岛很适合，巴厘岛或泰国？\n用户：巴厘岛，全家去，预算可以高一些，喜欢深度游。",
]
EDUCATION_CONVERSATIONS = [
    "学生：二次函数求导我总是算不对。\n老师：f(x)=ax²+bx+c的导数是f'(x)=2ax+b。练习：f(x)=3x²-2x+1？\n学生：f'(x)=6x-2？\n老师：正确！但注意负号。\n学生：容易把负号搞混。",
    "学生：牛顿第二定律F=ma的应用题不会。\n老师：质量5kg，加速度2m/s²，合力？\n学生：F=10N！\n老师：反过来，合力20N质量4kg？\n学生：a=5m/s²！但方向判断容易错。",
    "学生：复合函数求导又搞混了。\n老师：链式法则，外层×内层。f(x)=(3x+1)²？\n学生：f'(x)=2(3x+1)×3=18x+6？\n老师：太棒了，这次符号也没错，进步很大！",
]


# ============================================================
# 一、功能测试：三个领域端到端验证
# ============================================================
def test_domain_e2e(domain, user_id, conversations):
    """单领域端到端测试：多轮写入→检索验证。"""
    print(f"\n{'='*50}")
    print(f"  功能测试: {domain} 领域 (用户: {user_id})")
    print(f"{'='*50}")

    # 清理历史数据
    call_delete("/api/memory/reset", {"domain": domain, "user_id": user_id})

    write_times = []  # 写入延迟记录
    memory_counts = []  # 每轮记忆数量

    for i, conv in enumerate(conversations):
        # 写入对话记忆并计时
        _, lat = measure(
            f"第{i+1}轮对话写入",
            lambda: call_post("/api/memory/process",
                             {"domain": domain, "user_id": user_id, "conversation": conv})
        )
        write_times.append(lat)

        # 查记忆数
        r = call_get("/api/memory/list", {"domain": domain, "user_id": user_id})
        count = r.json().get("data", {}).get("count", 0)
        memory_counts.append(count)

    # 检索验证：用最后一轮的关键词搜索
    search_queries = {
        "medical": "头痛 青霉素过敏",
        "tourism": "海边 家庭 巴厘岛",
        "education": "求导 牛顿定律 薄弱点",
    }
    query = search_queries.get(domain, "test")
    search_result, search_lat = measure(
        "历史记忆检索",
        lambda: call_get("/api/memory/context",
                        {"domain": domain, "user_id": user_id, "query": query, "top_k": 5})
    )
    memories = search_result.json().get("data", {}).get("memories", [])
    search_count = len(memories)

    # 返回测试结果
    passed = search_count >= 1 and memory_counts[-1] >= 1
    return {
        "domain": domain,
        "user_id": user_id,
        "rounds": len(conversations),
        "final_memory_count": memory_counts[-1] if memory_counts else 0,
        "search_results": search_count,
        "avg_write_ms": round(statistics.mean(write_times), 1) if write_times else 0,
        "search_ms": round(search_lat, 1),
        "passed": passed,
    }


# ============================================================
# 二、性能测试：延迟基准
# ============================================================
def test_latency_benchmark():
    """测量各操作延迟基准。"""
    print(f"\n{'='*50}\n  性能基准测试\n{'='*50}")
    results = {}
    _, lat = measure("健康检查", lambda: requests.get(f"{API}/api/health", timeout=5))
    results["health_check_ms"] = round(lat, 1)
    _, lat = measure("记忆列表", lambda: call_get("/api/memory/list", {"domain":"medical","user_id":"bench"}))
    results["list_memories_ms"] = round(lat, 1)
    search_lats = []
    for i in range(10):  # 重复10次取统计值
        _, lat = measure(f"检索#{i+1}", lambda: call_get("/api/memory/context",
            {"domain":"medical","user_id":"bench","query":f"查询{i}","top_k":3}))
        search_lats.append(lat)
    results["search_avg_ms"] = round(statistics.mean(search_lats), 1)
    results["search_p95_ms"] = round(sorted(search_lats)[int(len(search_lats)*0.95)], 1)
    results["search_min_ms"] = round(min(search_lats), 1)
    results["search_max_ms"] = round(max(search_lats), 1)
    _, lat = measure("LLM对话", lambda: call_post("/api/chat",
        {"messages":[{"role":"user","content":"1+1=?一句话回复"}]}))
    results["llm_chat_ms"] = round(lat, 1)
    return results


# ============================================================
# 三、并发测试
# ============================================================
def test_concurrency(num_workers=5):
    """并发测试：多线程同时请求真实记忆接口。"""
    print(f"\n{'='*50}\n  并发测试 ({num_workers} 线程)\n{'='*50}")
    lock = threading.Lock()
    success, fail = [0], [0]
    lats = []

    def worker(wid):
        for i in range(5):
            try:
                if i % 2 == 0:
                    path = "/api/memory/context"
                    method = "get"
                    payload = {"domain": "medical", "user_id": f"bench_{wid}", "query": f"并发查询{i}", "top_k": 3}
                else:
                    path = "/api/memory/process"
                    method = "post"
                    payload = {
                        "domain": "medical",
                        "user_id": f"bench_{wid}",
                        "conversation": f"用户：我第{i}次并发测试提到头痛。\n助手：已记录本轮并发测试。",
                    }

                start = now_ms()
                if method == "get":
                    r = requests.get(f"{API}{path}", params=payload, timeout=15)
                else:
                    r = requests.post(f"{API}{path}", json=payload, timeout=30)
                elapsed = now_ms() - start

                if r.status_code == 200:
                    with lock:
                        success[0] += 1
                        lats.append(elapsed)
                else:
                    with lock:
                        fail[0] += 1
            except Exception:
                with lock:
                    fail[0] += 1

    threads = []
    start_all = now_ms()
    for i in range(num_workers):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    total_time = now_ms() - start_all
    total = success[0] + fail[0]
    return {
        "workers": num_workers, "total_requests": total,
        "success": success[0], "fail": fail[0],
        "success_rate": round(success[0]/total*100,1) if total else 0,
        "total_time_ms": round(total_time,1),
        "avg_latency_ms": round(statistics.mean(lats),1) if lats else 0,
        "max_latency_ms": round(max(lats),1) if lats else 0,
        "stable": success[0] == total,
    }


# ============================================================
# 四、报告生成
# ============================================================
def generate_report(functional, benchmark, concurrency):
    """生成并输出测试报告，同时保存 JSON。"""
    print(f"\n{'='*60}\n  集成测试报告\n{'='*60}")
    # 功能
    print("\n--- 一、功能测试 ---")
    all_func = all(r["passed"] for r in functional)
    for r in functional:
        s = "✅" if r["passed"] else "❌"
        print(f"  {s} {r['domain']} | 轮次:{r['rounds']} 记忆:{r['final_memory_count']} 检索:{r['search_results']} 写入:{r['avg_write_ms']}ms")
    # 性能
    print("\n--- 二、性能测试 ---")
    b = benchmark
    print(f"  检索平均: {b['search_avg_ms']}ms {'✅' if b['search_avg_ms']<200 else '❌'} (目标<200ms)")
    print(f"  检索P95:  {b['search_p95_ms']}ms  最小:{b['search_min_ms']}ms  最大:{b['search_max_ms']}ms")
    print(f"  LLM对话:  {b['llm_chat_ms']}ms  列表:{b['list_memories_ms']}ms  健康:{b['health_check_ms']}ms")
    # 并发
    print("\n--- 三、并发测试 ---")
    c = concurrency
    print(f"  线程:{c['workers']} 请求:{c['total_requests']} 成功率:{c['success_rate']}% 平均:{c['avg_latency_ms']}ms 最大:{c['max_latency_ms']}ms {'✅' if c['stable'] else '❌'}")
    # 结论
    search_ok = b["search_avg_ms"] < 200
    all_ok = all_func and search_ok and c["stable"]
    print(f"\n--- 四、结论 ---")
    print(f"  {'✅' if all_func else '❌'} 功能 | {'✅' if search_ok else '❌'} 性能 | {'✅' if c['stable'] else '❌'} 并发")
    print(f"  总体验收: {'✅ 通过' if all_ok else '❌ 未达标'}")
    # 保存报告JSON
    path = os.path.join(os.path.dirname(__file__), "test_report_output.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"date": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "functional": functional, "benchmark": benchmark,
                   "concurrency": concurrency, "passed": all_ok}, f, ensure_ascii=False, indent=2)
    print(f"\n  报告已保存: {path}")
    return all_ok


# ============================================================
# 主入口
# ============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  多领域智能体长期记忆系统 — 集成测试")
    print(f"  API地址: {API}")
    print(f"  开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # --- 0. 预检 ---
    print("\n[预检] 检查API连通性...")
    try:
        r = requests.get(f"{API}/api/health", timeout=5)
        if r.json().get("status") == "ok":
            print("  ✅ API服务正常")
        else:
            print("  ⚠ API服务异常，请确认agent_bridge.py已启动")
            exit(1)
    except Exception as e:
        print(f"  ❌ 无法连接API: {e}")
        print("  请先启动: python 02_研发/agent_bridge.py")
        exit(1)

    # --- 一、功能测试 ---
    functional_results = []
    # 医疗复诊
    functional_results.append(
        test_domain_e2e("medical", "report_patient_001", MEDICAL_CONVERSATIONS))
    # 文旅规划
    functional_results.append(
        test_domain_e2e("tourism", "report_traveler_001", TOURISM_CONVERSATIONS))
    # 教育辅导
    functional_results.append(
        test_domain_e2e("education", "report_student_001", EDUCATION_CONVERSATIONS))

    # --- 二、性能基准 ---
    benchmark_results = test_latency_benchmark()

    # --- 三、并发测试 ---
    concurrency_results = test_concurrency(num_workers=5)

    # --- 四、生成报告 ---
    all_passed = generate_report(functional_results, benchmark_results, concurrency_results)

    # --- 清理测试数据 ---
    print("\n[清理] 清除测试数据...")
    for r in functional_results:
        call_delete("/api/memory/reset",
                    {"domain": r["domain"], "user_id": r["user_id"]})
        call_delete("/api/memory/reset",
                    {"domain": "medical", "user_id": "bench_user"})
    print("  测试数据已清理")

    # 退出
    sys.exit(0 if all_passed else 1)
