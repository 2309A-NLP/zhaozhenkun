"""
short_term_memory.py - RAG工单6 多轮对话记忆模块
需求: 交互友好性 — 支持多轮对话，维护会话历史
功能: 基于session_id的对话历史管理，自动截断保留最近N轮
"""
import logging, time
from config import LOG_FMT, LOG_DATEFMT

logging.basicConfig(format=LOG_FMT, datefmt=LOG_DATEFMT, level=logging.INFO)
logger = logging.getLogger("short_term_memory")


class ShortTermMemory:
    """短时记忆：按session_id存储对话历史，自动保留最近max_turns轮"""

    def __init__(self, max_turns=5):
        self.sessions: dict[str, list] = {}
        self.max_turns = max_turns

    def add_message(self, session_id: str, role: str, content: str):
        """添加一条消息，自动淘汰旧轮次"""
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        self.sessions[session_id].append({"role": role, "content": content})
        # 只保留最近max_turns轮（每轮=user+assistant）
        history = self.sessions[session_id]
        max_msgs = self.max_turns * 2
        if len(history) > max_msgs:
            self.sessions[session_id] = history[-max_msgs:]

    def get_history(self, session_id: str) -> list:
        """获取指定session的完整对话历史"""
        return self.sessions.get(session_id, [])

    def get_recent_messages(self, session_id: str, n: int = 3) -> list:
        """获取最近n轮对话（每轮2条）"""
        history = self.sessions.get(session_id, [])
        return history[-(n * 2):]

    def clear(self, session_id: str):
        """清空指定session"""
        self.sessions.pop(session_id, None)

    def format_for_prompt(self, session_id: str, max_rounds: int = 3) -> str:
        """将最近对话历史格式化为字符串，供LLM prompt注入"""
        msgs = self.get_recent_messages(session_id, max_rounds)
        if not msgs:
            return ""
        parts = []
        for m in msgs:
            prefix = "用户" if m["role"] == "user" else "助手"
            parts.append(f"{prefix}: {m['content'][:200]}")
        return "\n".join(parts)


# 全局单例
memory = ShortTermMemory(max_turns=5)
