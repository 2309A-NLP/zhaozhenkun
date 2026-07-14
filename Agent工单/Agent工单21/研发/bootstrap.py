"""文件功能：集中初始化配置、仓储、模型客户端和业务服务，提供全局服务容器。"""

from __future__ import annotations  # 启用延后类型注解支持。

from dataclasses import dataclass  # 定义服务容器数据类。
from functools import lru_cache  # 缓存全局单例容器。

from 优化.avatar_pipeline_optimizer import AvatarPipelineOptimizer  # 导入数字人脚本优化器。
from 优化.prompt_optimizer import PromptOptimizer  # 导入提示词优化器。
from 优化.retrieval_optimizer import RetrievalOptimizer  # 导入召回优化器。
from 设计.architecture import AppSettings  # 导入配置类型。
from 设计.architecture import load_settings  # 导入配置加载函数。
from 设计.architecture import prepare_runtime_dirs  # 导入目录初始化函数。
from 研发.clients_llm import ModelClient  # 导入统一模型客户端。
from 研发.clients_ultralight import UltralightAdapter  # 导入 Ultralight 适配器。
from 研发.repositories_local import ProjectRepository  # 导入本地仓储门面。
from 研发.services_assets import AssetService  # 导入素材服务。
from 研发.services_avatar import AvatarService  # 导入数字人任务服务。
from 研发.services_chat import ChatService  # 导入会话问答服务。
from 研发.services_personas import PersonaService  # 导入数字人画像服务。
from 研发.services_training import TrainingService  # 导入训练编排服务。


@dataclass(slots=True)  # 定义服务容器。
class ServiceContainer:  # 保存运行时所需的全部服务对象。
    settings: AppSettings  # 保存全局配置对象。
    repository: ProjectRepository  # 保存仓储对象。
    model_client: ModelClient  # 保存模型客户端。
    ultralight_adapter: UltralightAdapter  # 保存数字人适配器。
    retrieval_optimizer: RetrievalOptimizer  # 保存召回优化器。
    prompt_optimizer: PromptOptimizer  # 保存提示词优化器。
    avatar_optimizer: AvatarPipelineOptimizer  # 保存脚本优化器。
    asset_service: AssetService  # 保存素材服务。
    persona_service: PersonaService  # 保存数字人服务。
    training_service: TrainingService  # 保存训练服务。
    chat_service: ChatService  # 保存问答服务。
    avatar_service: AvatarService  # 保存数字人响应服务。


@lru_cache(maxsize=1)  # 缓存全局容器实例。
def get_container() -> ServiceContainer:  # 构建并返回全局服务容器。
    settings = load_settings()  # 加载应用配置。
    prepare_runtime_dirs(settings)  # 初始化运行时目录。
    repository = ProjectRepository(settings.data_dir)  # 初始化本地仓储对象。
    model_client = ModelClient(settings)  # 初始化模型客户端。
    ultralight_adapter = UltralightAdapter(settings)  # 初始化 Ultralight 适配器。
    retrieval_optimizer = RetrievalOptimizer()  # 初始化召回优化器。
    prompt_optimizer = PromptOptimizer()  # 初始化提示词优化器。
    avatar_optimizer = AvatarPipelineOptimizer()  # 初始化数字人脚本优化器。
    asset_service = AssetService(settings, repository)  # 初始化素材服务。
    persona_service = PersonaService(repository)  # 初始化数字人画像服务。
    training_service = TrainingService(repository, ultralight_adapter)  # 初始化训练编排服务。
    chat_service = ChatService(settings, repository, model_client, retrieval_optimizer, prompt_optimizer)  # 初始化问答服务。
    avatar_service = AvatarService(repository, model_client, ultralight_adapter, avatar_optimizer)  # 初始化数字人任务服务。
    return ServiceContainer(  # 返回完整服务容器。
        settings=settings,  # 保存全局配置对象。
        repository=repository,  # 保存仓储对象。
        model_client=model_client,  # 保存模型客户端。
        ultralight_adapter=ultralight_adapter,  # 保存数字人适配器。
        retrieval_optimizer=retrieval_optimizer,  # 保存召回优化器。
        prompt_optimizer=prompt_optimizer,  # 保存提示词优化器。
        avatar_optimizer=avatar_optimizer,  # 保存脚本优化器。
        asset_service=asset_service,  # 保存素材服务。
        persona_service=persona_service,  # 保存数字人服务。
        training_service=training_service,  # 保存训练服务。
        chat_service=chat_service,  # 保存问答服务。
        avatar_service=avatar_service,  # 保存数字人响应服务。
    )  # 结束容器构建。
