# -*- coding: utf-8 -*-  # 指定源码使用 UTF-8 编码。
"""lesson_service.py - 智能备课场景服务模块。"""  # 说明当前文件职责。


class LessonService:  # 定义智能备课服务类。
    def __init__(self, llm_client, knowledge_service):  # 初始化智能备课服务。
        self.llm_client = llm_client  # 保存模型客户端实例。
        self.knowledge_service = knowledge_service  # 保存知识服务实例。

    def generate(self, payload: dict) -> dict:  # 生成备课结果结构。
        course = payload.get("course", "通用课程")  # 读取课程名称。
        topic = payload.get("topic", "核心知识点")  # 读取主题名称。
        audience = payload.get("audience", "高职学生")  # 读取目标学生群体。
        goal = payload.get("goal", "完成一节高质量教学设计")  # 读取教学目标。
        knowledge = self.knowledge_service.search(topic, course=course, top_k=3)  # 检索相关知识片段。
        prompt = self._build_prompt(course, topic, audience, goal, knowledge, payload.get("message", ""))  # 构造备课提示词。
        provider = payload.get("model_provider", "deepseek")  # 读取当前场景选择的模型服务商。
        content = self.llm_client.chat_text("你是一名资深职业教育教研专家。", prompt, provider=provider)  # 调用指定文本模型生成内容。
        return {  # 返回统一的备课结果结构。
            "scene": "lesson",  # 标记当前场景为智能备课。
            "title": f"{course} - {topic} 备课方案",  # 返回结果标题。
            "summary": content,  # 返回模型生成的备课正文。
            "knowledge": knowledge,  # 返回命中的知识片段。
            "cards": [  # 返回结构化展示卡片。
                {"label": "教学目标", "value": goal},  # 返回教学目标卡片。
                {"label": "目标对象", "value": audience},  # 返回学习对象卡片。
                {"label": "备课建议", "value": "建议结合案例讲授与任务驱动式练习。"},  # 返回方法建议卡片。
            ],  # 完成结果卡片列表。
        }  # 完成备课结果结构构建。

    def _build_prompt(self, course: str, topic: str, audience: str, goal: str, knowledge: list, message: str) -> str:  # 构造备课场景提示词。
        refs = "\n".join([f"- {item['topic']}：{item['summary']}" for item in knowledge]) or "- 暂无命中知识片段"  # 汇总知识参考片段。
        extra_need = message or "请结合课程目标输出完整教学方案。"  # 读取用户在文本框中的补充需求。
        return (  # 返回完整提示词文本。
            f"请围绕课程《{course}》的主题“{topic}”生成现代化备课方案。\n"  # 描述课程和主题。
            f"目标学生：{audience}。\n"  # 描述目标学生群体。
            f"教学目标：{goal}。\n"  # 描述教学目标。
            f"补充要求：{extra_need}\n"  # 注入用户的文本补充要求。
            "请输出：课程导入、教学流程、互动设计、练习设计、课堂评价、课后作业。\n"  # 约束输出结构。
            f"参考知识：\n{refs}"  # 注入知识片段内容。
        )  # 完成提示词构造。
