# -*- coding: utf-8 -*-
# 工单编号：人工智能NLP-Agent数字人项目-17-教育Agent任务工单-教学场景功能分析及智能备课
# 模块：知识库路由 - 资源检索、上传、列表、引用与删除

from fastapi import APIRouter, Depends, HTTPException, Query
from auth import auth_service
from knowledge_base import knowledge_base_service
from resource_search import resource_search_service
from schemas import SearchRequest, UploadRequest

router = APIRouter()


@router.post("/api/v1/knowledge/search", tags=["知识库"], summary="检索知识库资源")
async def search_knowledge(req: SearchRequest,
                           current_user: dict = Depends(auth_service.get_current_user)):
    """检索知识库资源 - 综合检索知识库和本地教材"""
    types = [req.resource_type] if req.resource_type else None
    results = resource_search_service.search_all_sources(req.query, req.max_results, types)
    return {"code": 200, "data": results}


@router.post("/api/v1/knowledge/upload", tags=["知识库"], summary="上传资源到知识库")
async def upload_resource(req: UploadRequest,
                          current_user: dict = Depends(auth_service.get_current_user)):
    """上传资源到知识库 - 将教材或文档添加到向量知识库"""
    tag_list = [item.strip() for item in req.tags.split(",")] if req.tags else []
    resource_id = knowledge_base_service.add_document(
        title=req.title,
        content=req.content,
        resource_type=req.resource_type,
        tags=tag_list,
        source_url=req.source_url or None,
    )
    return {"code": 200, "message": "资源上传成功", "data": {"resource_id": resource_id}}


@router.get("/api/v1/knowledge/resources", tags=["知识库"], summary="获取知识库资源列表")
async def list_knowledge_resources(resource_type: str = "",
                                   page: int = Query(default=1, ge=1),
                                   page_size: int = Query(default=20, ge=1, le=100),
                                   current_user: dict = Depends(auth_service.get_current_user)):
    """获取知识库资源列表 - 基于元数据聚合资源"""
    grouped = {}
    for item in knowledge_base_service.metadata:
        resource_id = item["resource_id"]
        if resource_id not in grouped:
            grouped[resource_id] = {
                "resource_id": resource_id,
                "title": item["title"],
                "resource_type": item["resource_type"],
                "source_url": item.get("source_url", ""),
                "tags": item.get("tags", []),
                "snippet": item.get("content", "")[:200],
            }
    items = list(grouped.values())
    if resource_type:
        items = [item for item in items if item["resource_type"] == resource_type]
    total = len(items)
    start = (page - 1) * page_size
    return {"code": 200, "data": {"items": items[start:start + page_size], "total": total, "page": page, "page_size": page_size}}


@router.delete("/api/v1/knowledge/resource/{resource_id}", tags=["知识库"], summary="删除知识库资源")
async def delete_knowledge_resource(resource_id: str,
                                    current_user: dict = Depends(auth_service.get_current_user)):
    """删除知识库资源 - 删除指定资源及其向量"""
    deleted = knowledge_base_service.delete_resource(resource_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="资源不存在")
    return {"code": 200, "message": "资源删除成功", "data": {"resource_id": resource_id}}


@router.post("/api/v1/knowledge/resource/{resource_id}/cite", tags=["知识库"], summary="生成资源引用文本")
async def cite_resource(resource_id: str,
                        current_user: dict = Depends(auth_service.get_current_user)):
    """生成资源引用 - 按资源类型输出引用文本"""
    resource = next((item for item in knowledge_base_service.metadata if item["resource_id"] == resource_id), None)
    if not resource:
        raise HTTPException(status_code=404, detail="资源不存在")
    citation_text = resource_search_service.generate_citation(
        resource_title=resource["title"],
        resource_type=resource["resource_type"],
        source_url=resource.get("source_url") or None,
    )
    return {"code": 200, "data": {"resource_id": resource_id, "title": resource["title"], "citation_text": citation_text}}


@router.get("/api/v1/knowledge/stats", tags=["知识库"], summary="知识库统计信息")
async def knowledge_stats(current_user: dict = Depends(auth_service.get_current_user)):
    """获取知识库统计 - 返回向量数和文档数"""
    return {"code": 200, "data": knowledge_base_service.get_statistics()}
