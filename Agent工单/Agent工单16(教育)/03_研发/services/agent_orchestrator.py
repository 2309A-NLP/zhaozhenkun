# -*- coding: utf-8 -*-  # 指定源码使用 UTF-8 编码。
"""agent_orchestrator.py - 教育 Agent 的主业务编排模块。"""  # 说明当前文件职责。

from repositories.json_store import JsonStore  # 导入本地 JSON 仓储类。
from services.evaluation_service import EvaluationService  # 导入教学评估服务。
from services.knowledge_service import EducationKnowledgeService  # 导入教育知识服务。
from services.lesson_service import LessonService  # 导入智能备课服务。
from services.llm_client import LLMClient  # 导入统一模型客户端。
from services.multimodal_service import MultimodalService  # 导入多模态辅助服务。
from services.personalization_service import PersonalizationService  # 导入个性化学习服务。
from services.tutor_service import TutorService  # 导入智能助教服务。


class AgentOrchestrator:  # 定义教育 Agent 主编排器类。
    def __init__(self, settings: dict):  # 初始化主编排器。
        self.settings = settings  # 保存应用配置对象。
        self.llm_client = LLMClient(settings)  # 创建统一模型客户端实例。
        self.knowledge_service = EducationKnowledgeService(settings["KNOWLEDGE_PATH"])  # 创建知识服务实例。
        self.multimodal_service = MultimodalService(settings["UPLOAD_DIR"], settings["MAX_UPLOAD_MB"], self.llm_client)  # 创建多模态辅助服务实例。
        self.lesson_service = LessonService(self.llm_client, self.knowledge_service)  # 创建智能备课服务实例。
        self.tutor_service = TutorService(self.llm_client, self.knowledge_service)  # 创建智能助教服务实例。
        self.evaluation_service = EvaluationService(self.llm_client, self.multimodal_service)  # 创建教学评估服务实例。
        self.personalization_service = PersonalizationService(self.llm_client, self.knowledge_service)  # 创建个性化学习服务实例。
        self.course_store = JsonStore(settings["COURSES_PATH"], [])  # 创建课程仓储实例。
        self.student_store = JsonStore(settings["STUDENTS_PATH"], [])  # 创建学生仓储实例。
        self.session_store = JsonStore(settings["SESSIONS_PATH"], {})  # 创建会话仓储实例。
        self.artifact_store = JsonStore(settings["ARTIFACTS_PATH"], [])  # 创建产出仓储实例。

    def get_context(self) -> dict:  # 返回首页初始化所需的上下文数据。
        return {  # 返回统一的页面上下文结构。
            "courses": self.course_store.read(),  # 返回课程列表数据。
            "students": self.student_store.read(),  # 返回学生列表数据。
            "model_status": self.llm_client.get_status(),  # 返回模型状态信息。
        }  # 完成页面上下文构造。

    def execute_scene(self, scene: str, payload: dict, file_storage=None) -> dict:  # 按场景执行具体业务逻辑。
        image_path = ""  # 初始化上传图片路径。
        if file_storage and file_storage.filename:  # 当用户上传图片时先进行保存。
            image_path = self.multimodal_service.save_upload(file_storage)  # 保存图片并记录本地路径。
        if scene == "lesson":  # 当场景为智能备课时调用备课服务。
            result = self.lesson_service.generate(payload)  # 获取智能备课结果。
        elif scene == "tutor":  # 当场景为智能助教时调用助教服务。
            result = self._run_tutor(payload)  # 获取智能助教结果。
        elif scene == "evaluation":  # 当场景为教学评估时调用评估服务。
            result = self.evaluation_service.evaluate(payload, image_path=image_path)  # 获取教学评估结果。
        elif scene == "personalization":  # 当场景为个性化学习时调用学习方案服务。
            result = self._run_personalization(payload)  # 获取个性化学习结果。
        else:  # 当场景值不在支持范围内时拒绝执行。
            raise ValueError("不支持的业务场景")  # 抛出场景不支持异常。
        result["model_provider"] = payload.get("model_provider", self.settings.get("DEFAULT_MODEL_PROVIDER", "deepseek"))  # 回写本次实际使用的模型服务商。
        result["input_mode"] = "image" if image_path else "text"  # 回写本次输入模式。
        self.artifact_store.append_item({"scene": scene, "payload": payload, "result": result})  # 记录本次产出内容。
        return result  # 返回最终业务结果。

    def _run_tutor(self, payload: dict) -> dict:  # 运行智能助教场景并维护历史对话。
        session_id = payload.get("session_id", "default")  # 读取会话标识符。
        sessions = self.session_store.read()  # 读取历史会话记录。
        history = sessions.get(session_id, [])  # 读取当前会话历史内容。
        history.append({"role": "user", "content": payload.get("message", "")})  # 追加本轮用户消息。
        result = self.tutor_service.answer({**payload, "history": history})  # 调用助教服务生成回答。
        history.append({"role": "assistant", "content": result["answer"]})  # 追加本轮助手回答。
        sessions[session_id] = history[-12:]  # 仅保留最近若干轮会话内容。
        self.session_store.write(sessions)  # 将更新后的会话写回本地存储。
        result["history"] = sessions[session_id]  # 将最新会话历史回传给前端。
        return result  # 返回带历史的助教结果。

    def _run_personalization(self, payload: dict) -> dict:  # 运行个性化学习场景。
        student_id = payload.get("student_id")  # 读取目标学生编号。
        student = self._find_student(student_id)  # 按编号读取学生画像。
        return self.personalization_service.build_plan(payload, student)  # 返回个性化学习方案。

    def _find_student(self, student_id: str) -> dict:  # 根据学生编号查找学生画像。
        for student in self.student_store.read():  # 遍历全部学生记录。
            if student.get("id") == student_id:  # 当学生编号匹配时返回记录。
                return student  # 返回命中的学生画像。
        raise ValueError("未找到对应学生信息")  # 当没有命中学生时抛出异常。
