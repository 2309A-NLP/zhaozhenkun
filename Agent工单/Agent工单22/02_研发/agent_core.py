#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
02_研发 — 完整 Agent 框架（记忆 + 工具调用 + 任务规划）
==============================================================================
整合长期记忆 + 领域工具 + DeepSeek推理，构建真正的自主Agent。
具备: 记忆检索 → 任务规划 → 工具调用 → 结果观察 → 记忆存储 完整闭环。
启动: python agent_core.py  → 打开 http://localhost:8010
==============================================================================
"""

import json, sys, os, time, traceback  # 标准库
from typing import Dict, List, Callable, Any  # 类型注解
from dataclasses import dataclass, field  # 数据类
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llm_client import DeepSeekClient  # LLM客户端
from memory_processor import MemoryProcessor  # 记忆处理

# ============================================================
# 一、工具定义（三个领域的可调用工具）
# ============================================================
@dataclass
class Tool:
    """Agent可调用的工具定义。"""
    name: str  # 工具名称
    description: str  # 工具描述（LLM据此决定何时调用）
    parameters: Dict  # 参数schema（JSON Schema格式）
    handler: Callable  # 实际执行函数
    domain: str  # 所属领域

# 注册所有工具
TOOLS_REGISTRY: Dict[str, Tool] = {}

def register_tool(name, desc, params, domain):
    """装饰器：将函数注册为Agent可调用的工具。"""
    def decorator(func):
        TOOLS_REGISTRY[name] = Tool(name, desc, params, func, domain)
        return func
    return decorator

# ====== 医疗工具 ======
@register_tool("挂号预约", "在指定科室预约挂号", {"department":"科室","date":"日期","patient_name":"姓名"}, "medical")
def tool_register(department="内科", date="明天", patient_name="患者"):
    """挂号预约。"""
    return {"status": "ok", "appointment_id": f"APT{int(time.time())}",
            "message": f"已为{patient_name}预约{department}{date}的号"}

@register_tool("查询影像报告", "查询CT/X光/MRI检查结果", {"patient_id":"患者ID","exam_type":"CT/X光/MRI"}, "medical")
def tool_imaging(patient_id="", exam_type="CT"):
    """查询影像报告。"""
    return {"status": "ok", "patient_id": patient_id, "exam_type": exam_type,
            "report": f"{exam_type}未见明显异常，请结合临床判断。"}

@register_tool("开具处方", "为患者开具药品处方", {"patient_id":"患者ID","drugs":"药品","dosage":"用法用量"}, "medical")
def tool_prescribe(patient_id="", drugs="布洛芬", dosage="一次一片一日两次"):
    """开具处方。"""
    return {"status": "ok", "rx_id": f"RX{int(time.time())}",
            "message": f"处方：{drugs}，{dosage}"}

# ====== 文旅工具 ======
@register_tool("查询景点", "搜索推荐景点", {"destination":"目的地","preference":"偏好","budget":"预算"}, "tourism")
def tool_search_attractions(destination="三亚", preference="海边", budget="舒适"):
    """景点搜索。"""
    spots = {"三亚":["亚龙湾","天涯海角","蜈支洲岛"],"巴厘岛":["库塔海滩","乌布皇宫","海神庙"]}
    d = spots.get(destination, [f"{destination}景点1"])
    return {"destination": destination, "attractions": d[:5], "recommendation": f"推荐{d[0]}"}

@register_tool("预订行程", "预订旅行行程", {"destination":"目的地","check_in":"入住日期","days":"天数","guests":"人数"}, "tourism")
def tool_book_trip(destination="三亚", check_in="明天", days="3", guests="2"):
    """预订行程。"""
    return {"status": "ok", "booking_id": f"TRIP{int(time.time())}",
            "message": f"已预订{destination}{days}日行程，{guests}人"}

# ====== 教育工具 ======
@register_tool("出练习题", "根据薄弱点生成练习题", {"topic":"知识点","difficulty":"简单/中等/困难","count":"数量"}, "education")
def tool_generate_exercises(topic="函数求导", difficulty="中等", count="3"):
    """出题。"""
    return {"topic": topic, "difficulty": difficulty,
            "exercises": [f"求 f(x)=x²+3x 的导数", f"求 f(x)=2x³-5x+1 的导数"]}

@register_tool("评估答题", "评估答题结果并分析薄弱点", {"answers":"答案JSON","topic":"知识点"}, "education")
def tool_evaluate_answers(answers="{}", topic="函数求导"):
    """评估答题。"""
    return {"correct": 2, "total": 3, "accuracy": "67%",
            "weak_points": ["负号处理","链式法则"], "suggestion": "重点练习链式法则"}

# ============================================================
# 二、Agent 核心类
# ============================================================
class Agent:
    """具备记忆+工具调用+任务规划的完整Agent。循环: 感知→检索记忆→规划→调工具→观察→存储"""

    def __init__(self, domain: str, user_id: str, verbose: bool = True):
        """初始化Agent。domain: medical/tourism/education, user_id: 用户ID。"""
        self.domain = domain  # 领域
        self.user_id = user_id  # 用户ID
        self.verbose = verbose  # 日志开关
        self.llm = DeepSeekClient()  # LLM客户端
        self.memory = MemoryProcessor()  # 记忆处理器
        self.tools = self._get_domain_tools()  # 领域工具
        self._base_system = self._build_system_prompt()  # 系统提示词
        self._messages = []  # 当前对话

    def _log(self, msg: str):
        """打印日志(verbose模式)。"""
        if self.verbose:
            print(f"  [Agent] {msg}")

    def _get_domain_tools(self) -> List[Tool]:
        """获取领域工具列表。"""
        return [t for t in TOOLS_REGISTRY.values() if t.domain == self.domain]

    def _build_system_prompt(self) -> str:
        """构建System Prompt（工具说明+记忆占位）。"""
        td = "\n".join(f"- {t.name}: {t.description}，参数:{json.dumps(t.parameters,ensure_ascii=False)}" for t in self.tools)
        return f"""你是{self.domain}领域的智能Agent。自主决策，主动调用工具完成任务。

## 可用工具
{td}

## 工作方式
分析需求→参考记忆→如需调用工具则输出JSON→观察结果→决定下一步或回复用户

## 输出格式
调用工具: {{"action":"tool_call","tool":"工具名","params":{{...}}}}
回复用户: {{"action":"reply","content":"你的回复"}}

## 用户长期记忆
{{memory_context}}"""

    def _get_memory_context(self, query: str) -> str:
        """检索历史记忆上下文。"""
        try:
            memories = self.memory.retrieve_context(self.domain, self.user_id, query, top_k=5)
            return self.memory.build_context_prompt(memories, self.domain)
        except Exception:
            return "(记忆检索失败)"

    def run(self, user_input: str) -> str:
        """Agent主循环：检索记忆→LLM推理→工具调用→返回结果→存储记忆。"""
        self._log(f"收到: {user_input[:80]}...")

        # Step 1: 检索历史记忆
        memory_ctx = self._get_memory_context(user_input)
        self._log(f"记忆: 检索完成")

        # Step 2: 构建完整system prompt（注入记忆）
        system_prompt = self._base_system.replace("{memory_context}", memory_ctx)

        # Step 3: 初始化对话
        self._messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ]

        # Step 4: ReAct循环（最多5轮推理-行动）
        final_reply = "抱歉，我无法完成这个请求。"
        for turn in range(5):
            # 调用LLM推理
            response = self.llm.chat(self._messages, temperature=0.3, max_tokens=1000)
            self._log(f"思考回合{turn+1}: {response[:100]}...")

            # 解析LLM的决策
            action = self._parse_action(response)
            if not action:
                final_reply = response  # 无法解析，直接当回复
                break

            if action.get("action") == "reply":
                final_reply = action.get("content", response)
                break  # 任务完成，退出循环

            elif action.get("action") == "tool_call":
                # 执行工具调用
                tool_name = action.get("tool", "")
                params = action.get("params", {})
                tool_result = self._execute_tool(tool_name, params)
                self._log(f"工具调用: {tool_name} → {str(tool_result)[:80]}")
                # 将工具结果追加到对话中，让LLM继续推理
                self._messages.append({"role": "assistant", "content": response})
                self._messages.append({"role": "user",
                    "content": f"工具执行结果: {json.dumps(tool_result, ensure_ascii=False)}"})
            else:
                final_reply = response
                break  # 未知格式，退出

        # Step 5: 存储本轮对话到长期记忆
        conv_text = f"用户：{user_input}\nAgent：{final_reply}"
        try:
            self.memory.process_conversation(self.domain, self.user_id, conv_text)
            self._log("记忆已存储")
        except Exception:
            pass

        return final_reply

    def _parse_action(self, llm_response: str) -> Dict:
        """从LLM回复中解析出action JSON。"""
        try:
            # 尝试直接解析
            return json.loads(llm_response)
        except json.JSONDecodeError:
            pass
        # 尝试提取```json代码块
        import re
        m = re.search(r'\{[^{}]*"action"[^{}]*\}', llm_response, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return {"action": "reply", "content": llm_response}  # 解析失败，直接当回复

    def _execute_tool(self, tool_name: str, params: Dict) -> Dict:
        """执行工具调用。"""
        tool = TOOLS_REGISTRY.get(tool_name)
        if not tool:
            return {"error": f"未知工具: {tool_name}"}
        try:
            return tool.handler(**params) if params else tool.handler()
        except Exception as e:
            return {"error": str(e)}

    def list_memories(self) -> List:
        """列出用户全部记忆。"""
        return self.memory.get_all_memories(self.domain, self.user_id)

    def reset(self):
        """清空用户记忆。"""
        self.memory.reset_user_memory(self.domain, self.user_id)

# ============================================================
# 三、Agent Web 界面
# ============================================================
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse
import uvicorn

app = FastAPI(title="Agent 数字人")
_agents: Dict[str, Agent] = {}  # Agent实例缓存

@app.get("/", response_class=HTMLResponse)
def root():
    """读取前端HTML文件并返回。"""
    path = os.path.join(os.path.dirname(__file__), "..", "frontend", "agent.html")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>前端文件未找到</h1>"

@app.post("/api/agent/run")
async def api_agent_run(request: Request):
    """Agent主循环：接收用户消息，返回Agent回复+工具调用记录。"""
    body = await request.json()
    domain = body.get("domain", "medical")
    user_id = body.get("user_id", "default")
    message = body.get("message", "")
    # 获取或创建Agent实例
    key = f"{domain}:{user_id}"
    if key not in _agents:
        _agents[key] = Agent(domain, user_id, verbose=False)
    agent = _agents[key]
    # 执行Agent主循环
    reply = agent.run(message)
    # 收集工具调用信息（本轮内）
    tool_calls_log = []  # 简化：不追踪内部工具调用细节
    return {"reply": reply, "tool_calls": tool_calls_log,
            "domain": domain, "user_id": user_id}

@app.get("/api/agent/memories")
def api_agent_memories(domain: str, user_id: str):
    """列出Agent的用户记忆。"""
    key = f"{domain}:{user_id}"
    agent = _agents.get(key, Agent(domain, user_id, verbose=False))
    mems = agent.list_memories()
    return {"memories": mems, "count": len(mems)}

@app.delete("/api/agent/reset")
def api_agent_reset(domain: str, user_id: str):
    """清空Agent的用户记忆。"""
    key = f"{domain}:{user_id}"
    if key in _agents:
        _agents[key].reset()
    else:
        Agent(domain, user_id).reset()
    return {"ok": True}


# ============================================================
# 入口
# ============================================================
if __name__ == "__main__":
    print("=" * 55)
    print("  Agent 数字人 — 记忆+工具+规划")
    print("  浏览器打开: http://localhost:8010")
    print("=" * 55)
    uvicorn.run(app, host="0.0.0.0", port=8010)
