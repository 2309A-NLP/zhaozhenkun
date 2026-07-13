# -*- coding: utf-8 -*-  # 工单18：指定源码编码为 UTF-8。
"""services.py - 工单18智能助教的业务服务编排模块。"""  # 工单18：声明当前文件功能。

from __future__ import annotations  # 工单18：启用延迟类型注解。

from requests import RequestException  # 工单18：导入请求异常类型。

from app.config import now_text  # 工单18：导入当前时间函数。
from app.llm_client import llm_client  # 工单18：导入双模型客户端实例。
from app.retrieval import accessible_resources  # 工单18：导入可访问资源查询函数。
from app.retrieval import build_citations  # 工单18：导入引用构造函数。
from app.retrieval import search_resources  # 工单18：导入混合检索函数。
from app.state import load_state  # 工单18：导入状态加载函数。
from app.state import update_state  # 工单18：导入原子状态更新函数。

SYSTEM_PROMPT = (  # 工单18：定义统一系统提示词。
    "你是一名面向教育场景的智能助教。"  # 工单18：约束角色定位。
    "请给出准确、结构化、鼓励式回答。"  # 工单18：约束回答风格。
    "必须优先依据检索内容回答，并在答案末尾保留引用。"  # 工单18：约束回答依据。
)  # 工单18：结束系统提示词定义。


def _citation_label(citation: dict) -> str:  # 工单18：将结构化引用转为可读文本。
    return f"[{citation['scope']}] {citation['title']} · {'/'.join(citation['media_kinds'])} · {citation['location_text']}"  # 工单18：返回统一引用文本。


def build_user_prompt(question: str, refs: list[dict]) -> str:  # 工单18：构造助教问答提示词。
    ref_lines = []  # 工单18：初始化参考资料行列表。
    for index, item in enumerate(refs, start=1):  # 工单18：遍历检索结果。
        ref_lines.append(f"资料{index}（{item['scope']}，{','.join(item['media_kinds'])}，{item['location_text']}）：{item['title']}\n{item['snippet']}")  # 工单18：将每条检索结果转为提示词文本。
    refs_text = "\n\n".join(ref_lines) if ref_lines else "暂无命中资料。"  # 工单18：拼接参考资料文本。
    return f"用户问题：{question}\n参考资料：\n{refs_text}\n请按以下结构回答：1.核心解释 2.结合资料说明 3.常见误区 4.下一步练习建议。"  # 工单18：返回完整用户提示词。


def fallback_answer(question: str, refs: list[dict], provider: str) -> dict:  # 工单18：在远端模型不可用时返回兜底答案。
    bullet_refs = [_citation_label(item) for item in build_citations(refs)]  # 工单18：构造引用列表文本。
    answer = [  # 工单18：构造本地兜底回答内容。
        f"问题：{question}",  # 工单18：写入问题原文。
        "核心解释：系统已完成公共+私有知识混合检索，当前使用本地兜底回答。",  # 工单18：说明当前回答模式。
        "结合资料说明：优先建议阅读命中片段，再结合自己的私有笔记进行迁移理解。",  # 工单18：给出结合资料的学习建议。
        "常见误区：只记结论、不看原始材料；只看公共知识、不结合个人笔记。",  # 工单18：补充常见误区。
        "下一步练习建议：尝试基于一条私有笔记和一条公共资料，重新组织一次完整解释。",  # 工单18：给出练习建议。
        "引用：" + ("；".join(bullet_refs) if bullet_refs else "暂无"),  # 工单18：拼接引用文本。
    ]  # 工单18：结束兜底答案内容构造。
    return {"answer": "\n".join(answer), "provider": provider, "model": "local-fallback"}  # 工单18：返回兜底答案结构。


def answer_question(owner: dict, question: str, provider: str, top_k: int, use_public: bool, use_private: bool) -> dict:  # 工单18：执行业务级助教问答流程。
    refs = search_resources(owner, question, top_k, use_public, use_private)  # 工单18：执行公共+私有知识混合检索。
    prompt = build_user_prompt(question, refs)  # 工单18：根据问题和资料构造提示词。
    try:  # 工单18：开始调用远端模型。
        llm_result = llm_client.chat(provider, SYSTEM_PROMPT, prompt)  # 工单18：执行模型问答。
    except RequestException:  # 工单18：处理模型接口请求异常。
        llm_result = fallback_answer(question, refs, provider)  # 工单18：使用本地兜底回答。
    citations = build_citations(refs)  # 工单18：构造最终结构化引用列表。
    log_record = {"asked_at": now_text(), "user_id": owner["user_id"], "question": question, "provider": llm_result["provider"], "model": llm_result["model"], "citations": citations}  # 工单18：构造问答日志记录。
    update_state(lambda state: state["qa_logs"].append(log_record))  # 工单18：在原子写回流程中追加问答日志。
    return {"question": question, "answer": llm_result["answer"], "model_provider": llm_result["provider"], "model_name": llm_result["model"], "references": refs, "citations": citations}  # 工单18：返回问答结果。


def dashboard_for_user(owner: dict) -> dict:  # 工单18：构造当前用户工作台统计数据。
    resources = accessible_resources(owner)  # 工单18：读取当前用户全部可访问资源。
    state = load_state()  # 工单18：加载状态文件内容。
    private_count = sum(1 for item in resources if item["scope"] == "private")  # 工单18：统计私有资源条数。
    public_count = sum(1 for item in resources if item["scope"] == "public")  # 工单18：统计公共资源条数。
    my_logs = [item for item in state["qa_logs"] if item["user_id"] == owner["user_id"]]  # 工单18：筛选当前用户的问答日志。
    return {"display_name": owner["display_name"], "role": owner["role"], "private_resource_count": private_count, "public_resource_count": public_count, "qa_count": len(my_logs), "latest_questions": my_logs[-5:][::-1]}  # 工单18：返回工作台统计结构。
