# -*- coding: utf-8 -*-
# 工单编号：人工智能CV-AIGC-16-【必选】文旅Agent任务工单-需求分析与功能设计V1.1-20260306
"""
routes_generate.py - 内容生成相关路由
功能：注册 /api/generate-ppt（PPT生成）、/api/generate-flowchart（流程图生成）、
      /api/download/{filename}（文件下载）
PPT使用LLM生成大纲 + python-pptx渲染，流程图使用LLM生成Mermaid代码
"""

from fastapi import APIRouter  # FastAPI路由分组
from fastapi.responses import JSONResponse, FileResponse  # JSON响应和文件下载响应
from pydantic import BaseModel  # 请求体数据模型

# 导入各模块
from llm_client import call_llm  # 非流式LLM调用
from ppt_generator import (  # PPT生成模块
    PPTX_AVAILABLE,  # pptx是否可用
    OUTPUT_DIR,  # 输出目录
    parse_outline_json,  # 解析LLM大纲JSON
    create_pptx,  # 创建PPT文件
    FALLBACK_SLIDES,  # 默认PPT内容
)

# ============================================================
# 创建路由组
# ============================================================
router = APIRouter(prefix="/api", tags=["内容生成"])  # /api前缀，OpenAPI分组"内容生成"


# ============================================================
# 请求体数据模型
# ============================================================
class PPTRequest(BaseModel):
    """PPT生成请求模型"""
    topic: str  # PPT主题
    slides_count: int = 6  # 页数，默认6页
    provider: str = "kimi"  # 使用的LLM


class FlowchartRequest(BaseModel):
    """流程图生成请求模型"""
    topic: str  # 流程图主题
    provider: str = "kimi"  # 使用的LLM


# ============================================================
# POST /api/generate-ppt - PPT生成接口
# ============================================================
@router.post("/generate-ppt")  # 注册POST路由
async def generate_ppt(req: PPTRequest):
    """
    生成PPT文件
    流程：LLM生成内容大纲(JSON) → python-pptx渲染为.pptx → 返回下载链接
    """
    # 检查python-pptx是否安装
    if not PPTX_AVAILABLE:  # 未安装pptx
        return JSONResponse(
            {"success": False, "error": "请先安装python-pptx: pip install python-pptx"},
            status_code=500,
        )  # 返回500错误

    # 步骤1：用LLM生成PPT内容大纲（JSON格式）
    outline_prompt = (
        f"请为以下主题生成PPT内容大纲，输出纯JSON格式（不要markdown代码块）：\n"
        f"主题：{req.topic}\n"
        f"要求：\n"
        f"- 共{req.slides_count}页幻灯片\n"
        f"- 每页包含：标题(title)、副标题(subtitle，可选)、3-5个要点(bullets，数组)\n"
        f'- JSON结构：{{"slides": [{{"title": "xx", "subtitle": "xx", "bullets": ["点1", "点2"]}}]}}'
    )  # PPT大纲生成prompt

    # 调用LLM获取大纲JSON
    messages = [{"role": "user", "content": outline_prompt}]  # 用户消息
    content = await call_llm(req.provider, messages)  # 非流式调用LLM

    # 步骤2：解析JSON大纲
    slides_data = parse_outline_json(content, req.slides_count, req.topic)  # 解析或fallback

    # 步骤3：生成PPT文件
    try:
        filename = create_pptx(slides_data, req.topic)  # 创建PPT，返回文件名
        return JSONResponse({
            "success": True,  # 成功标记
            "filename": filename,  # 文件名
            "path": str(OUTPUT_DIR / filename),  # 完整路径
        })  # 返回成功响应
    except Exception as e:  # PPT生成异常
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)  # 返回错误


# ============================================================
# POST /api/generate-flowchart - 流程图生成接口
# ============================================================
@router.post("/generate-flowchart")  # 注册POST路由
async def generate_flowchart(req: FlowchartRequest):
    """
    生成流程图Mermaid代码
    流程：LLM分析主题 → 输出Mermaid语法 → 前端mermaid.js渲染
    """
    # 构造Mermaid生成prompt
    prompt = (
        f'请为主题"{req.topic}"设计一个流程图，输出纯Mermaid语法（不要markdown代码块标记）。\n'
        "要求：\n"
        "- 使用 graph TD 或 flowchart TD 格式\n"
        "- 节点使用中文描述\n"
        "- 包含至少6个节点\n"
        "- 逻辑清晰，层级合理\n"
        "- 可以为不同节点添加样式\n"
        "只输出Mermaid代码。"
    )  # 流程图生成prompt

    # 调用LLM生成Mermaid代码
    messages = [{"role": "user", "content": prompt}]  # 用户消息
    content = await call_llm(req.provider, messages)  # 非流式调用

    # 清理：去掉可能的markdown代码块标记
    mermaid_code = content.strip()  # 去除首尾空白
    if mermaid_code.startswith("```"):  # 有代码块标记
        lines = mermaid_code.split("\n")  # 按行分割
        if lines[0].startswith("```"):  # 去掉首行```
            lines = lines[1:]  # 删第一行
        if lines and lines[-1].startswith("```"):  # 去掉末行```
            lines = lines[:-1]  # 删最后一行
        mermaid_code = "\n".join(lines)  # 重新拼接

    return JSONResponse({
        "success": True,  # 成功标记
        "mermaid": mermaid_code,  # Mermaid代码
        "topic": req.topic,  # 原始主题
    })  # 返回Mermaid代码给前端渲染


# ============================================================
# GET /api/download/{filename} - 文件下载接口
# ============================================================
@router.get("/download/{filename}")  # 注册GET路由（路径参数）
async def download_file(filename: str):
    """
    下载生成的文件（PPT等）
    前端通过此接口下载生成的.pptx文件
    """
    filepath = OUTPUT_DIR / filename  # 拼接完整路径
    if filepath.exists():  # 文件存在
        return FileResponse(str(filepath), filename=filename)  # 返回文件下载响应
    return JSONResponse({"error": "文件不存在"}, status_code=404)  # 404未找到
