"""工单18：Agent 任务调度服务 — 负责多步骤导览任务的规划与执行。"""
import json
from services.llm_service import generate_answer
from services.knowledge_service import search_spots

# 工单18：预定义 Agent 工具集，每个工具是一个可调用的导览功能。
AGENT_TOOLS = {
    "search_spots": {
        "name": "搜索景点",
        "description": "根据关键词搜索知识库中的景点信息",
        "parameters": {"query": "搜索关键词"},
    },
    "recommend_route": {
        "name": "推荐路线",
        "description": "根据当前上下文推荐游览路线",
        "parameters": {"spots": "景点名称列表"},
    },
    "explain_detail": {
        "name": "详细讲解",
        "description": "对特定景点进行深度文化历史讲解",
        "parameters": {"spot_name": "景点名称", "aspect": "讲解角度(历史/建筑/文化/自然)"},
    },
    "interactive_quiz": {
        "name": "互动问答",
        "description": "根据当前讲解内容生成互动问题",
        "parameters": {"topic": "问答主题"},
    },
    "quick_summary": {
        "name": "快速概览",
        "description": "给出景点的快速概括介绍",
        "parameters": {"spot_name": "景点名称"},
    },
}

# 工单18：将工具定义转为 LLM 可理解的函数描述。
def build_tools_prompt() -> str:
    lines = ["可用工具："]
    for key, tool in AGENT_TOOLS.items():
        params = ", ".join(f"{k}: {v}" for k, v in tool["parameters"].items())
        lines.append(f"- {key}: {tool['description']} (参数: {params})")
    return "\n".join(lines)

# 工单18：解析 LLM 返回的工具调用，返回 (tool_name, params_dict)。
def parse_tool_call(text: str) -> tuple:
    text = text.strip()
    try:
        if "{" in text:
            start = text.index("{")
            end = text.rindex("}") + 1
            data = json.loads(text[start:end])
            return data.get("tool", ""), data.get("params", {})
    except (json.JSONDecodeError, ValueError):
        pass
    for tool_name in AGENT_TOOLS:
        if tool_name in text.lower():
            return tool_name, {}
    return "", {}

# 工单18：执行具体工具，返回结果文本。
def execute_tool(tool_name: str, params: dict) -> str:
    if tool_name == "search_spots":
        spots = search_spots(params.get("query", ""))
        return json.dumps([{"name": s["name"], "summary": s["summary"]} for s in spots], ensure_ascii=False)
    elif tool_name == "recommend_route":
        spots = search_spots(" ".join(params.get("spots", [])))
        names = [s["name"] for s in spots[:3]]
        return " → ".join(names) if names else "建议从主入口开始游览。"
    elif tool_name == "explain_detail":
        spots = search_spots(params.get("spot_name", ""))
        if spots:
            s = spots[0]
            return f"【{s['name']}】{s['details']}"
        return f"未找到「{params.get('spot_name', '')}」的详细信息。"
    elif tool_name == "interactive_quiz":
        topic = params.get("topic", "文旅知识")
        return f"关于「{topic}」的互动问答：你知道这里最著名的景点是什么吗？请说出你的答案！"
    elif tool_name == "quick_summary":
        spots = search_spots(params.get("spot_name", ""))
        return spots[0]["summary"] if spots else "暂无该景点信息。"
    return "工具执行完成。"

# 工单18：Agent 规划循环 — 让 LLM 决定调用哪些工具，执行后汇总结果。
def agent_plan_and_execute(settings: dict, task: str, language: str = "zh", max_steps: int = 3) -> dict:
    system_prompt = (
        f"你是文旅导览智能调度 Agent。根据游客任务，决定使用哪些工具。\n"
        f"{build_tools_prompt()}\n"
        f"回复格式：{{\"tool\": \"工具名\", \"params\": {{\"key\": \"value\"}}}} 或 {{\"done\": true, \"answer\": \"最终回复\"}}\n"
        f"使用{language}回复。"
    )
    history = [{"role": "system", "content": system_prompt}, {"role": "user", "content": f"任务：{task}"}]
    results = []
    for step in range(max_steps):
        prompt = "\n".join(f"{m['role']}: {m['content']}" for m in history)
        response = generate_answer(settings, system_prompt, f"{prompt}\n\n请决定下一步：")
        if "done" in response.lower() and "answer" in response.lower():
            try:
                data = json.loads(response[response.index("{"):response.rindex("}") + 1])
                return {"answer": data.get("answer", response), "steps": results, "tool_calls": len(results)}
            except (json.JSONDecodeError, ValueError):
                return {"answer": response, "steps": results, "tool_calls": len(results)}
        tool_name, params = parse_tool_call(response)
        if tool_name and tool_name in AGENT_TOOLS:
            tool_result = execute_tool(tool_name, params)
            results.append({"tool": tool_name, "params": params, "result": tool_result})
            history.append({"role": "assistant", "content": f"调用工具 {tool_name}，结果：{tool_result}"})
        else:
            break
    # 工单18：汇总所有工具结果生成最终回复
    if results:
        summary_prompt = f"根据以下工具执行结果，生成一段完整的导览回复：\n" + "\n".join(r["result"] for r in results)
        final = generate_answer(settings, system_prompt, f"工具结果汇总：\n{summary_prompt}\n请用{language}输出最终导览讲解。")
        return {"answer": final, "steps": results, "tool_calls": len(results)}
    return {"answer": "抱歉，我暂时无法完成这个任务。", "steps": results, "tool_calls": 0}
