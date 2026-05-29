# -*- coding: utf-8 -*-
"""
ADSD 在线服务 - 短期记忆管理模块
负责维护对话的短期上下文记忆
主要功能：
1. 添加对话记录：保存用户和助手的对话内容及时间戳
2. 获取上下文：将最近的对话记录格式化为上下文文本
3. 获取最近提问：筛选出最近的用户提问
4. 清空记忆：重置对话上下文
"""
from datetime import datetime  # 导入datetime模块，用于记录每条对话的时间戳
from typing import List, Dict, Optional  # 导入类型提示，用于函数参数和返回值的类型注解


class ShortTermMemory:
    """短期记忆管理 - 维护对话上下文"""  # 类的文档字符串

    def __init__(self, max_turns: int = 12):
        """初始化短期记忆管理器

        Args:
            max_turns: 最大保留的对话轮数（默认12轮）
        """
        self.max_turns = max_turns  # 最大保留的对话轮数限制
        self.conversation = []  # 存储对话记录的列表

    def add(self, role: str, content: str, metadata: Optional[Dict] = None) -> None:
        """添加一条对话记录到记忆中

        Args:
            role: 角色（如"user"或"assistant"）
            content: 对话内容
            metadata: 附加的元数据（可选）
        """
        # 将新的对话记录添加到列表中
        self.conversation.append({
            "role": role,  # 发言人角色
            "content": content,  # 对话内容
            "timestamp": datetime.now().isoformat(),  # 添加当前时间戳（ISO格式）
            "metadata": metadata or {}  # 元数据，如果没有提供则使用空字典
        })
        # 如果对话记录超过最大轮数限制
        if len(self.conversation) > self.max_turns:
            # 只保留最后max_turns条记录（丢弃最早的记录）
            self.conversation = self.conversation[-self.max_turns:]

    def get_context(self, last_n: int = 6) -> str:
        """获取最近的对话上下文

        Args:
            last_n: 获取最近n条对话记录（默认6条）

        Returns:
            格式化的对话上下文字符串
        """
        # 将最近last_n条记录格式化为"角色: 内容"的形式，用换行符连接
        return "\n".join(f"{item['role']}: {item['content']}"
                         for item in self.conversation[-last_n:])

    def get_recent_questions(self, limit: int = 3) -> List[str]:
        """获取最近的用户提问

        Args:
            limit: 获取最近用户提问的数量限制（默认3条）

        Returns:
            用户提问内容列表
        """
        # 从对话记录中筛选出role为"user"的记录，提取content
        # 取最后limit条（最近的limit条用户提问）
        return [item["content"] for item in self.conversation
                if item["role"] == "user"][-limit:]

    def clear(self) -> None:
        """清空所有短期记忆"""  # 方法文档
        self.conversation = []  # 将对话列表重置为空列表
