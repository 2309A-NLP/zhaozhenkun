#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
03_测试 — 教育辅导模拟测试
==============================================================================
测试场景：学生多次提问，验证智能体是否能识别其知识薄弱点，
追踪学习进度，并有针对性地解答和复习。
覆盖：知识追踪 × 3轮 → 薄弱点识别 → 针对性推荐验证
==============================================================================
"""

import json  # JSON 格式化
import sys  # 系统路径
import os  # 操作系统接口
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "02_研发"))

import requests  # HTTP 客户端


# ============================================================
# 测试配置
# ============================================================
BRIDGE_URL = os.getenv("BRIDGE_URL", "http://localhost:8008")  # 桥接 API
TEST_STUDENT_ID = "test_student_wang_wu_001"  # 测试学生的唯一 ID
DOMAIN = "education"  # 教育领域


def print_section(title: str):
    """打印测试章节标题。"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def call_api(method: str, path: str, **kwargs) -> dict:
    """通用 API 调用封装。"""
    url = f"{BRIDGE_URL}{path}"
    try:
        if method == "post":
            resp = requests.post(url, json=kwargs.get("json", {}), timeout=60)
        elif method == "get":
            resp = requests.get(url, params=kwargs.get("params", {}), timeout=60)
        elif method == "delete":
            resp = requests.delete(url, params=kwargs.get("params", {}), timeout=60)
        else:
            return {"success": False}
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  [错误] API 调用失败: {e}")
        return {"success": False, "message": str(e)}


def contains_any(text: str, keywords) -> bool:
    return any(keyword in text for keyword in keywords)


def test_education_scenario():
    """教育辅导模拟：3 轮学习 → 薄弱点识别验证。"""
    print_section("教育辅导模拟测试 — 学生王五")

    # ----------------------------------------------------------
    # 步骤 1: 清理历史数据
    # ----------------------------------------------------------
    print("\n[准备] 清理历史数据...")
    call_api("delete", "/api/memory/reset", params={
        "domain": DOMAIN, "user_id": TEST_STUDENT_ID,
    })

    # ----------------------------------------------------------
    # 步骤 2: 第一轮辅导（数学 — 函数基础薄弱）
    # ----------------------------------------------------------
    print_section("第1轮：数学辅导 — 二次函数求导")
    round1_conv = """
    学生：老师，二次函数求导我总是算不对，能再讲一遍吗？
    老师：好的。二次函数 f(x)=ax²+bx+c 的导数是什么还记得吗？
    学生：好像是 f'(x)=2ax+b，但我不确定为什么是这样。
    老师：没错！我们来推导一下。用求导公式：xⁿ 的导数是 n·xⁿ⁻¹。
    那 x² 的导数就是 2x，a 是系数所以变成 2a·x，bx 的导数是 b，常数 c 的导数是 0。
    学生：哦！原来是这样推导的。但我计算的时候总是符号搞错。
    老师：这很正常，多练习就好了。我给你几道题，你做做看。
    学生：第一题 f(x)=3x²-2x+1，导数是 f'(x)=6x-2，对吧？
    老师：完全正确！你学得很快。
    学生：第二题 f(x)=-x²+5x-3，导数是 f'(x)=-2x+5，对吗？
    老师：又对了！看来你已经掌握了。
    学生：谢谢老师！但我还是容易把负号搞混。
    """

    r1 = call_api("post", "/api/memory/process", json={
        "domain": DOMAIN, "user_id": TEST_STUDENT_ID, "conversation": round1_conv,
    })
    print(f"  写入结果: {r1.get('message', '失败')}")
    summary = r1.get("data", {}).get("summary", "")
    if summary:
        print(f"  学习摘要: {summary[:150]}...")

    # ----------------------------------------------------------
    # 步骤 3: 第二轮辅导（物理 — 力学问题）
    # ----------------------------------------------------------
    print_section("第2轮：物理辅导 — 牛顿第二定律")
    round2_conv = """
    学生：老师，牛顿第二定律 F=ma 的应用题我总是做不对。
    老师：别着急，我们一步步分析。你哪里不理解？
    学生：我不太明白什么时候用 F=ma，什么时候用其他公式。
    老师：F=ma 是力学的核心公式。当你需要求力、质量或加速度时就要用到它。
    比如说，一个物体质量 5kg，加速度 2m/s²，合力是多少？
    学生：F = 5 × 2 = 10N，对吗？
    老师：没错！看来你理解了计算，那如果反过来呢？已知合力 20N，质量 4kg，求加速度。
    学生：a = F/m = 20/4 = 5 m/s²！我好像懂了！
    老师：很好！但要注意方向的判断，力是有方向的。
    学生：方向判断确实容易出错...我得记住这个。
    """

    r2 = call_api("post", "/api/memory/process", json={
        "domain": DOMAIN, "user_id": TEST_STUDENT_ID, "conversation": round2_conv,
    })
    print(f"  写入结果: {r2.get('message', '失败')}")
    summary2 = r2.get("data", {}).get("summary", "")
    if summary2:
        print(f"  学习摘要: {summary2[:150]}...")

    # ----------------------------------------------------------
    # 步骤 4: 第三轮辅导（数学复习 — 薄弱点复现）
    # ----------------------------------------------------------
    print_section("第3轮：数学复习 — 薄弱点复现")
    round3_conv = """
    学生：老师，今天的复合函数求导我又搞混了...
    老师：我们回顾一下。上次你学二次函数求导时，哪部分最容易出错？
    学生：就是负号处理那部分。复合函数又有链式法则，我更晕了。
    老师：好，那我们重点攻克符号问题。记住：链式法则是"外层求导 × 内层求导"。
    比如 f(x) = (3x+1)²，外层是 u²，内层是 3x+1。
    学生：所以 f'(x) = 2(3x+1) × 3 = 6(3x+1) = 18x+6？
    老师：太棒了！你完全正确。这次符号也没搞错，进步很大！
    学生：谢谢老师！我感觉这次真的掌握了。
    """

    r3 = call_api("post", "/api/memory/process", json={
        "domain": DOMAIN, "user_id": TEST_STUDENT_ID, "conversation": round3_conv,
    })
    print(f"  写入结果: {r3.get('message', '失败')}")
    summary3 = r3.get("data", {}).get("summary", "")
    if summary3:
        print(f"  学习摘要: {summary3[:150]}...")

    # ----------------------------------------------------------
    # 步骤 5: 验证 — 检索学生学习薄弱点
    # ----------------------------------------------------------
    print_section("验证：检索学生薄弱点")
    new_query = "王五在数学和物理的学习情况，有哪些薄弱点需要加强"

    search_result = call_api("get", "/api/memory/context", params={
        "domain": DOMAIN, "user_id": TEST_STUDENT_ID, "query": new_query, "top_k": 5,
    })

    memories = search_result.get("data", {}).get("memories", [])
    count = search_result.get("data", {}).get("count", 0)
    print(f"  检索到 {count} 条相关记忆")

    for i, mem in enumerate(memories, 1):
        print(f"\n  记忆 #{i}:")
        print(f"    内容: {mem.get('memory', 'N/A')[:150]}...")
        score = mem.get("score")
        if score:
            print(f"    相关度: {score:.4f}")

    # ----------------------------------------------------------
    # 步骤 6: 验证检查 + 带记忆聊天回复
    # ----------------------------------------------------------
    print_section("验证结论")
    all_text = " ".join(m.get("memory", "") for m in memories)

    checks = [
        ("检索到至少 2 条学习记录", count >= 2),
        ("记忆包含'求导'知识点", contains_any(all_text, ["求导", "导数", "derivative"])),
        ("记忆包含'符号'薄弱点", contains_any(all_text, ["符号", "负号", "sign"])),
        ("记忆包含'牛顿第二定律'", contains_any(all_text, ["牛顿", "F=ma", "力学", "Newton"])),
        ("记忆包含'方向判断'薄弱点", contains_any(all_text, ["方向", "direction"])),
        ("记忆包含学生进步信息", contains_any(all_text, ["进步", "掌握", "正确", "progress", "improved", "master"])),
    ]

    chat_result = call_api("post", "/api/chat", json={
        "domain": DOMAIN,
        "user_id": TEST_STUDENT_ID,
        "inject_memory": True,
        "memory_injected": False,
        "messages": [
            {"role": "system", "content": "你是一个辅导老师。"},
            {"role": "user", "content": "请结合我之前的学习记录，告诉我现在最该优先复习哪些薄弱点，并给我一点鼓励。"}
        ]
    })
    reply_text = chat_result.get("reply", "")
    print(f"  带记忆回复预览: {reply_text[:200]}...")
    checks.append(("回复体现数学薄弱点", contains_any(reply_text, ["符号", "链式法则", "求导", "导数", "sign", "derivative"])))
    checks.append(("回复体现物理薄弱点", contains_any(reply_text, ["方向", "牛顿", "F=ma", "Newton", "direction"])))
    checks.append(("后端实际使用了历史记忆", chat_result.get("used_memory_count", 0) >= 1))

    all_passed = True
    for desc, passed in checks:
        status = "✅ 通过" if passed else "❌ 未通过"
        if not passed:
            all_passed = False
        print(f"  {status} — {desc}")

    # ----------------------------------------------------------
    # 步骤 7: 列出所有记忆
    # ----------------------------------------------------------
    print_section("全部学习记录")
    list_result = call_api("get", "/api/memory/list", params={
        "domain": DOMAIN, "user_id": TEST_STUDENT_ID,
    })
    all_memories = list_result.get("data", {}).get("memories", [])
    print(f"  共 {len(all_memories)} 条学习记录:")
    for i, mem in enumerate(all_memories, 1):
        print(f"  {i}. {mem.get('memory', 'N/A')[:100]}...")

    # ----------------------------------------------------------
    # 步骤 8: 清理
    # ----------------------------------------------------------
    print_section("清理测试数据")
    call_api("delete", "/api/memory/reset", params={
        "domain": DOMAIN, "user_id": TEST_STUDENT_ID,
    })
    print("  测试数据已清理")

    print(f"\n{'='*60}")
    print(f"  测试结果: {'全部通过 ✅' if all_passed else '存在未通过项 ❌'}")
    print(f"{'='*60}")
    return all_passed


# ============================================================
# 入口
# ============================================================
if __name__ == "__main__":
    success = test_education_scenario()
    sys.exit(0 if success else 1)
