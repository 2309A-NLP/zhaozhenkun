# -*- coding: utf-8 -*-
# 工单编号：人工智能NLP-Agent数字人项目-17-教育Agent任务工单-教学场景功能分析及智能备课
# 模块：备课路由 - 内容生成、查询、编辑、克隆与流式输出

import json
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from auth import auth_service
from lesson_generator import lesson_generator
from schemas import GenerateRequest, ImproveRequest, UpdateContentRequest, CloneContentRequest
from version_control import version_control_service
from app_state import save_generated_content, get_generated_content_or_404, generated_content_store

router = APIRouter()


@router.post("/api/v1/lesson-prep/generate", tags=["智能备课"], summary="生成教学内容")
async def generate_lesson_content(req: GenerateRequest,
                                  current_user: dict = Depends(auth_service.get_current_user)):
    """生成教学内容 - 调用大模型+知识库自动生成教案/课件/习题等"""
    course_info = {
        "course_name": req.course_name,
        "chapter": req.chapter,
        "grade_level": req.grade_level,
        "subject": req.subject,
        "teaching_objectives": req.teaching_objectives,
        "class_hours": req.class_hours,
        "key_points": req.key_points,
        "difficult_points": req.difficult_points,
        "teacher_id": current_user["user_id"],
    }
    types_list = [item.strip() for item in req.content_types.split(",")]
    results = lesson_generator.generate_content(
        course_info=course_info,
        content_types=types_list,
        use_knowledge_base=req.use_kb,
        additional_instructions=req.additional_instructions or None,
    )
    for content in results:
        save_generated_content(content)
        version_control_service.save_version(
            content_id=content["content_id"],
            content_snapshot=content["raw_content"],
            editor_id=current_user["user_id"],
            change_summary="AI初始生成",
        )
    return {"code": 200, "message": "内容生成成功", "data": {"contents": results, "total": len(results)}}


@router.post("/api/v1/lesson-prep/improve", tags=["智能备课"], summary="优化改进内容")
async def improve_content(req: ImproveRequest,
                          current_user: dict = Depends(auth_service.get_current_user)):
    """优化教学内容 - 根据教师反馈改进已生成内容"""
    improved = lesson_generator.improve_content(req.content_text, req.improvement_request)
    return {"code": 200, "message": "内容优化成功", "data": {"improved_content": improved}}


@router.get("/api/v1/lesson-prep/content/{content_id}", tags=["智能备课"], summary="获取单个内容详情")
async def get_content_detail(content_id: str,
                             current_user: dict = Depends(auth_service.get_current_user)):
    """获取内容详情 - 返回内容主体与版本摘要"""
    content = get_generated_content_or_404(content_id)
    versions = version_control_service.get_versions(content_id)
    return {"code": 200, "data": {**content, "versions": versions}}


@router.get("/api/v1/lesson-prep/contents", tags=["智能备课"], summary="获取内容列表")
async def list_contents(content_type: str = "", keyword: str = "",
                        page: int = Query(default=1, ge=1),
                        page_size: int = Query(default=20, ge=1, le=100),
                        current_user: dict = Depends(auth_service.get_current_user)):
    """获取内容列表 - 支持按类型和关键字筛选"""
    items = list(generated_content_store.values())
    if content_type:
        items = [item for item in items if item.get("content_type") == content_type]
    if keyword:
        items = [item for item in items if keyword.lower() in item.get("title", "").lower() or keyword.lower() in item.get("raw_content", "").lower()]
    total = len(items)
    start = (page - 1) * page_size
    return {"code": 200, "data": {"items": items[start:start + page_size], "total": total, "page": page, "page_size": page_size}}


@router.put("/api/v1/lesson-prep/content/{content_id}", tags=["智能备课"], summary="更新编辑后的内容")
async def update_content(content_id: str, req: UpdateContentRequest,
                         current_user: dict = Depends(auth_service.get_current_user)):
    """更新内容 - 保存编辑结果并记录版本"""
    content = get_generated_content_or_404(content_id)
    content["raw_content"] = req.raw_content
    content["structured_content"] = req.structured_content
    content["updated_at"] = datetime.now().isoformat()
    save_generated_content(content)
    version = version_control_service.save_version(
        content_id=content_id,
        content_snapshot=req.raw_content,
        editor_id=current_user["user_id"],
        change_summary=req.change_summary,
    )
    return {"code": 200, "message": "内容更新成功", "data": {"content": content, "version": version}}


@router.delete("/api/v1/lesson-prep/content/{content_id}", tags=["智能备课"], summary="删除指定内容")
async def delete_content(content_id: str,
                         current_user: dict = Depends(auth_service.get_current_user)):
    """删除内容 - 从内存内容库移除"""
    get_generated_content_or_404(content_id)
    del generated_content_store[content_id]
    return {"code": 200, "message": "内容删除成功", "data": {"content_id": content_id}}


@router.post("/api/v1/lesson-prep/content/{content_id}/clone", tags=["智能备课"], summary="克隆/复制内容")
async def clone_content(content_id: str, req: CloneContentRequest,
                        current_user: dict = Depends(auth_service.get_current_user)):
    """克隆内容 - 复制一份现有内容并生成新ID"""
    source = get_generated_content_or_404(content_id)
    cloned = dict(source)
    cloned["content_id"] = f"clone_{datetime.now().timestamp():.6f}".replace(".", "")
    cloned["title"] = req.title or f"{source['title']}-副本"
    cloned["generated_at"] = datetime.now().isoformat()
    save_generated_content(cloned)
    version_control_service.save_version(
        content_id=cloned["content_id"],
        content_snapshot=cloned["raw_content"],
        editor_id=current_user["user_id"],
        change_summary="克隆生成",
    )
    return {"code": 200, "message": "内容克隆成功", "data": cloned}


@router.post("/api/v1/lesson-prep/generate-stream", tags=["智能备课"], summary="流式生成教学内容")
async def generate_lesson_content_stream(req: GenerateRequest,
                                         current_user: dict = Depends(auth_service.get_current_user)):
    """流式生成教学内容 - 实时返回生成进度和内容token"""
    course_info = {
        "course_name": req.course_name,
        "chapter": req.chapter,
        "grade_level": req.grade_level,
        "subject": req.subject,
        "teaching_objectives": req.teaching_objectives,
        "class_hours": req.class_hours,
        "key_points": req.key_points,
        "difficult_points": req.difficult_points,
        "teacher_id": current_user["user_id"],
    }
    content_type = req.content_types.split(",")[0].strip()

    async def generate():
        full_text = []
        for chunk in lesson_generator.generate_content_stream(
            course_info=course_info, content_type=content_type, use_knowledge_base=req.use_kb):
            if isinstance(chunk, dict) and chunk.get("__meta__"):
                yield f"data: {json.dumps({'type': 'meta', 'content_id': chunk['content_id'], 'model': chunk['model_used']})}\n\n"
            else:
                full_text.append(chunk)
                yield f"data: {json.dumps({'type': 'token', 'text': chunk})}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'total_length': len(''.join(full_text))})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
