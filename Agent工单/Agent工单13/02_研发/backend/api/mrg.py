"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
MRG 医疗报告生成 API —— 基于影像 + 临床信息自动生成结构化诊断报告（千问多模态）
================================================================================
"""
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from config import UPLOAD_DIR, ALLOWED_IMAGE_EXTENSIONS
from services.llm_client import get_qwen_client

router = APIRouter(prefix="/api/mrg", tags=["MRG 医疗报告生成"])

class MRGRequest(BaseModel):
    image_filename: str = Field(..., description="已上传的影像文件名")
    clinical_info: str = Field(default="", max_length=2000, description="临床信息（主诉/病史等，可选）")

class MRGResponse(BaseModel):
    success: bool; report: str; model: str; image_filename: str
    clinical_info: str; latency_ms: float; usage: dict; error: str = ""

@router.post("/generate")
async def generate_report(req: MRGRequest):
    """
    医疗报告生成：上传影像 → AI 自动生成规范诊断报告
    报告含：【检查项目】【检查技术】【影像所见】【诊断印象】【建议】
    """
    fp = UPLOAD_DIR / req.image_filename
    if not fp.exists():                                  # 文件存在性检查
        raise HTTPException(404, detail=f"影像不存在: {req.image_filename}")
    if fp.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS: # 格式验证
        raise HTTPException(400, detail=f"不支持: {fp.suffix}")

    qwen = get_qwen_client()                             # 千问多模态客户端
    r = qwen.generate_report(str(fp), req.clinical_info) # 调用 MRG
    return MRGResponse(success="error" not in r, report=r["content"],
        model=r["model"], image_filename=req.image_filename, clinical_info=req.clinical_info,
        latency_ms=r.get("latency_ms",0), usage=r.get("usage",{}), error=r.get("error",""))
