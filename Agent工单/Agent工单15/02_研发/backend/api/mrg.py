"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
MRG 医疗报告生成 API —— 基于影像 + 临床信息自动生成结构化诊断报告（千问多模态）
================================================================================
"""
from pathlib import Path  # 导入 Path 类，用于文件路径操作
from fastapi import APIRouter, HTTPException  # 导入 FastAPI 的路由器和 HTTP 异常类
from pydantic import BaseModel, Field  # 导入 Pydantic 的 BaseModel 和 Field，用于数据模型定义和字段校验
from config import UPLOAD_DIR, ALLOWED_IMAGE_EXTENSIONS  # 从配置导入上传目录路径和允许的图片扩展名集合
from services.llm_client import get_qwen_client  # 导入千问（Qwen）多模态客户端工厂函数

router = APIRouter(prefix="/api/mrg", tags=["MRG 医疗报告生成"])  # 创建 API 路由器，前缀 /api/mrg，Swagger 标签为"MRG 医疗报告生成"

class MRGRequest(BaseModel):  # 定义 MRG（Medical Report Generation）请求数据模型
    image_filename: str = Field(..., description="已上传的影像文件名")  # 必填：已上传的影像文件名称
    clinical_info: str = Field(default="", max_length=2000, description="临床信息（主诉/病史等，可选）")  # 可选：临床补充信息，最大 2000 字符

class MRGResponse(BaseModel):  # 定义 MRG 响应数据模型
    success: bool; report: str; model: str; image_filename: str  # 响应字段：成功标志、生成的报告文本、使用的模型名、影像文件名
    clinical_info: str; latency_ms: float; usage: dict; error: str = ""  # 响应字段：临床信息、延迟（毫秒）、API 用量、错误信息（默认空）

@router.post("/generate")  # 注册 POST 路由：/api/mrg/generate，生成医疗报告
async def generate_report(req: MRGRequest):  # 定义异步医疗报告生成接口，接收 MRGRequest 请求体
    """
    医疗报告生成：上传影像 → AI 自动生成规范诊断报告
    报告含：【检查项目】【检查技术】【影像所见】【诊断印象】【建议】
    """
    fp = UPLOAD_DIR / req.image_filename  # 拼接上传目录与文件名，得到完整的图片文件路径
    if not fp.exists():                                  # 文件存在性检查：验证影像文件是否存在于磁盘
        raise HTTPException(404, detail=f"影像不存在: {req.image_filename}")  # 文件不存在则返回 404 错误
    if fp.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS: # 格式验证：检查文件扩展名是否在允许的影像格式列表中
        raise HTTPException(400, detail=f"不支持: {fp.suffix}")  # 格式不支持则返回 400 错误

    qwen = get_qwen_client()                             # 千问多模态客户端：获取千问 VL 模型客户端实例
    r = qwen.generate_report(str(fp), req.clinical_info) # 调用 MRG：传入图片路径和临床信息，让千问生成结构化诊断报告
    return MRGResponse(success="error" not in r, report=r["content"],  # 构造并返回 MRGResponse：根据是否有 error 判断成功
        model=r["model"], image_filename=req.image_filename, clinical_info=req.clinical_info,  # 返回模型名、影像文件名、临床信息
        latency_ms=r.get("latency_ms",0), usage=r.get("usage",{}), error=r.get("error",""))  # 返回延迟、用量统计、错误信息（缺失时默认值）
