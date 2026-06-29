# -*- coding: utf-8 -*-
"""
test_6_cases.py — 6个需求测试用例 + 变体场景测试
--------------------------------------------------------------
运行方式:  cd Agent工单11 && python 测试/test_6_cases.py
前提条件: python run.py 已在另一个终端启动(http://127.0.0.1:5003)

工单编号: 人工智能NLP-Agent数字人项目-医疗智能体-挂号管理任务
所属目录: 测试
"""
import requests       # HTTP请求
import time           # 耗时统计
import json           # JSON解析

BASE = "http://127.0.0.1:5003/api/chat"  # 测试目标API

# ============================================================
# 6个核心测试用例(来自任务工单)
# ============================================================
TEST_CASES = [
    # 用例1: 挂号
    ("帮我大宝挂一个今天下午2点儿科专家的号",
     ["儿科", "挂号成功"]),  # 期望包含这些关键词

    # 用例2: 号源查询
    ("牙科最近的号哪天的？",
     ["牙科"]),

    # 用例3: 复约(基于历史)
    ("我之前挂过眼科的一个专家，帮我再约那个专家的号",
     ["眼科", "吴丹"]),  # 历史中吴丹=眼科主任医师

    # 用例4: 二宝皮肤科
    ("我明天上午9点想带二宝看皮肤科，还有号吗？",
     ["皮肤科"]),

    # 用例5: 取消挂号
    ("取消我上周三挂的消化内科普通号",
     ["消化内科", "取消"]),

    # 用例6: 医生排班
    ("帮我查下张建国医生下周的坐诊时间",
     ["张建国"]),
]

# ============================================================
# 变体测试(边界场景)
# ============================================================
EDGE_CASES = [
    # 时间冲突
    "帮我挂一个昨天下午3点的儿科号",     # 过去时间
    # 号源不足
    "帮我挂一个牙科的号，随便什么时间",   # 不指定时间
    # 无效科室
    "帮我挂一个美容科的号",               # 不存在的科室
    # 错误时间格式
    "帮我挂一个下个月32号的号",           # 无效日期
    # 无家人匹配
    "帮我三宝挂一个儿科号",               # 不存在的家人
]

def run_test(query: str, expected_keywords: list = None):
    """执行单个测试用例并打印结果。"""
    print(f"\n{'='*60}")
    print(f"🧪 测试: {query[:60]}")
    t0 = time.time()
    try:
        resp = requests.post(BASE,
            json={"question": query, "session": "test"},
            timeout=30)
        elapsed = time.time() - t0
        data = resp.json()
        answer = data.get("answer", "")
        tool = data.get("tool", "")
        # 打印结果
        print(f"  工具: {tool} | 耗时: {elapsed*1000:.0f}ms")
        print(f"  回答: {answer[:200]}")
        # 关键词检查
        if expected_keywords:
            hits = [kw for kw in expected_keywords if kw in answer]
            if hits:
                print(f"  ✅ 关键词命中: {hits}")
            else:
                print(f"  ⚠️ 未命中关键词: {expected_keywords}")
        # SLA检查(<500ms)
        if elapsed < 0.5:
            print(f"  ✅ SLA达标 ({elapsed*1000:.0f}ms < 500ms)")
        else:
            print(f"  ⚠️ SLA超标 ({elapsed*1000:.0f}ms > 500ms)")
        return elapsed
    except Exception as e:
        print(f"  ❌ 请求失败: {e}")
        return 999

if __name__ == "__main__":
    print("=" * 60)
    print("🏥 医疗挂号Agent — 6核心用例 + 5边界测试")
    print("=" * 60)

    # 健���检查
    try:
        h = requests.get("http://127.0.0.1:5003/api/health", timeout=5)
        print(f"\n健康检查: {h.json()}")
    except Exception:
        print("\n⚠️ 服务未启动! 请先运行: python run.py")
        exit(1)

    times = []
    print("\n" + "=" * 60)
    print("📋 6个核心测试用例")
    print("=" * 60)
    for query, keywords in TEST_CASES:
        t = run_test(query, keywords)
        times.append(t)

    print("\n" + "=" * 60)
    print("📋 5个边界场景测试")
    print("=" * 60)
    for query in EDGE_CASES:
        t = run_test(query)
        times.append(t)

    # 汇总
    print("\n" + "=" * 60)
    print("📊 测试汇总")
    print(f"  总用例: {len(times)}")
    print(f"  平均耗时: {sum(times)/len(times)*1000:.0f}ms")
    print(f"  最快: {min(times)*1000:.0f}ms")
    print(f"  最慢: {max(times)*1000:.0f}ms")
    sla_ok = sum(1 for t in times if t < 0.5)
    print(f"  SLA达标(<500ms): {sla_ok}/{len(times)}")
