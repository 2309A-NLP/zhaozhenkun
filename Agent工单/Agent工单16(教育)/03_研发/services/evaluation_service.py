# -*- coding: utf-8 -*-  # 指定源码使用 UTF-8 编码。
"""evaluation_service.py - 教学评估场景服务模块。"""  # 说明当前文件职责。


class EvaluationService:  # 定义教学评估服务类。
    def __init__(self, llm_client, multimodal_service):  # 初始化教学评估服务。
        self.llm_client = llm_client  # 保存模型客户端实例。
        self.multimodal_service = multimodal_service  # 保存多模态辅助服务实例。

    def evaluate(self, payload: dict, image_path: str = "") -> dict:  # 生成教学评估结果。
        task_name = payload.get("task_name", "课堂作业")  # 读取作业名称。
        text_answer = payload.get("message") or payload.get("content", "")  # 优先读取文本交互内容并兼容历史字段。
        provider = payload.get("model_provider", "deepseek")  # 读取当前场景选择的模型服务商。
        prompt = self._build_prompt(task_name, text_answer)  # 构造评估提示词。
        if image_path:  # 当存在图片作业时调用多模态分析。
            content = self.multimodal_service.analyze_homework_image(prompt, image_path, provider=provider)  # 获取图片评估结果。
        else:  # 当没有图片时走文本评估路径。
            content = self.llm_client.chat_text("你是一名严谨且鼓励式的教学评估助手。", prompt, provider=provider)  # 调用指定文本模型生成评估结果。
        return {  # 返回统一的评估结果结构。
            "scene": "evaluation",  # 标记当前场景为教学评估。
            "title": f"{task_name} 评估结果",  # 返回结果标题。
            "feedback": content,  # 返回评估与讲解正文。
            "scores": [  # 返回结构化评分卡片。
                {"label": "知识理解", "value": "良好"},  # 返回知识理解状态。
                {"label": "逻辑表达", "value": "可提升"},  # 返回逻辑表达状态。
                {"label": "纠错建议", "value": "重点复习易错步骤"},  # 返回纠错建议内容。
            ],  # 完成评分卡片列表。
        }  # 完成评估结果构建。

    def _build_prompt(self, task_name: str, text_answer: str) -> str:  # 构造评估场景提示词。
        return (  # 返回完整提示词文本。
            f"请对“{task_name}”进行教学化评估。\n"  # 描述当前评估任务。
            f"学生作答内容：{text_answer or '图片作业待识别'}\n"  # 注入作答内容或图片待识别提示。
            "请输出：整体评价、主要错误、正确思路、针对性改进建议。"  # 约束输出结构。
        )  # 完成提示词构造。
