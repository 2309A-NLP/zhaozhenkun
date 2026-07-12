# -*- coding: utf-8 -*-  # 指定源码使用 UTF-8 编码。
"""personalization_service.py - 个性化学习场景服务模块。"""  # 说明当前文件职责。


class PersonalizationService:  # 定义个性化学习服务类。
    def __init__(self, llm_client, knowledge_service):  # 初始化个性化学习服务。
        self.llm_client = llm_client  # 保存模型客户端实例。
        self.knowledge_service = knowledge_service  # 保存知识服务实例。

    def build_plan(self, payload: dict, student: dict) -> dict:  # 生成学生个性化学习方案。
        focus = payload.get("focus", "巩固薄弱知识点")  # 读取学习聚焦目标。
        course = payload.get("course", "")  # 读取课程名称。
        knowledge = self.knowledge_service.search(focus, course=course, top_k=3)  # 检索相关知识片段。
        provider = payload.get("model_provider", "deepseek")  # 读取当前场景选择的模型服务商。
        prompt = self._build_prompt(student, focus, knowledge, payload.get("message", ""))  # 构造个性化学习提示词。
        content = self.llm_client.chat_text("你是一名擅长因材施教的学习规划师。", prompt, provider=provider)  # 调用指定文本模型生成学习方案。
        return {  # 返回统一的个性化学习结果结构。
            "scene": "personalization",  # 标记当前场景为个性化学习。
            "student_name": student.get("name", "未命名学生"),  # 返回学生姓名。
            "profile": student,  # 返回完整学生画像。
            "plan": content,  # 返回个性化学习方案正文。
            "knowledge": knowledge,  # 返回命中的知识片段。
            "highlights": [  # 返回关键摘要信息。
                {"label": "学习风格", "value": student.get("learning_style", "混合型")},  # 返回学习风格标签。
                {"label": "薄弱点", "value": "、".join(student.get("weak_points", [])) or "暂无"},  # 返回薄弱点标签。
                {"label": "学习目标", "value": "、".join(student.get("study_goals", [])) or "待补充"},  # 返回学习目标标签。
            ],  # 完成关键摘要列表。
        }  # 完成个性化结果构建。

    def _build_prompt(self, student: dict, focus: str, knowledge: list, message: str) -> str:  # 构造个性化学习提示词。
        refs = "\n".join([f"- {item['topic']}：{item['summary']}" for item in knowledge]) or "- 暂无参考知识"  # 汇总知识片段。
        extra_need = message or "请输出适合当前学生的个性化学习建议。"  # 读取用户在文本框中的补充需求。
        return (  # 返回完整提示词文本。
            f"请为学生 {student.get('name', '未命名学生')} 生成个性化学习方案。\n"  # 注入学生基本信息。
            f"学习风格：{student.get('learning_style', '混合型')}。\n"  # 注入学习风格信息。
            f"薄弱知识点：{'、'.join(student.get('weak_points', [])) or '暂无'}。\n"  # 注入薄弱点信息。
            f"学习目标：{'、'.join(student.get('study_goals', [])) or '待补充'}。\n"  # 注入学习目标信息。
            f"当前聚焦：{focus}。\n"  # 注入当前聚焦主题。
            f"补充要求：{extra_need}\n"  # 注入用户的文本补充要求。
            f"参考知识：\n{refs}\n"  # 注入知识片段内容。
            "请输出：周学习目标、每日行动、练习策略、评估方式、教师跟进建议。"  # 约束输出结构。
        )  # 完成提示词构造。
