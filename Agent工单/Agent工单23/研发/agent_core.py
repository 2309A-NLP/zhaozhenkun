#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
研发 — Research Agent 核心模块 (ReAct 模式)
==============================================================================
功能: 基于 ReAct (Reasoning + Acting) 模式实现 Research Agent 核心循环。
      实现: 思考→行动→观察→(循环)→最终答案 的完整推理链。
      支持多轮搜索、网页内容抓取、答案归一化。
说明: 本模块是项目的核心，整合 LLM、搜索工具和提示词工程。
==============================================================================
"""
import json  # JSON 解析
import re  # 正则表达式
import sys  # 系统接口
import os  # 操作系统接口
import time  # 时间相关
from typing import Dict, List, Optional  # 类型注解

# 添加父目录到 sys.path，支持从任意目录运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 添加项目根目录

from 设计.prompts import RESEARCH_AGENT_SYSTEM_PROMPT  # 导入 System Prompt
from 研发.llm_client import DeepSeekClient  # 导入 LLM 客户端
from 研发.search_tools import web_search, web_fetch, format_search_results  # 导入搜索工具
from 研发.config import MAX_AGENT_TURNS, VERBOSE  # 导入配置


class ResearchAgent:  # Research Agent 主类
    """Research Agent，基于 ReAct 模式进行多步推理和信息检索。

    循环流程:
    1. Thought: LLM 分析当前状态，决定下一步
    2. Action: 执行搜索(search)或抓取(fetch)操作
    3. Observation: 将工具返回结果追加到上下文
    4. 重复 1-3 直到给出答案或达到最大轮数
    """

    def __init__(  # 初始化方法
        self,  # 实例自身
        llm_client: DeepSeekClient = None,  # LLM 客户端（可选，默认自动创建）
        max_turns: int = None,  # 最大推理轮数
        verbose: bool = None,  # 是否打印详细日志
    ):
        """初始化 Research Agent，设置 LLM 客户端和参数。"""
        self.llm = llm_client or DeepSeekClient()  # 创建或使用传入的 LLM 客户端
        self.max_turns = max_turns or MAX_AGENT_TURNS  # 设置最大轮数
        self.verbose = verbose if verbose is not None else VERBOSE  # 设置日志开关
        self.context: List[Dict] = []  # 当前推理上下文（收集的信息）
        self.turns: List[Dict] = []  # 每轮推理记录

    def _log(self, msg: str) -> None:  # 条件日志输出
        """如果 verbose 模式开启，打印日志信息。"""
        if self.verbose:  # 开启详细日志
            print(f"  [Agent] {msg}")  # 打印带前缀的日志

    def research(self, question: str) -> Dict:  # 核心研究方法
        """对给定问题执行 Research Agent 完整推理流程，返回包含答案和推理链的结果。

        Args:
            question: 用户提出的自然语言问题

        Returns:
            {"answer": "答案文本", "turns": [...], "total_turns": N, "success": bool}
        """
        self._log(f"收到问题: {question[:100]}...")  # 打印问题摘要

        # 重置状态
        self.context = []  # 清空上下文
        self.turns = []  # 清空轮次记录

        # 构建初始消息列表
        messages = [  # 对话消息
            {"role": "system", "content": RESEARCH_AGENT_SYSTEM_PROMPT},  # 系统提示词
            {"role": "user", "content": f"请回答以下问题:\n{question}"},  # 用户问题
        ]

        final_answer = ""  # 最终答案

        # ReAct 主循环
        for turn in range(self.max_turns):  # 最多 max_turns 轮
            self._log(f"--- 第 {turn + 1}/{self.max_turns} 轮推理 ---")  # 打印轮次

            # Step 1: 调用 LLM 进行思考和决策
            try:  # 尝试调用 LLM
                llm_response = self.llm.chat(messages)  # 调用 LLM
            except Exception as e:  # LLM 调用失败
                self._log(f"LLM 调用失败: {e}")  # 打印错误
                break  # 退出循环

            self._log(f"LLM 回复: {llm_response[:150]}...")  # 打印 LLM 回复摘要

            # Step 2: 解析 LLM 输出，提取 action JSON
            action = self._parse_action(llm_response)  # 解析 action

            if action is None:  # 无法解析
                self._log("无法解析 LLM 输出，尝试继续...")  # 打印警告
                # 将 LLM 原始回复作为上下文追加
                messages.append({"role": "assistant", "content": llm_response})  # 追加 assistant 消息
                messages.append({"role": "user", "content": "请按照 JSON 格式输出你的行动或答案。"})  # 提示格式
                continue  # 继续下一轮

            action_type = action.get("action", "")  # 获取动作类型

            # Step 3: 根据 action 类型执行不同操作
            if action_type == "answer":  # LLM 给出了最终答案
                final_answer = action.get("content", "")  # 提取答案
                self._log(f"获得最终答案: {final_answer[:100]}")  # 打印答案
                # 记录本轮
                self.turns.append({  # 记录推理轮次
                    "turn": turn + 1,  # 轮次编号
                    "action": "answer",  # 动作类型
                    "content": final_answer,  # 答案内容
                })
                break  # 退出循环

            elif action_type == "search":  # LLM 需要搜索
                query = action.get("query", "")  # 提取搜索关键词
                self._log(f"执行搜索: {query}")  # 打印搜索关键词

                search_result = web_search(query)  # 执行搜索
                formatted = format_search_results(search_result)  # 格式化搜索结果

                # 将搜索结果追加到上下文
                self.context.append({  # 记录上下文
                    "type": "search",  # 上下文类型
                    "query": query,  # 搜索词
                    "result": search_result,  # 原始结果
                })

                # 将本轮交互追加到消息列表
                messages.append({"role": "assistant", "content": llm_response})  # LLM 的搜索决策
                messages.append({"role": "user",  # 搜索结果（以 user 角色注入）
                    "content": f"搜索结果:\n{formatted}\n\n请继续推理或给出答案。"})  # 搜索结果文本

                self.turns.append({  # 记录推理轮次
                    "turn": turn + 1,  # 轮次编号
                    "action": "search",  # 动作类型
                    "query": query,  # 搜索词
                    "results_count": len(search_result.get("results", [])),  # 结果数量
                })

            elif action_type == "fetch":  # LLM 需要读取网页
                url = action.get("url", "")  # 提取目标 URL
                self._log(f"获取网页: {url[:80]}")  # 打印 URL

                fetch_result = web_fetch(url)  # 获取网页内容
                content_text = fetch_result.get("content", "") if fetch_result.get("success") else f"获取失败: {fetch_result.get('error')}"  # noqa: E501

                # 记录上下文
                self.context.append({  # 记录上下文
                    "type": "fetch",  # 上下文类型
                    "url": url,  # 来源 URL
                    "content": content_text[:1000],  # 截取前 1000 字符
                })

                # 追加到消息列表
                messages.append({"role": "assistant", "content": llm_response})  # LLM 的 fetch 决策
                messages.append({"role": "user",  # 网页内容
                    "content": f"网页内容 ({url}):\n{content_text}\n\n请继续推理或给出答案。"})  # 网页文本

                self.turns.append({  # 记录推理轮次
                    "turn": turn + 1,  # 轮次编号
                    "action": "fetch",  # 动作类型
                    "url": url,  # 目标 URL
                    "success": fetch_result.get("success", False),  # 是否成功
                })

            else:  # 未知 action 类型
                self._log(f"未知 action: {action_type}")  # 打印警告
                # 当作文本回复处理
                messages.append({"role": "assistant", "content": llm_response})
                continue  # 继续循环

        # 如果循环结束仍未获得答案，尝试让 LLM 基于已有上下文给出答案
        if not final_answer:  # 未获得答案
            self._log("强制生成答案...")  # 打印提示
            messages.append({"role": "user",  # 要求 LLM 基于已收集信息给出答案
                "content": "请基于以上的搜索和收集的所有信息，给出你对原始问题的最终答案。只输出答案本身，不需要解释。"})  # 强制回答提示
            try:  # 尝试获取答案
                final_answer = self.llm.chat(messages)  # 获取 LLM 回复
                # 尝试解析可能的 answer action
                action = self._parse_action(final_answer)  # 解析
                if action and action.get("action") == "answer":  # 是答案格式
                    final_answer = action.get("content", final_answer)  # 提取答案内容
            except Exception as e:  # 调用失败
                final_answer = f"研究未完成: {str(e)}"  # 错误信息

        return {  # 返回完整结果
            "answer": final_answer.strip(),  # 最终答案
            "turns": self.turns,  # 推理链
            "total_turns": len(self.turns),  # 总轮数
            "context_count": len(self.context),  # 上下文条目数
            "success": bool(final_answer),  # 是否成功
        }

    def _parse_action(self, text: str) -> Optional[Dict]:  # 解析 LLM 输出中的 action JSON
        """从 LLM 回复文本中解析出 action JSON 对象。

        Args:
            text: LLM 回复的原始文本

        Returns:
            解析出的 action dict，失败返回 None
        """
        # 策略1: 尝试直接 JSON 解析整段文本
        text_stripped = text.strip()  # 去除首尾空白
        if text_stripped.startswith("{"):  # 以 { 开头，可能是 JSON
            try:  # 尝试解析
                return json.loads(text_stripped)  # 直接解析
            except json.JSONDecodeError:  # 解析失败
                pass  # 继续尝试其他策略

        # 策略2: 提取 ```json 代码块中的内容
        json_block = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)  # 查找代码块
        if json_block:  # 找到代码块
            try:  # 尝试解析
                return json.loads(json_block.group(1).strip())  # 解析代码块内容
            except json.JSONDecodeError:  # 解析失败
                pass  # 继续尝试

        # 策略3: 用正则提取第一个 JSON 对象
        json_match = re.search(r'\{[^{}]*"action"\s*:\s*"[^"]*"[^{}]*\}', text)  # 查找含 action 的 JSON
        if json_match:  # 找到匹配
            try:  # 尝试解析
                return json.loads(json_match.group(0))  # 解析匹配到的 JSON
            except json.JSONDecodeError:  # 解析失败
                pass  # 继续尝试

        # 策略4: 更宽松的正则匹配
        json_match2 = re.search(r'\{.*?"action"\s*:\s*"(?:search|fetch|answer)".*?\}', text, re.DOTALL)  # 宽松匹配
        if json_match2:  # 找到匹配
            try:  # 尝试解析
                return json.loads(json_match2.group(0))  # 解析 JSON
            except json.JSONDecodeError:  # 解析失败
                pass  # 放弃

        return None  # 所有策略都失败，返回 None

    def answer_question(self, question: str) -> str:  # 简化接口
        """简化的问答接口：输入问题，输出答案字符串。"""
        result = self.research(question)  # 调用完整研究流程
        return result.get("answer", "")  # 只返回答案文本


# ============================================================
# 模块自检
# ============================================================
if __name__ == "__main__":  # 模块自检入口
    print("=" * 50)  # 分隔线
    print("  Research Agent — 自检测试")  # 标题
    print("=" * 50)  # 分隔线

    agent = ResearchAgent(verbose=True)  # 创建 Agent 实例

    # 简单测试问题
    test_question = "2024年巴黎奥运会的开幕式在哪个场馆举行？"  # 测试问题

    print(f"\n问题: {test_question}\n")  # 打印问题
    result = agent.research(test_question)  # 执行研究
    print(f"\n{'=' * 50}")  # 分隔线
    print(f"最终答案: {result['answer']}")  # 打印答案
    print(f"使用轮数: {result['total_turns']}")  # 打印轮数
    print(f"搜索次数: {result['context_count']}")  # 打印上下文数
