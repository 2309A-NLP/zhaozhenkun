#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
02_研发 — 智能体集成适配器
==============================================================================
提供一行代码即可让已有智能体接入记忆系统的通用适配器。
支持: 医疗/文旅/教育/法律等任意领域智能体。

使用示例（3行代码完成记忆集成）:
    adapter = AgentAdapter("medical", "PAT001")
    context = adapter.before_turn("用户当前问题")   # 对话开始前检索记忆
    reply = your_llm.chat(context + user_message)   # 注入记忆上下文的LLM调用
    adapter.after_turn(user_message, reply)          # 对话结束后存储记忆

也可以独立运行测试: python agent_adapter.py
==============================================================================
"""

import json, sys, os, time  # 标准库
import requests  # HTTP客户端

# 默认API地址
API = os.getenv("MEMORY_API", "http://localhost:8008")


class AgentAdapter:
    """智能体记忆适配器 — 让已有Agent拥有长期记忆能力。

    封装了记忆系统的完整调用流程:
    1. before_turn(): 对话开始前 → 检索历史记忆 → 返回上下文提示词
    2. after_turn():  对话结束后 → 存储对话到mem0

    使用方式:
        adapter = AgentAdapter(domain="medical", user_id="PAT001")
        ctx = adapter.before_turn("头痛怎么办?")
        # 将 ctx 注入你的LLM system prompt
        adapter.after_turn("用户：头痛\n助手：建议休息..")
    """

    def __init__(self, domain: str, user_id: str,
                 api_url: str = None, verbose: bool = True):
        """初始化适配器。

        Args:
            domain: 领域代码 medical/tourism/education/legal/...
            user_id: 用户/患者/学生唯一标识
            api_url: 记忆API地址，默认 http://localhost:8008
            verbose: 是否打印日志
        """
        self.domain = domain  # 领域标识
        self.user_id = user_id  # 用户ID
        self.api = (api_url or API).rstrip("/")  # API地址
        self.verbose = verbose  # 日志开关
        self._conversation_turns = []  # 当前会话的对话轮次缓存

    def _log(self, msg: str):
        """打印日志（verbose模式）。"""
        if self.verbose:
            print(f"[MemoryAdapter] {msg}")

    # ----------------------------------------------------------
    # 对话前钩子：检索历史记忆
    # ----------------------------------------------------------
    def before_turn(self, user_query: str) -> str:
        """对话前调用：根据用户当前问题检索相关记忆。

        这个方法的返回值应该直接注入到LLM的system prompt中。

        Args:
            user_query: 用户当前的问题/消息文本

        Returns:
            格式化的记忆上下文提示词，可直接注入LLM的system prompt
            如: "【历史记忆】\n1. 用户偏好海边旅行\n2. 用户对海鲜过敏\n..."
        """
        try:
            # 调用记忆API检索历史上下文
            url = f"{self.api}/api/memory/context"
            resp = requests.get(url, params={
                "domain": self.domain,
                "user_id": self.user_id,
                "query": user_query,
                "top_k": 5,
            }, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            context = data.get("data", {}).get("context_prompt", "(无历史)")
            count = data.get("data", {}).get("count", 0)
            self._log(f"before_turn: 检索到{count}条相关记忆")
            return context
        except Exception as e:
            self._log(f"before_turn失败: {e}")
            return "(记忆检索失败，按无历史处理)"

    # ----------------------------------------------------------
    # 对话后钩子：存储对话记忆
    # ----------------------------------------------------------
    def after_turn(self, user_msg: str, assistant_reply: str):
        """对话后调用：将本轮对话存储到记忆系统。

        Args:
            user_msg: 用户本轮消息
            assistant_reply: 助手/智能体的回复
        """
        # 记录本轮对话
        turn_text = f"用户：{user_msg}\n助手：{assistant_reply}"
        self._conversation_turns.append(turn_text)

        try:
            # 异步存储不阻塞：合并所有轮次发到API
            full_conversation = "\n".join(self._conversation_turns)
            url = f"{self.api}/api/memory/process"
            requests.post(url, json={
                "domain": self.domain,
                "user_id": self.user_id,
                "conversation": full_conversation,
            }, timeout=30)
            self._log(f"after_turn: 已存储({len(self._conversation_turns)}轮)")
        except Exception as e:
            self._log(f"after_turn失败: {e}")

    # ----------------------------------------------------------
    # 记忆管理
    # ----------------------------------------------------------
    def list_memories(self) -> list:
        """列出该用户在此领域的所有记忆。"""
        try:
            url = f"{self.api}/api/memory/list"
            resp = requests.get(url, params={
                "domain": self.domain, "user_id": self.user_id,
            }, timeout=10)
            data = resp.json()
            return data.get("data", {}).get("memories", [])
        except Exception as e:
            self._log(f"list_memories失败: {e}")
            return []

    def reset_memories(self) -> bool:
        """清空该用户在此领域的所有记忆。"""
        try:
            url = f"{self.api}/api/memory/reset"
            resp = requests.delete(url, params={
                "domain": self.domain, "user_id": self.user_id,
            }, timeout=10)
            self._conversation_turns = []  # 同时清空本地缓存
            return resp.json().get("success", False)
        except Exception as e:
            self._log(f"reset_memories失败: {e}")
            return False

    def memory_count(self) -> int:
        """获取记忆数量。"""
        memories = self.list_memories()
        return len(memories) if memories else 0

    def clear_session(self):
        """清空当前会话的对话缓存（新会话时调用）。"""
        self._conversation_turns = []
        self._log("会话缓存已清空")


# ============================================================
# 使用示例：演示如何用适配器让已有Agent接入记忆系统
# ============================================================
class DemoAgent:
    """模拟一个已有的智能体（如法律/医疗/文旅Agent）。

    展示如何用3行代码（before_turn → LLM → after_turn）接入记忆系统。
    """

    def __init__(self, domain: str, user_id: str):
        """初始化Agent，创建记忆适配器。"""
        self.adapter = AgentAdapter(domain, user_id)  # ← 第1步：创建适配器

    def respond(self, user_msg: str) -> str:
        """处理用户消息并返回回复（模拟LLM调用）。"""
        # 第2步: 对话前检索记忆上下文
        context = self.adapter.before_turn(user_msg)

        # 第3步: 把记忆注入system prompt调用LLM（这里用echo模拟）
        system_prompt = (
            f"你是{self.adapter.domain}领域的智能助手。\n"
            f"以下是用户的历史信息，请据此提供个性化回复：\n{context}"
        )
        # ---- 实际使用时替换为真实的LLM调用 ----
        # reply = llm.chat([{"role":"system","content":system_prompt},
        #                    {"role":"user","content":user_msg}])
        reply = f"[模拟回复] 基于记忆上下文({self.adapter.memory_count()}条历史)，"
        reply += f"智能体对'{user_msg[:20]}...'的个性化回复。"
        # --------------------------------------

        # 第4步: 对话后存储记忆
        self.adapter.after_turn(user_msg, reply)
        return reply


# ============================================================
# 独立运行测试
# ============================================================
if __name__ == "__main__":
    print("=" * 55)
    print("  Agent集成适配器 — 演示测试")
    print("=" * 55)

    # 测试: 模拟一个医疗Agent，患者3轮咨询
    agent = DemoAgent("medical", "ADAPTER_TEST_001")

    # 先清理旧数据
    agent.adapter.reset_memories()

    questions = [
        "医生，我最近总是头痛，怎么办？",
        "上次开的药吃了还是痛，而且今天早上晕倒了。",
        "CT结果说没事，那我平时需要注意什么？",
    ]

    for i, q in enumerate(questions, 1):
        print(f"\n--- 第{i}轮 ---")
        # 检索记忆
        ctx = agent.adapter.before_turn(q)
        print(f"  记忆上下文: {ctx[:100]}...")
        # 模拟回复
        reply = agent.respond(q)
        print(f"  回复: {reply[:80]}...")
        time.sleep(0.5)  # 模拟思考时间

    # 查看所有记忆
    print(f"\n--- 最终记忆 ---")
    memories = agent.adapter.list_memories()
    for m in memories:
        print(f"  • {m.get('memory','')[:100]}...")

    # 清理
    agent.adapter.reset_memories()
    print(f"\n  适配器测试完成 ✅")
