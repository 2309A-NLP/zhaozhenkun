#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
03_测试 — 医疗复诊模拟测试
==============================================================================
测试场景：患者多次咨询同一病症，验证智能体是否能回忆历史情况，
避免重复询问，提供连续的诊疗建议。
覆盖：记忆写入 × 3轮 → 记忆检索 → 上下文验证
==============================================================================
"""

import json  # JSON 格式化输出
import sys  # 系统路径
import os  # 操作系统接口

# 添加研发模块路径，跟02_研发在同一个项目内
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "02_研发"))
from agent_bridge import MemoryResponse  # 仅用于类型参考

# 导入测试目标：通过 agent_bridge 的 HTTP API 测试完整链路
import requests  # HTTP 客户端，调用桥接 API


# ============================================================
# 测试配置
# ============================================================
# 桥接 API 地址（agent_bridge.py 默认端口 8008）
BRIDGE_URL = os.getenv("BRIDGE_URL", "http://localhost:8008")
# 测试患者 ID，每次测试使用不同 ID 避免数据污染
TEST_PATIENT_ID = "test_patient_zhang_san_001"
# 测试领域
DOMAIN = "medical"


def print_section(title: str):
    """打印测试章节标题，清晰分隔各步骤。"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def call_api(method: str, path: str, **kwargs) -> dict:
    """通用的 API 调用封装函数。

    Args:
        method: HTTP 方法 (get/post/delete)
        path: API 路径，如 /api/memory/process
        **kwargs: 传递给 requests 的参数 (json/params)

    Returns:
        API 响应的 JSON 字典
    """
    url = f"{BRIDGE_URL}{path}"  # 拼接完整 URL
    try:
        # 根据方法分发调用
        if method == "post":
            resp = requests.post(url, json=kwargs.get("json", {}), timeout=60)
        elif method == "get":
            resp = requests.get(url, params=kwargs.get("params", {}), timeout=60)
        elif method == "delete":
            resp = requests.delete(url, params=kwargs.get("params", {}), timeout=60)
        else:
            raise ValueError(f"不支持的 HTTP 方法: {method}")
        # 检查状态码
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        # 桥接服务未启动时的提示
        print(f"  [错误] 无法连接桥接服务: {BRIDGE_URL}")
        print(f"  请先启动: python 02_研发/agent_bridge.py")
        return {"success": False, "message": "connection_error"}


def contains_any(text: str, keywords) -> bool:
    return any(keyword in text for keyword in keywords)


def test_medical_scenario():
    """医疗复诊模拟：3 轮问诊 → 检索验证。"""
    print_section("医疗复诊模拟测试 — 患者张三")

    # ----------------------------------------------------------
    # 步骤 1: 清理测试数据（确保干净的测试环境）
    # ----------------------------------------------------------
    print("\n[准备] 清理历史测试数据...")
    call_api("delete", "/api/memory/reset", params={
        "domain": DOMAIN, "user_id": TEST_PATIENT_ID,
    })

    # ----------------------------------------------------------
    # 步骤 2: 第一轮问诊（初诊）
    # ----------------------------------------------------------
    print_section("第1轮：初诊 — 头痛 + 恶心")
    round1_conv = """
    医生：您好，请问今天哪里不舒服？
    患者：医生，我最近总是头痛，特别是下午的时候，有时候会恶心。
    医生：这种情况持续多久了？
    患者：大概一周了。
    医生：以前有过类似情况吗？
    患者：以前偶尔也会，但没有这次严重。
    医生：好的，我先给您开点布洛芬，如果三天没好转再来复诊。
    """

    # 调用桥接 API 处理本轮对话
    r1 = call_api("post", "/api/memory/process", json={
        "domain": DOMAIN,
        "user_id": TEST_PATIENT_ID,
        "conversation": round1_conv,
    })
    print(f"  写入结果: {r1.get('message', '失败')}")
    # 打印提取的结构化信息（如有）
    extracted = r1.get("data", {}).get("extracted", {})
    if extracted:
        print(f"  提取信息: {json.dumps(extracted, ensure_ascii=False, indent=2)}")

    # ----------------------------------------------------------
    # 步骤 3: 第二轮问诊（复诊 — 症状未好转）
    # ----------------------------------------------------------
    print_section("第2轮：复诊 — 头痛未缓解")
    round2_conv = """
    医生：张三，上次开的布洛芬效果怎么样？
    患者：吃了三天，头痛还是没有明显好转，而且今天早上还晕了一次。
    医生：晕倒的时候是什么感觉？
    患者：就是站起来的时候突然眼前一黑，差点摔倒。
    医生：你这可能不只是普通头痛，我给你开个CT检查，排除一下其他问题。
    患者：好的医生，我马上去做检查。
    """

    r2 = call_api("post", "/api/memory/process", json={
        "domain": DOMAIN,
        "user_id": TEST_PATIENT_ID,
        "conversation": round2_conv,
    })
    print(f"  写入结果: {r2.get('message', '失败')}")
    extracted2 = r2.get("data", {}).get("extracted", {})
    if extracted2:
        print(f"  提取信息: {json.dumps(extracted2, ensure_ascii=False, indent=2)}")

    # ----------------------------------------------------------
    # 步骤 4: 第三轮问诊（二次复诊 — CT结果）
    # ----------------------------------------------------------
    print_section("第3轮：二次复诊 — CT结果排查")
    round3_conv = """
    医生：张三，CT结果出来了，没有发现器质性病变，应该是紧张性头痛。
    患者：那就好，吓死我了。医生，那我应该注意什么？
    医生：重点是放松，不要熬夜。之前给你开的药继续吃，我再加一个改善睡眠的药。
    患者：好的，谢谢医生。对了，我对青霉素过敏，之前忘了说。
    医生：这个信息很重要！我记录一下，以后开药会注意。过敏信息已经更新到你的档案了。
    """

    r3 = call_api("post", "/api/memory/process", json={
        "domain": DOMAIN,
        "user_id": TEST_PATIENT_ID,
        "conversation": round3_conv,
    })
    print(f"  写入结果: {r3.get('message', '失败')}")
    # 打印摘要（验证摘要生成功能）
    summary = r3.get("data", {}).get("summary", "")
    if summary:
        print(f"  生成的摘要: {summary[:200]}...")

    # ----------------------------------------------------------
    # 步骤 5: 模拟新问诊 — 检索历史记忆
    # ----------------------------------------------------------
    print_section("验证：新问诊时检索历史记忆")
    new_query = "患者张三来复诊，头痛问题"

    search_result = call_api("get", "/api/memory/context", params={
        "domain": DOMAIN,
        "user_id": TEST_PATIENT_ID,
        "query": new_query,
        "top_k": 5,
    })

    # 检查检索结果
    memories = search_result.get("data", {}).get("memories", [])
    count = search_result.get("data", {}).get("count", 0)
    print(f"  检索到 {count} 条相关记忆")

    # 逐条展示记忆内容
    for i, mem in enumerate(memories, 1):
        print(f"\n  记忆 #{i}:")
        print(f"    内容: {mem.get('memory', 'N/A')[:120]}...")
        score = mem.get("score")
        if score:
            print(f"    相关度: {score:.4f}")

    # 打印生成的上下文提示词（完整版的前200字符）
    context_prompt = search_result.get("data", {}).get("context_prompt", "")
    print(f"\n  上下文提示词预览:")
    print(f"    {context_prompt[:400]}..." if len(context_prompt) > 400 else f"    {context_prompt}")

    # ----------------------------------------------------------
    # 步骤 6: 验证关键点 + 带记忆聊天回复
    # ----------------------------------------------------------
    print_section("验证结论")
    checks = []  # 检查项列表

    # 检查1: 至少检索到2条记忆（3轮问诊应有至少几条记忆）
    checks.append(("至少检索到 2 条记忆", count >= 2))

    # 检查2: 记忆内容应包含关键信息
    all_text = " ".join(m.get("memory", "") for m in memories)
    checks.append(("记忆包含'头痛'关键词", contains_any(all_text, ["头痛", "headache"])))
    checks.append(("记忆包含'过敏'关键词", contains_any(all_text, ["过敏", "青霉素", "allergy", "penicillin"])))
    checks.append(("记忆包含'CT检查'关键词", contains_any(all_text, ["CT", "检查", "scan"])))

    # 检查3: /api/chat 的最终回复体现历史记忆
    chat_result = call_api("post", "/api/chat", json={
        "domain": DOMAIN,
        "user_id": TEST_PATIENT_ID,
        "inject_memory": True,
        "memory_injected": False,
        "messages": [
            {"role": "system", "content": "你是一个医疗助手。"},
            {"role": "user", "content": "请结合我之前的情况，先概括我的过敏信息和做过的检查，再给我下一步建议。"}
        ]
    })
    reply_text = chat_result.get("reply", "")
    print(f"  带记忆回复预览: {reply_text[:200]}...")
    checks.append(("回复体现过敏史", contains_any(reply_text, ["青霉素", "过敏", "allergy", "penicillin"])))
    checks.append(("回复体现既往检查", contains_any(reply_text, ["CT", "检查", "scan"])))
    checks.append(("后端实际使用了历史记忆", chat_result.get("used_memory_count", 0) >= 1))

    # 输出检查结果
    all_passed = True
    for desc, passed in checks:
        status = "✅ 通过" if passed else "❌ 未通过"
        if not passed:
            all_passed = False
        print(f"  {status} — {desc}")

    # ----------------------------------------------------------
    # 步骤 7: 清理
    # ----------------------------------------------------------
    print_section("清理测试数据")
    call_api("delete", "/api/memory/reset", params={
        "domain": DOMAIN, "user_id": TEST_PATIENT_ID,
    })
    print("  测试数据已清理")

    # 返回测试结果
    print(f"\n{'='*60}")
    print(f"  测试结果: {'全部通过 ✅' if all_passed else '存在未通过项 ❌'}")
    print(f"{'='*60}")
    return all_passed


# ============================================================
# 入口
# ============================================================
if __name__ == "__main__":
    success = test_medical_scenario()
    # 用退出码表示测试结果，方便 CI 集成
    sys.exit(0 if success else 1)
