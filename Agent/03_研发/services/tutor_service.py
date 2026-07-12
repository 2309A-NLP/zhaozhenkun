# -*- coding: utf-8 -*-  # 指定源码使用 UTF-8 编码。
"""tutor_service.py - 智能助教场景服务模块。"""  # 说明当前文件职责。


class TutorService:  # 定义智能助教服务类。
    def __init__(self, llm_client, knowledge_service):  # 初始化智能助教服务。
        self.llm_client = llm_client  # 保存模型客户端实例。
        self.knowledge_service = knowledge_service  # 保存知识服务实例。

    def answer(self, payload: dict) -> dict:  # 生成智能助教问答结果。
        question = payload.get("message", "请解释这个知识点")  # 读取用户问题文本。
        course = payload.get("course", "")  # 读取课程名称。
        history = payload.get("history", [])[-6:]  # 截取最近几轮历史消息。
        knowledge = self.knowledge_service.search(question, course=course, top_k=3)  # 检索相关知识片段。
        provider = payload.get("model_provider", "deepseek")  # 读取当前场景选择的模型服务商。
        prompt = self._build_prompt(question, history, knowledge)  # 构造助教提示词。
        content = self.llm_client.chat_text("你是一名耐心、结构化、鼓励式的智能助教。", prompt, provider=provider)  # 调用指定文本模型生成回答。
        return {  # 返回统一的助教结果结构。
            "scene": "tutor",  # 标记当前场景为智能助教。
            "answer": content,  # 返回问答结果文本。
            "knowledge": knowledge,  # 返回命中的知识片段。
            "tips": ["先理解概念，再完成一道变式练习。", "建议把易错点整理进错题本。"],  # 返回辅助学习建议。
        }  # 完成助教结果构建。

    def _build_prompt(self, question: str, history: list, knowledge: list) -> str:  # 构造助教场景提示词。
        history_lines = []  # 初始化历史消息文本列表。
        for item in history:  # 遍历最近历史消息。
            role = item.get("role", "user")  # 读取消息角色。
            history_lines.append(f"{role}: {item.get('content', '')}")  # 格式化为单行历史文本。
        refs = "\n".join([f"- {item['topic']}：{item['summary']}" for item in knowledge]) or "- 暂无参考知识"  # 汇总知识片段。
        history_text = "\n".join(history_lines) or "无"  # 汇总历史对话文本。
        return (  # 返回完整提示词文本。
            "请用分步骤、鼓励式、适合高职学生理解的方式回答问题。\n"  # 约束回答风格。
            f"历史对话：\n{history_text}\n"  # 注入历史上下文。
            f"当前问题：{question}\n"  # 注入当前问题。
            f"参考知识：\n{refs}\n"  # 注入知识片段。
            "请包含：核心解释、常见误区、一个练习建议。"  # 约束回答结构。
        )  # 完成提示词构造。
