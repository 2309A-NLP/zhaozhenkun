"""文件功能：把问答结果整理为数字人口播脚本，并调用真实 Ultralight 推理生成视频。"""
from __future__ import annotations  # 启用延后类型注解支持。
from 设计.prompts import build_avatar_script_prompt  # 导入口播脚本提示词构造函数。
from 设计.schemas import AvatarJobRecord  # 导入数字人任务结构。
from 研发.clients_llm import ModelClient  # 导入统一模型客户端。
from 研发.clients_ultralight import UltralightAdapter  # 导入数字人适配器。
from 研发.repositories_local import ProjectRepository  # 导入项目仓储。
from 优化.avatar_pipeline_optimizer import AvatarPipelineOptimizer  # 导入数字人脚本优化器。


class AvatarService:  # 定义数字人响应服务。
    def __init__(self, repository: ProjectRepository, model_client: ModelClient, ultralight_adapter: UltralightAdapter, avatar_optimizer: AvatarPipelineOptimizer) -> None:  # 初始化数字人服务。
        self.repository = repository  # 保存仓储对象。
        self.model_client = model_client  # 保存模型客户端。
        self.ultralight_adapter = ultralight_adapter  # 保存数字人适配器。
        self.avatar_optimizer = avatar_optimizer  # 保存脚本优化器。

    def preflight_job(self, persona_id: str) -> dict[str, object]:  # 检查数字人任务是否满足执行条件。
        persona = self.repository.personas.get_item("persona_id", persona_id)  # 读取数字人画像记录。
        if persona is None:  # 如果数字人不存在。
            raise ValueError("数字人不存在，无法执行数字人任务预检。")  # 抛出业务异常。
        assets = self.repository.assets.list_items()  # 读取全部素材供预检使用。
        return self.ultralight_adapter.preflight_avatar(persona, assets)  # 返回数字人任务预检结果。

    def create_job(self, persona_id: str, session_id: str, answer_text: str) -> dict[str, object]:  # 创建数字人输出任务。
        persona = self.repository.personas.get_item("persona_id", persona_id)  # 读取数字人画像记录。
        if persona is None:  # 如果数字人不存在。
            raise ValueError("数字人不存在，无法创建数字人任务。")  # 抛出业务异常。
        motion_style = self.avatar_optimizer.choose_motion_style(str(persona.get("motion_style", "自然")), answer_text)  # 推断当前回答的动作风格。
        polished = self.model_client.generate_text("你是一名数字人口播脚本整理助手。", build_avatar_script_prompt(answer_text, motion_style))  # 调用模型整理脚本文本。
        script_lines = self.avatar_optimizer.build_script_lines(polished or answer_text)  # 拆分为适合播报的脚本行。
        assets = self.repository.assets.list_items()  # 读取全部素材，供头像和训练数据选择使用。
        job = AvatarJobRecord(persona_id=persona_id, session_id=session_id, answer_text=answer_text, script_text="\n".join(script_lines), status="running")  # 构造数字人任务对象。
        job.output_path = self.ultralight_adapter.render_avatar_response(persona, script_lines, job.avatar_job_id, answer_text, assets)  # 调用真实 Ultralight 推理生成结果。
        job.status = "prepared"  # 更新任务状态。
        job.message = "真实 Ultralight 推理结果已生成。"  # 更新任务说明。
        return self.repository.save_avatar_job(job)  # 保存并返回数字人任务。

    def list_jobs(self) -> list[dict[str, object]]:  # 列出全部数字人任务。
        return self.repository.avatar_jobs.list_items()  # 返回全部数字人任务记录。
