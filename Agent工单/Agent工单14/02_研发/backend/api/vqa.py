"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
VQA 视觉问答 API —— 上传影像 + 自然语言问题 → AI 给出诊断级回答（千问多模态）
================================================================================
"""
from typing import List
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from config import UPLOAD_DIR, ALLOWED_IMAGE_EXTENSIONS
from services.llm_client import get_qwen_client

router = APIRouter(prefix="/api/vqa", tags=["VQA 视觉问答"])

class VQARequest(BaseModel):
    image_filename: str = Field(..., description="已上传的影像文件名")       # 来自 upload API 的返回值
    question: str = Field(..., min_length=1, max_length=2000)               # 用户问题
    system_prompt: str = Field(default="", description="自定义角色设定（可选）")

class VQAResponse(BaseModel):
    success: bool; question: str; answer: str; model: str; image_filename: str
    latency_ms: float; usage: dict; error: str = ""

def _valid(path: Path) -> None:
    """校验图片文件存在且格式合法"""
    if not path.exists():
        raise HTTPException(404, detail=f"影像不存在: {path.name}，请先上传")
    if path.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(400, detail=f"不支持的格式: {path.suffix}")
    if path.stat().st_size < 64:
        raise HTTPException(400, detail="影像文件无效（太小）")

@router.post("/ask")
async def vqa_ask(req: VQARequest):
    """
    医学影像视觉问答：上传一张医学影像并提出问题，AI 分析后给出专业回答
    示例: "影像中是否有肺部渗出性病变？" / "心脏大小是否正常？" / "有无骨折？"
    """
    fp = UPLOAD_DIR / req.image_filename
    _valid(fp)                                           # 校验文件
    qwen = get_qwen_client()                             # 获取千问客户端
    sp = req.system_prompt if req.system_prompt else None # 可选自定义角色
    r = qwen.vqa(str(fp), req.question, sp)              # 调用千问 VL 多模态
    return VQAResponse(success="error" not in r, question=req.question,
        answer=r["content"], model=r["model"], image_filename=req.image_filename,
        latency_ms=r.get("latency_ms",0), usage=r.get("usage",{}), error=r.get("error",""))

@router.post("/batch")
async def vqa_batch(requests: List[VQARequest]):
    """批量 VQA：对同一张影像提多个问题，减少重复上传"""
    if not requests: raise HTTPException(400, detail="请求列表为空")
    fp = UPLOAD_DIR / requests[0].image_filename
    _valid(fp)
    qwen = get_qwen_client()
    results = []
    for req in requests:
        r = qwen.vqa(str(fp), req.question)
        results.append({"question":req.question, "answer":r["content"], "latency_ms":r.get("latency_ms",0)})
    return JSONResponse({"success":True, "image_filename":requests[0].image_filename,
                         "count":len(results), "results":results})
