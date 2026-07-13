# -*- coding: utf-8 -*-
# 工单编号：人工智能NLP-Agent数字人项目-17-教育Agent任务工单-教学场景功能分析及智能备课
# 模块：导出路由 - 教学内容导出与下载

import json
import os
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from auth import auth_service
from export_service import export_service
from schemas import ExportRequest
from app_state import resolve_export_path_or_404

router = APIRouter()


@router.post("/api/v1/export/convert", tags=["导出"], summary="导出教学内容")
async def export_content(req: ExportRequest,
                         current_user: dict = Depends(auth_service.get_current_user)):
    """导出教学内容 - 将内容导出为指定格式文档"""
    content_list = json.loads(req.content_json)
    formats = [fmt.strip() for fmt in req.export_format.split(",")]
    results = export_service.export_batch(content_list, req.title, formats)
    download_info = {fmt: export_service.get_download_info(path) for fmt, path in results.items()}
    return {"code": 200, "message": "导出完成", "data": {"files": download_info}}


@router.get("/api/v1/export/download", tags=["导出"], summary="下载导出文件")
async def download_file(file_path: str,
                        current_user: dict = Depends(auth_service.get_current_user)):
    """下载导出文件 - 提供文件下载功能"""
    resolved_path = resolve_export_path_or_404(file_path)
    return FileResponse(resolved_path, filename=os.path.basename(resolved_path))
