#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
03_测试 — 文旅规划模拟测试
==============================================================================
测试场景：用户多次咨询旅行，验证智能体是否能结合其历史偏好
推荐新目的地，提供个性化的行程建议。
覆盖：偏好学习 × 2轮 → 个性化推荐验证 → 记忆检索验证
==============================================================================
"""

import json  # JSON 格式化输出
import sys  # 系统路径
import os  # 操作系统接口
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "02_研发"))

import requests  # HTTP 客户端


# ============================================================
# 测试配置
# ============================================================
BRIDGE_URL = os.getenv("BRIDGE_URL", "http://localhost:8008")  # 桥接 API 地址
TEST_USER_ID = "test_traveler_li_si_001"  # 测试用户的唯一 ID
DOMAIN = "tourism"  # 文旅领域


def print_section(title: str):
    """打印测试章节标题。"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def call_api(method: str, path: str, **kwargs) -> dict:
    """通用 API 调用封装。

    Args:
        method: HTTP 方法
        path: API 路径
        **kwargs: json 或 params 参数

    Returns:
        API 响应的 JSON 字典
    """
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


def test_tourism_scenario():
    """文旅偏好学习与推荐测试。"""
    print_section("文旅规划模拟测试 — 用户李四")

    # ----------------------------------------------------------
    # 步骤 1: 清理测试数据
    # ----------------------------------------------------------
    print("\n[准备] 清理历史数据...")
    call_api("delete", "/api/memory/reset", params={
        "domain": DOMAIN, "user_id": TEST_USER_ID,
    })

    # ----------------------------------------------------------
    # 步骤 2: 第一次旅行咨询（海边偏好）
    # ----------------------------------------------------------
    print_section("第1轮：首次咨询 — 海边度假偏好")
    round1_conv = """
    用户：你好，我想找个地方度假，有什么推荐吗？
    助手：您好！请问您喜欢什么类型的旅行呢？海边、山景还是城市？
    用户：我特别喜欢海边，最好是温暖的地方，不喜欢太冷。
    助手：了解。那您对预算有什么要求吗？
    用户：预算不是大问题，舒适就好。对了，我和家人一起去，有两个小孩。
    助手：家庭度假的话，三亚或者厦门都是不错的选择，适合亲子游。
    用户：三亚听起来不错！我喜欢海鲜，那边的海鲜应该很新鲜。
    """

    r1 = call_api("post", "/api/memory/process", json={
        "domain": DOMAIN, "user_id": TEST_USER_ID, "conversation": round1_conv,
    })
    print(f"  写入结果: {r1.get('message', '失败')}")
    summary = r1.get("data", {}).get("summary", "")
    if summary:
        print(f"  生成摘要: {summary[:150]}...")

    # ----------------------------------------------------------
    # 步骤 3: 第二次旅行咨询（历史偏好 + 新需求）
    # ----------------------------------------------------------
    print_section("第2轮：再次咨询 — 历史偏好 + 新目的地探索")
    round2_conv = """
    用户：上次你推荐的三亚很棒！我们一家玩得很开心。
    助手：很高兴您喜欢！这次有什么新的旅行计划吗？
    用户：嗯，想换个地方。还是海边，但这次想去国外看看。
    助手：好的，结合您之前的偏好，东南亚的海岛应该很适合。
    用户：对！泰国或者巴厘岛怎么样？还是一家人去，预算可以再高一些。
    助手：巴厘岛非常适合家庭度假，有很多亲子酒店和水上活动。泰国也很多海鲜美食。
    用户：那就巴厘岛吧！我比较喜欢深度游，不喜欢走马观花。
    """

    r2 = call_api("post", "/api/memory/process", json={
        "domain": DOMAIN, "user_id": TEST_USER_ID, "conversation": round2_conv,
    })
    print(f"  写入结果: {r2.get('message', '失败')}")
    summary2 = r2.get("data", {}).get("summary", "")
    if summary2:
        print(f"  生成摘要: {summary2[:150]}...")

    # ----------------------------------------------------------
    # 步骤 4: 第三次咨询 — 验证个性化推荐
    # ----------------------------------------------------------
    print_section("第3轮：新咨询 — 验证偏好记忆")
    # 用户提出模糊需求，智能体应基于历史偏好推荐
    new_query = "我想找一个适合家庭度假的温暖海滨目的地"

    search_result = call_api("get", "/api/memory/context", params={
        "domain": DOMAIN, "user_id": TEST_USER_ID, "query": new_query, "top_k": 5,
    })

    # 检查检索结果
    memories = search_result.get("data", {}).get("memories", [])
    count = search_result.get("data", {}).get("count", 0)
    print(f"  检索到 {count} 条相关记忆")

    # 逐条展示
    for i, mem in enumerate(memories, 1):
        print(f"\n  记忆 #{i}:")
        print(f"    内容: {mem.get('memory', 'N/A')[:150]}...")
        score = mem.get("score")
        if score:
            print(f"    相关度: {score:.4f}")

    # 展示上下文提示词
    context = search_result.get("data", {}).get("context_prompt", "")
    print(f"\n  上下文提示词 (前300字):")
    print(f"    {context[:300]}...")

    # ----------------------------------------------------------
    # 步骤 5: 验证检查 + 带记忆聊天回复
    # ----------------------------------------------------------
    print_section("验证结论")
    all_text = " ".join(m.get("memory", "") for m in memories)

    checks = [
        ("检索到至少 2 条偏好记忆", count >= 2),
        ("记忆包含'海边'偏好", contains_any(all_text, ["海边", "海滨", "beach"])),
        ("记忆包含'家庭'关键词", contains_any(all_text, ["家庭", "亲子", "家人", "family", "children"])),
        ("记忆包含'海鲜'饮食偏好", contains_any(all_text, ["海鲜", "seafood"])),
        ("记忆包含目的地推荐", contains_any(all_text, ["三亚", "巴厘岛", "Sanya", "Bali"])),
    ]

    chat_result = call_api("post", "/api/chat", json={
        "domain": DOMAIN,
        "user_id": TEST_USER_ID,
        "inject_memory": True,
        "memory_injected": False,
        "messages": [
            {"role": "system", "content": "你是一个旅行规划师。"},
            {"role": "user", "content": "请结合我之前的旅行偏好，推荐一个温暖、适合带孩子的海边目的地，并说明理由。"}
        ]
    })
    reply_text = chat_result.get("reply", "")
    print(f"  带记忆回复预览: {reply_text[:200]}...")
    checks.append(("回复体现海边偏好", contains_any(reply_text, ["海边", "海滨", "beach", "island", "海滩", "海岛"])))
    checks.append(("回复体现家庭出行", "孩子" in reply_text or "家庭" in reply_text or "亲子" in reply_text))
    checks.append(("后端实际使用了历史记忆", chat_result.get("used_memory_count", 0) >= 1))

    all_passed = True
    for desc, passed in checks:
        status = "✅ 通过" if passed else "❌ 未通过"
        if not passed:
            all_passed = False
        print(f"  {status} — {desc}")

    # ----------------------------------------------------------
    # 步骤 6: 列出所有记忆（验证完整性）
    # ----------------------------------------------------------
    print_section("所有记忆列表")
    list_result = call_api("get", "/api/memory/list", params={
        "domain": DOMAIN, "user_id": TEST_USER_ID,
    })
    all_memories = list_result.get("data", {}).get("memories", [])
    print(f"  共 {len(all_memories)} 条记忆:")
    for i, mem in enumerate(all_memories, 1):
        print(f"  {i}. {mem.get('memory', 'N/A')[:100]}...")

    # ----------------------------------------------------------
    # 步骤 7: 清理
    # ----------------------------------------------------------
    print_section("清理测试数据")
    call_api("delete", "/api/memory/reset", params={
        "domain": DOMAIN, "user_id": TEST_USER_ID,
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
    success = test_tourism_scenario()
    sys.exit(0 if success else 1)
