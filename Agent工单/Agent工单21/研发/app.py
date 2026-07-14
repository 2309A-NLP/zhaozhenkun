"""文件功能：构建 FastAPI 应用、注册页面与核心业务接口，并暴露统一启动入口。"""
from __future__ import annotations  # 启用延后类型注解支持。
from pathlib import Path  # 处理模板目录路径。
from fastapi import FastAPI  # 导入 FastAPI 应用类。
from fastapi import File  # 导入文件参数声明。
from fastapi import Form  # 导入表单参数声明。
from fastapi import Request  # 导入请求对象类型。
from fastapi import UploadFile  # 导入上传文件类型。
from fastapi.responses import JSONResponse  # 导入 JSON 响应类型。
from fastapi.templating import Jinja2Templates  # 导入模板渲染器。
from 研发.api_models import AvatarJobCreateRequest  # 导入数字人任务请求模型。
from 研发.api_models import AvatarJobPreflightRequest  # 导入数字人任务预检请求模型。
from 研发.api_models import ChatRequest  # 导入问答请求模型。
from 研发.api_models import PersonaCreateRequest  # 导入数字人创建请求模型。
from 研发.api_models import PersonaUpdateRequest  # 导入数字人更新请求模型。
from 研发.api_models import TextAssetCreateRequest  # 导入文本素材请求模型。
from 研发.api_models import TrainingJobCreateRequest  # 导入训练任务请求模型。
from 研发.api_models import TrainingJobPreflightRequest  # 导入训练预检请求模型。
from 研发.bootstrap import get_container  # 导入全局服务容器获取函数。


def create_app() -> FastAPI:  # 构建并返回 FastAPI 应用。
    container = get_container()  # 获取全局服务容器。
    app = FastAPI(title=container.settings.app_name, version="1.0.0")  # 创建应用对象。
    templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))  # 初始化模板渲染器。

    @app.get("/")  # 注册首页路由。
    def index(request: Request) -> object:  # 渲染首页数据看板。
        return templates.TemplateResponse(  # 返回模板响应。
            request=request,  # 传入当前请求对象。
            name="index.html",  # 指定要渲染的模板名称。
            context={  # 传入模板上下文数据。
                "request": request,  # 传入当前请求对象。
                "app_name": container.settings.app_name,  # 传入应用名称。
                "personas": container.persona_service.list_personas(),  # 传入数字人列表。
                "assets": container.asset_service.list_assets(),  # 传入素材列表。
                "training_jobs": container.training_service.list_jobs(),  # 传入训练任务列表。
                "avatar_jobs": container.avatar_service.list_jobs(),  # 传入数字人任务列表。
            },  # 结束模板上下文构造。
        )  # 完成模板响应构造。

    @app.get("/health")  # 注册健康检查路由。
    def health() -> dict[str, object]:  # 返回健康检查结果。
        return {"status": "ok", "app_name": container.settings.app_name, "mock_mode": container.settings.use_mock_response}  # 返回服务状态。

    @app.get("/api/readiness")  # 注册真实链路就绪状态接口。
    def readiness() -> dict[str, object]:  # 返回全局就绪状态。
        return container.ultralight_adapter.describe_readiness()  # 返回 Ultralight 全局就绪状态。

    @app.get("/api/assets")  # 注册素材列表接口。
    def list_assets() -> list[dict[str, object]]:  # 返回全部素材。
        return container.asset_service.list_assets()  # 调用素材服务返回结果。

    @app.post("/api/assets/text")  # 注册文本素材创建接口。
    def create_text_asset(payload: TextAssetCreateRequest) -> dict[str, object]:  # 创建文本素材。
        return container.asset_service.create_text_asset(payload.name, payload.content_text, payload.tags)  # 调用素材服务返回结果。

    @app.post("/api/assets/upload")  # 注册上传素材接口。
    async def upload_asset(file: UploadFile = File(...), asset_type: str = Form("document"), tags: str = Form("")) -> dict[str, object]:  # 接收上传素材。
        tag_list = [item.strip() for item in tags.split(",") if item.strip()]  # 把逗号分隔标签转换为列表。
        return await container.asset_service.save_upload(file, asset_type, tag_list)  # 调用素材服务保存上传文件。

    @app.get("/api/personas")  # 注册数字人列表接口。
    def list_personas() -> list[dict[str, object]]:  # 返回全部数字人。
        return container.persona_service.list_personas()  # 调用数字人服务返回结果。

    @app.post("/api/personas")  # 注册数字人创建接口。
    def create_persona(payload: PersonaCreateRequest) -> dict[str, object]:  # 创建数字人画像。
        return container.persona_service.create_persona(payload.model_dump())  # 调用数字人服务保存结果。

    @app.put("/api/personas/{persona_id}")  # 注册数字人更新接口。
    def update_persona(persona_id: str, payload: PersonaUpdateRequest) -> dict[str, object]:  # 更新已有数字人画像。
        return container.persona_service.update_persona(persona_id, payload.model_dump(exclude_unset=True, exclude_none=True))  # 调用数字人服务更新结果。

    @app.post("/api/training-jobs/preflight")  # 注册训练预检接口。
    def preflight_training_job(payload: TrainingJobPreflightRequest) -> dict[str, object]:  # 返回训练预检结果。
        return container.training_service.preflight_job(payload.persona_id, payload.asset_ids)  # 调用训练服务执行预检。

    @app.post("/api/training-jobs")  # 注册训练任务创建接口。
    def create_training_job(payload: TrainingJobCreateRequest) -> dict[str, object]:  # 创建训练任务。
        return container.training_service.create_job(payload.persona_id, payload.asset_ids)  # 调用训练服务返回结果。

    @app.get("/api/training-jobs")  # 注册训练任务列表接口。
    def list_training_jobs() -> list[dict[str, object]]:  # 返回全部训练任务。
        return container.training_service.list_jobs()  # 调用训练服务返回结果。

    @app.post("/api/chat")  # 注册问答接口。
    def chat(payload: ChatRequest) -> dict[str, object]:  # 执行一次问答流程。
        return container.chat_service.ask(payload.persona_id, payload.question, payload.session_id, payload.image_asset_id)  # 调用问答服务返回结果。

    @app.post("/api/avatar-jobs/preflight")  # 注册数字人任务预检接口。
    def preflight_avatar_job(payload: AvatarJobPreflightRequest) -> dict[str, object]:  # 返回数字人任务预检结果。
        return container.avatar_service.preflight_job(payload.persona_id)  # 调用数字人服务执行预检。

    @app.post("/api/avatar-jobs")  # 注册数字人任务创建接口。
    def create_avatar_job(payload: AvatarJobCreateRequest) -> dict[str, object]:  # 创建数字人输出任务。
        return container.avatar_service.create_job(payload.persona_id, payload.session_id, payload.answer_text)  # 调用数字人服务返回结果。

    @app.get("/api/avatar-jobs")  # 注册数字人任务列表接口。
    def list_avatar_jobs() -> list[dict[str, object]]:  # 返回全部数字人任务。
        return container.avatar_service.list_jobs()  # 调用数字人服务返回结果。

    @app.exception_handler(ValueError)  # 注册业务异常处理器。
    async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:  # 捕获业务异常并返回 JSON 错误。
        return JSONResponse(status_code=400, content={"detail": str(exc)})  # 返回统一错误响应。

    return app  # 返回构建完成的应用对象。


app = create_app()  # 暴露默认应用实例。
