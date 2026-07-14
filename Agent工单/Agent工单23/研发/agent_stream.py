#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
研发 — Research Agent 流式推理模块
==============================================================================
功能: 在 agent_core.ResearchAgent 基础上封装流式 SSE 输出。
      将 ReAct 推理每一步通过 Generator yield 事件，供 SSE 端点实时推送。
说明: 继承 ResearchAgent，添加 research_stream() 生成器方法。
==============================================================================
"""
import json  # JSON 解析
import re  # 正则
import sys  # 系统接口
import os  # 操作系统
import time  # 时间
from typing import Dict, List, Generator  # 类型注解

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 项目根目录

from 设计.prompts import RESEARCH_AGENT_SYSTEM_PROMPT  # System Prompt
from 研发.llm_client import DeepSeekClient  # LLM 客户端
from 研发.search_tools import web_search, web_fetch, format_search_results  # 搜索工具
from 研发.config import MAX_AGENT_TURNS, VERBOSE  # 配置


class StreamAgent:  # 流式 Agent 封装
    """在 ResearchAgent 基础上提供流式推理能力，通过 yield 逐事件推送进度。

    用法:
        agent = StreamAgent()
        for event in agent.research_stream(question):
            send_to_client(event)  # 推送到前端
        result = agent.final_result  # 获取最终结果
    """

    def __init__(self, llm_client: DeepSeekClient = None, max_turns: int = None):  # 初始化
        """初始化流式 Agent。"""
        self.llm = llm_client or DeepSeekClient()  # LLM 客户端
        self.max_turns = max_turns or MAX_AGENT_TURNS  # 最大轮数
        self.final_result: Dict = {}  # 最终结果（流结束后填充）

    def _log(self, msg: str) -> None:  # 条件日志
        """Verbose 模式日志输出。"""
        if VERBOSE:  # 开启日志
            print(f"  [Agent] {msg}")  # 打印

    def _parse_action(self, text: str) -> Dict:  # 解析 LLM 输出的 action JSON
        """从 LLM 回复中提取 action JSON，失败返回 None。"""
        text = text.strip()  # 去空白
        if text.startswith("{"):  # 可能是 JSON
            try:  # 直接解析
                return json.loads(text)  # 返回解析结果
            except json.JSONDecodeError:  # 失败
                pass  # 继续

        # 提取 ```json 代码块
        m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)  # 查找代码块
        if m:  # 找到
            try:  # 尝试解析
                return json.loads(m.group(1).strip())  # 返回
            except json.JSONDecodeError:  # 失败
                pass  # 继续

        # 正则提取含 action 的 JSON 对象
        for pat in [  # 多级正则
            r'\{[^{}]*"action"\s*:\s*"[^"]*"[^{}]*\}',  # 严格
            r'\{.*?"action"\s*:\s*"(?:search|answer|fetch)".*?\}',  # 宽松
        ]:
            m = re.search(pat, text, re.DOTALL)  # 搜索
            if m:  # 找到
                try:  # 尝试解析
                    return json.loads(m.group(0))  # 返回
                except json.JSONDecodeError:  # 失败
                    pass  # 继续

        return {}  # 全部失败，返回空字典

    def research_stream(self, question: str, lang: str = "auto") -> Generator[Dict, None, None]:  # 流式推理生成器
        """对问题执行流式推理，yield 进度事件。

        Yield 事件:
          {"type": "start", "question": "..."}
          {"type": "thinking", "turn": N}
          {"type": "searching", "turn": N, "query": "..."}
          {"type": "results", "turn": N, "query": "...", "count": N}
          {"type": "answer", "content": "...", "turns": N, "elapsed": S}
          {"type": "error", "content": "..."}
        """
        self._log(f"问题: {question[:100]}...")  # 日志
        t_start = time.time()  # 计时开始

        yield {"type": "start", "question": question}  # 开始事件

        # 根据语言偏好构建搜索语言提示
        lang_hint = ""  # 语言提示
        if lang == "zh":  # 中文搜索
            lang_hint = "请用中文进行搜索"  # 中文提示
        elif lang == "en":  # 英文搜索
            lang_hint = "Please search in English"  # 英文提示
        else:  # 自动
            lang_hint = "搜索语言中英文均可"  # 自动提示

        # 构建消息
        messages = [  # 初始消息列表
            {"role": "system", "content": RESEARCH_AGENT_SYSTEM_PROMPT},  # 系统提示
            {"role": "user", "content": f"{lang_hint}\n回答问题（尽量1-2次搜索内给出答案）:\n{question}"},  # 用户问题含语言偏好
        ]

        final_answer = ""  # 答案
        turns_record = []  # 轮次记录

        # ReAct 循环
        for turn in range(self.max_turns):  # 最多 max_turns 轮
            yield {"type": "thinking", "turn": turn + 1}  # 思考事件

            # LLM 调用（低温度 + 限制 token 加速）
            try:  # 调用 LLM
                reply = self.llm.chat(messages, temperature=0.1, max_tokens=800)  # 快速调用
            except Exception as e:  # 失败
                yield {"type": "error", "content": f"LLM错误: {e}"}  # 错误事件
                break  # 退出

            self._log(f"第{turn+1}轮: {reply[:120]}")  # 日志
            action = self._parse_action(reply)  # 解析 action

            if not action:  # 无法解析
                messages.append({"role": "assistant", "content": reply})  # 追加
                messages.append({"role": "user", "content": "请输出JSON: {\"action\":\"search\",...} 或 {\"action\":\"answer\",...}"})  # 提示
                continue  # 继续

            act_type = action.get("action", "")  # 动作类型

            if act_type == "answer":  # 获得答案
                final_answer = action.get("content", "")  # 提取
                elapsed = round(time.time() - t_start, 1)  # 耗时
                turns_record.append({"turn": turn + 1, "action": "answer"})  # 记录
                yield {"type": "answer", "content": final_answer,  # 答案事件
                       "turns": turn + 1, "elapsed": elapsed}
                break  # 完成

            elif act_type == "search":  # 搜索
                query = action.get("query", "")  # 搜索词
                yield {"type": "searching", "turn": turn + 1, "query": query}  # 搜索事件

                s_result = web_search(query)  # 执行搜索
                formatted = format_search_results(s_result)  # 格式化
                n_results = len(s_result.get("results", []))  # 结果数

                yield {"type": "results", "turn": turn + 1,  # 结果事件
                       "query": query, "count": n_results}

                messages.append({"role": "assistant", "content": reply})  # LLM 决策
                messages.append({"role": "user",  # 搜索结果
                    "content": f"搜索结果({n_results}条):\n{formatted}\n\n从摘要中直接提取答案回答。"})  # 引导快速回答
                turns_record.append({"turn": turn + 1, "action": "search", "query": query})  # 记录

            elif act_type == "fetch":  # 抓取网页
                url = action.get("url", "")  # URL
                yield {"type": "fetching", "turn": turn + 1, "url": url}  # 抓取事件

                f_result = web_fetch(url)  # 抓取
                content = f_result.get("content", "") if f_result.get("success") else f"失败: {f_result.get('error')}"  # noqa: E501

                messages.append({"role": "assistant", "content": reply})  # LLM 决策
                messages.append({"role": "user",  # 网页内容
                    "content": f"网页内容:\n{content[:2000]}\n\n请基于以上信息回答。"})  # 截断
                turns_record.append({"turn": turn + 1, "action": "fetch", "url": url})  # 记录

            else:  # 未知
                messages.append({"role": "assistant", "content": reply})  # 追加
                continue  # 继续

        # 未获得答案时强制生成
        if not final_answer:  # 循环耗尽
            yield {"type": "thinking", "turn": -1}  # 强制思考
            messages.append({"role": "user",  # 强制回答
                "content": "基于以上所有信息，给出最终答案。JSON格式: {\"action\":\"answer\",\"content\":\"...\"}"})  # 强制提示
            try:  # 调用 LLM
                resp = self.llm.chat(messages, temperature=0.0, max_tokens=400)  # 最低温度
                act = self._parse_action(resp)  # 解析
                if act and act.get("action") == "answer":  # 成功
                    final_answer = act.get("content", resp)  # 提取
                else:  # 失败
                    final_answer = resp.strip()[:200]  # 直接用
            except Exception as e:  # 异常
                yield {"type": "error", "content": str(e)}  # 错误事件
                final_answer = ""  # 空答案

            elapsed = round(time.time() - t_start, 1)  # 耗时
            yield {"type": "answer", "content": final_answer,  # 答案事件
                   "turns": len(turns_record), "elapsed": elapsed}

        # 保存最终结果
        self.final_result = {  # 最终结果
            "answer": final_answer.strip(),  # 答案
            "turns": turns_record,  # 推理链
            "total_turns": len(turns_record),  # 总轮数
            "elapsed": round(time.time() - t_start, 1),  # 总耗时
            "success": bool(final_answer),  # 成功标志
        }
