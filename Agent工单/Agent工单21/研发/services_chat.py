"""文件功能：完成知识召回、多模态补充、会话记忆和 DeepSeek 问答主流程。"""

from __future__ import annotations  # 启用延后类型注解支持。

from pathlib import Path  # 处理图片素材本地路径。

from 设计.architecture import AppSettings  # 导入应用配置类型。
from 设计.prompts import build_dialogue_system_prompt  # 导入问答系统提示词构造函数。
from 设计.prompts import build_visual_prompt  # 导入图像理解提示词构造函数。
from 设计.schemas import ChatMessageRecord  # 导入会话消息结构。
from 设计.schemas import ChatSessionRecord  # 导入会话结构。
from 研发.clients_llm import ModelClient  # 导入统一模型客户端。
from 研发.repositories_local import ProjectRepository  # 导入项目仓储。
from 优化.prompt_optimizer import PromptOptimizer  # 导入提示词优化器。
from 优化.retrieval_optimizer import RetrievalOptimizer  # 导入召回优化器。


class ChatService:  # 定义会话问答服务。
    def __init__(self, settings: AppSettings, repository: ProjectRepository, model_client: ModelClient, retrieval_optimizer: RetrievalOptimizer, prompt_optimizer: PromptOptimizer) -> None:  # 初始化问答服务。
        self.settings = settings  # 保存全局配置。
        self.repository = repository  # 保存仓储对象。
        self.model_client = model_client  # 保存模型客户端。
        self.retrieval_optimizer = retrieval_optimizer  # 保存召回优化器。
        self.prompt_optimizer = prompt_optimizer  # 保存提示词优化器。

    def _ensure_session(self, persona_id: str, session_id: str) -> dict[str, object]:  # 获取或创建会话。
        if session_id:  # 如果调用方传入了会话主键。
            stored = self.repository.chat_sessions.get_item("session_id", session_id)  # 读取目标会话。
            if stored is not None:  # 如果会话存在。
                return stored  # 直接返回会话记录。
        session = ChatSessionRecord(persona_id=persona_id, title="数字人对话")  # 创建新会话对象。
        return self.repository.save_session(session)  # 保存并返回新会话记录。

    def ask(self, persona_id: str, question: str, session_id: str = "", image_asset_id: str = "") -> dict[str, object]:  # 执行一次问答流程。
        persona = self.repository.personas.get_item("persona_id", persona_id)  # 读取数字人画像。
        if persona is None:  # 如果数字人不存在。
            raise ValueError("数字人不存在，无法发起会话。")  # 抛出业务异常。
        session = self._ensure_session(persona_id, session_id)  # 获取或创建会话。
        all_assets = self.repository.assets.list_items()  # 读取全部素材。
        scoped_assets = [item for item in all_assets if item.get("asset_id") in persona.get("knowledge_asset_ids", [])] or all_assets  # 优先使用画像绑定的知识素材。
        selected_assets = self.retrieval_optimizer.select_assets(question, scoped_assets, self.settings.top_k_assets)  # 选出最相关知识素材。
        knowledge_text = self.prompt_optimizer.merge_knowledge(selected_assets, self.settings.max_context_chars)  # 合并知识上下文文本。
        image_summary = ""  # 初始化图像分析结果。
        if image_asset_id:  # 如果本轮传入了图片素材。
            image_asset = self.repository.assets.get_item("asset_id", image_asset_id)  # 读取图片素材记录。
            if image_asset and image_asset.get("file_path"):  # 如果图片素材存在并有本地路径。
                image_summary = self.model_client.analyze_image(question, Path(image_asset["file_path"]), build_visual_prompt(question))  # 调用多模态模型分析图片。
        history = session.get("messages", [])[-self.settings.max_history_messages :]  # 截取最近若干条历史消息。
        history_text = self.prompt_optimizer.format_history(history, self.settings.max_history_messages, self.settings.max_context_chars)  # 格式化历史消息。
        system_prompt = build_dialogue_system_prompt(str(persona.get("name", "默认数字人")), str(persona.get("voice_style", "专业、自然、简洁")), knowledge_text, image_summary)  # 构造系统提示词。
        user_prompt = f"历史消息：\n{history_text or '暂无'}\n\n用户问题：{question.strip()}"  # 构造用户提示词。
        answer_text = self.model_client.generate_text(system_prompt, user_prompt)  # 调用文本模型生成答案。
        self.repository.append_message(session["session_id"], ChatMessageRecord(role="user", content=question.strip()))  # 记录用户消息。
        updated = self.repository.append_message(session["session_id"], ChatMessageRecord(role="assistant", content=answer_text))  # 记录助手消息并拿到最新会话。
        return {  # 返回问答结果。
            "session_id": updated["session_id"],  # 返回会话主键。
            "answer_text": answer_text,  # 返回模型答案。
            "knowledge_assets": selected_assets,  # 返回命中的知识素材。
            "image_summary": image_summary,  # 返回图像分析结果。
        }  # 结束结果对象构造。
