# -*- coding: utf-8 -*-
# 工单编号：人工智能NLP-Agent数字人项目-17-教育Agent任务工单-教学场景功能分析及智能备课
# 模块：应用状态存储 - 进程内内容缓存、协同连接池与下载路径校验

import os
from fastapi import HTTPException
from config import get_settings

generated_content_store = {}
collaboration_connections = {}


def save_generated_content(content: dict) -> None:
    """保存生成内容到进程内存，支撑内容查询与编辑流程"""
    generated_content_store[content["content_id"]] = dict(content)



def get_generated_content_or_404(content_id: str) -> dict:
    """获取生成内容，不存在时抛404"""
    content = generated_content_store.get(content_id)
    if not content:
        raise HTTPException(status_code=404, detail="内容不存在")
    return content



def resolve_export_path_or_404(file_path: str) -> str:
    """限制下载范围在导出目录内，避免任意文件下载"""
    export_dir = os.path.abspath(get_settings().EXPORT_DIR)
    candidate = os.path.abspath(file_path)
    if os.path.commonpath([export_dir, candidate]) != export_dir:
        raise HTTPException(status_code=403, detail="禁止访问导出目录之外的文件")
    if not os.path.exists(candidate):
        raise HTTPException(status_code=404, detail="文件不存在")
    return candidate
