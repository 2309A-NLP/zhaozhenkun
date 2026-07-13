# -*- coding: utf-8 -*-  # 工单18：指定源码编码为 UTF-8。
"""routes.py - 工单18智能助教的 API 路由模块。"""  # 工单18：声明当前文件功能。

from __future__ import annotations  # 工单18：启用延迟类型注解。

from pathlib import Path  # 工单18：导入路径处理类。

from fastapi import APIRouter  # 工单18：导入路由类。
from fastapi import Depends  # 工单18：导入依赖注入工具。
from fastapi import File  # 工单18：导入文件上传声明工具。
from fastapi import HTTPException  # 工单18：导入异常类型。
from fastapi import Query  # 工单18：导入查询参数声明工具。
from fastapi import UploadFile  # 工单18：导入上传文件类型。

from app.auth import find_user  # 工单18：导入用户查找函数。
from app.auth import get_current_user  # 工单18：导入当前用户依赖。
from app.auth import issue_token  # 工单18：导入令牌签发函数。
from app.auth import public_user  # 工单18：导入用户脱敏函数。
from app.config import now_text  # 工单18：导入当前时间函数。
from app.document_parser import detect_media_kinds  # 工单18：导入模态识别函数。
from app.document_parser import parse_document  # 工单18：导入统一文件解析函数。
from app.models import AskRequest  # 工单18：导入问答请求模型。
from app.models import LoginRequest  # 工单18：导入登录请求模型。
from app.models import TextResourceRequest  # 工单18：导入文本资源模型。
from app.models import split_tags  # 工单18：导入标签拆分函数。
from app.retrieval import add_file_resource  # 工单18：导入文件资源写入函数。
from app.retrieval import add_text_resource  # 工单18：导入文本资源写入函数。
from app.retrieval import build_citations  # 工单18：导入引用构造函数。
from app.retrieval import delete_resource  # 工单18：导入资源删除函数。
from app.retrieval import get_resource  # 工单18：导入资源详情查询函数。
from app.retrieval import list_resources  # 工单18：导入资源筛选函数。
from app.retrieval import search_resources  # 工单18：导入混合检索函数。
from app.services import answer_question  # 工单18：导入智能助教问答服务。
from app.services import dashboard_for_user  # 工单18：导入工作台统计服务。
from app.state import new_id  # 工单18：导入唯一标识函数。

router = APIRouter(prefix="/api", tags=["assistant"])  # 工单18：创建主业务路由对象。


@router.post("/auth/login")  # 工单18：注册登录接口。
def login(payload: LoginRequest) -> dict:  # 工单18：处理用户名密码登录。
    user = find_user(payload.username, payload.password)  # 工单18：校验用户名密码。
    if not user:  # 工单18：若账号校验失败则抛出异常。
        raise HTTPException(status_code=401, detail="用户名或密码错误")  # 工单18：返回未授权错误。
    token = issue_token(user)  # 工单18：为登录用户生成访问令牌。
    return {"success": True, "message": "login ok", "data": {"access_token": token, "user": public_user(user)}}  # 工单18：返回脱敏后的登录结果。


@router.get("/me")  # 工单18：注册当前用户接口。
def me(current_user: dict = Depends(get_current_user)) -> dict:  # 工单18：返回当前用户资料。
    return {"success": True, "message": "ok", "data": public_user(current_user)}  # 工单18：输出当前登录用户公开对象。


@router.get("/dashboard")  # 工单18：注册工作台统计接口。
def dashboard(current_user: dict = Depends(get_current_user)) -> dict:  # 工单18：返回用户工作台数据。
    return {"success": True, "message": "ok", "data": dashboard_for_user(current_user)}  # 工单18：输出聚合统计结果。


@router.post("/assistant/ask")  # 工单18：注册智能助教问答接口。
def ask(payload: AskRequest, current_user: dict = Depends(get_current_user)) -> dict:  # 工单18：处理助教问答请求。
    result = answer_question(current_user, payload.question, payload.model_provider, payload.top_k, payload.use_public, payload.use_private)  # 工单18：执行完整助教业务链路。
    return {"success": True, "message": "ok", "data": result}  # 工单18：返回问答结果。


@router.post("/knowledge/text")  # 工单18：注册文本知识上传接口。
def add_text(payload: TextResourceRequest, current_user: dict = Depends(get_current_user)) -> dict:  # 工单18：新增文本型知识资源。
    resource = add_text_resource(current_user, {"scope": payload.scope, "title": payload.title, "resource_type": payload.resource_type, "content_text": payload.content_text, "source_url": payload.source_url, "tags": split_tags(payload.tags), "created_at": now_text()})  # 工单18：组织文本资源写入参数并创建资源。
    return {"success": True, "message": "created", "data": resource}  # 工单18：返回创建结果。


@router.post("/knowledge/file")  # 工单18：注册文件知识上传接口。
async def add_file(scope: str = Query("private", pattern="^(public|private)$"), model_provider: str = Query("qwen", pattern="^(deepseek|qwen)$"), file: UploadFile = File(...), current_user: dict = Depends(get_current_user)) -> dict:  # 工单18：新增文件型知识资源。
    file_bytes = await file.read()  # 工单18：读取上传文件二进制内容。
    parsed = parse_document(file.filename, file_bytes, provider=model_provider)  # 工单18：将文件解析为统一结构。
    content_text = parsed["content_text"]  # 工单18：读取解析后的正文文本。
    resource = {  # 工单18：构造待写入文件资源对象。
        "resource_id": new_id("res"),  # 工单18：生成资源编号。
        "owner_id": current_user["user_id"],  # 工单18：写入所属用户编号。
        "owner_role": current_user["role"],  # 工单18：写入所属角色。
        "scope": scope,  # 工单18：写入资源范围。
        "title": Path(file.filename).stem,  # 工单18：使用文件名主干作为标题。
        "resource_type": Path(file.filename).suffix.lower().replace(".", "") or "file",  # 工单18：根据后缀生成资源类型。
        "file_name": file.filename,  # 工单18：写入原始文件名。
        "source_url": "",  # 工单18：文件上传场景默认无外部链接。
        "tags": [],  # 工单18：初始化标签列表。
        "content_text": content_text,  # 工单18：写入解析后的正文内容。
        "media_kinds": detect_media_kinds(file.filename, content_text),  # 工单18：识别多模态类型。
        "chunks": parsed.get("chunks", []),  # 工单18：写入结构化切块结果。
        "created_at": now_text(),  # 工单18：写入创建时间。
        "unsupported": parsed.get("unsupported", False),  # 工单18：写入是否为降级解析标识。
    }  # 工单18：结束资源对象构造。
    created = add_file_resource(current_user, resource)  # 工单18：将资源写入存储层。
    if created.get("unsupported"):  # 工单18：对旧格式降级结果返回清晰提示。
        return {"success": False, "message": content_text, "data": created}  # 工单18：返回能力边界说明结果。
    return {"success": True, "message": "created", "data": created}  # 工单18：返回文件上传结果。


@router.post("/knowledge/search")  # 工单18：注册知识检索接口。
def search(payload: AskRequest, current_user: dict = Depends(get_current_user)) -> dict:  # 工单18：根据问题执行知识检索。
    references = search_resources(current_user, payload.question, payload.top_k, payload.use_public, payload.use_private)  # 工单18：执行纯检索流程。
    citations = build_citations(references)  # 工单18：根据检索结果构造引用列表。
    return {"success": True, "message": "ok", "data": {"references": references, "citations": citations}}  # 工单18：返回纯检索数据。


@router.get("/knowledge/list")  # 工单18：注册知识列表接口。
def list_knowledge(scope: str = Query("all", pattern="^(all|public|private)$"), resource_type: str = Query("all"), current_user: dict = Depends(get_current_user)) -> dict:  # 工单18：返回当前用户可访问知识资源。
    items = list_resources(current_user, scope=scope, resource_type=resource_type)  # 工单18：根据筛选条件返回知识资源列表。
    return {"success": True, "message": "ok", "data": {"items": items}}  # 工单18：返回知识资源列表。


@router.get("/knowledge/{resource_id}")  # 工单18：注册知识详情接口。
def resource_detail(resource_id: str, current_user: dict = Depends(get_current_user)) -> dict:  # 工单18：返回当前用户可访问的单个资源详情。
    item = get_resource(current_user, resource_id)  # 工单18：查询指定资源详情。
    if not item:  # 工单18：若资源不存在则抛出异常。
        raise HTTPException(status_code=404, detail="资源不存在")  # 工单18：返回资源不存在错误。
    return {"success": True, "message": "ok", "data": item}  # 工单18：返回资源详情结果。


@router.delete("/knowledge/{resource_id}")  # 工单18：注册知识删除接口。
def remove_resource(resource_id: str, current_user: dict = Depends(get_current_user)) -> dict:  # 工单18：删除当前用户自己上传的资源。
    try:  # 工单18：开始执行资源删除流程。
        item = delete_resource(current_user, resource_id)  # 工单18：调用删除服务删除指定资源。
    except PermissionError as exc:  # 工单18：处理越权删除场景。
        raise HTTPException(status_code=403, detail=str(exc)) from exc  # 工单18：返回禁止访问错误。
    except LookupError as exc:  # 工单18：处理资源不存在场景。
        raise HTTPException(status_code=404, detail=str(exc)) from exc  # 工单18：返回资源不存在错误。
    return {"success": True, "message": "deleted", "data": item}  # 工单18：返回删除结果。
