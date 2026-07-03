"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
VQA 视觉问答 API —— 上传影像 + 自然语言问题 → AI 给出诊断级回答（千问多模态）
================================================================================
"""
from typing import List  # 导入 List 类型注解，用于批量 VQA 请求的类型标注
from pathlib import Path  # 导入 Path 类，用于文件路径操作和扩展名校验
from fastapi import APIRouter, HTTPException  # 导入 FastAPI 的路由器和 HTTP 异常类
from fastapi.responses import JSONResponse  # 导入 JSONResponse，用于返回 JSON 格式响应
from pydantic import BaseModel, Field  # 导入 Pydantic 的 BaseModel 和 Field，用于请求/响应数据模型定义和字段校验
from config import UPLOAD_DIR, ALLOWED_IMAGE_EXTENSIONS  # 从配置导入上传目录路径和允许的图片扩展名集合
from services.llm_client import get_qwen_client  # 导入千问（Qwen）多模态客户端工厂函数

router = APIRouter(prefix="/api/vqa", tags=["VQA 视觉问答"])  # 创建 API 路由器，前缀 /api/vqa，Swagger 标签为"VQA 视觉问答"

class VQARequest(BaseModel):  # 定义 VQA 请求数据模型，继承自 Pydantic BaseModel
    image_filename: str = Field(..., description="已上传的影像文件名")       # 来自 upload API 的返回值，必填字段
    question: str = Field(..., min_length=1, max_length=2000)               # 用户问题，必填，长度 1-2000 字符
    system_prompt: str = Field(default="", description="自定义角色设定（可选）")  # 可选的自定义角色设定提示词

class VQAResponse(BaseModel):  # 定义 VQA 响应数据模型
    success: bool; question: str; answer: str; model: str; image_filename: str  # 响应字段：成功标志、原始问题、AI 回答、模型名、影像文件名
    latency_ms: float; usage: dict; error: str = ""  # 响应字段：延迟（毫秒）、API 用量统计、错误信息（默认空串）

def _valid(path: Path) -> None:  # 校验图片文件存在且格式合法的辅助函数
    """校验图片文件存在且格式合法"""  # 函数文档字符串
    if not path.exists():  # 检查文件是否存在于磁盘
        raise HTTPException(404, detail=f"影像不存在: {path.name}，请先上传")  # 文件不存在则返回 404 错误
    if path.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:  # 检查文件扩展名是否在允许列表中
        raise HTTPException(400, detail=f"不支持的格式: {path.suffix}")  # 格式不支持则返回 400 错误
    if path.stat().st_size < 64:  # 检查文件大小是否小于 64 字节（无效文件）
        raise HTTPException(400, detail="影像文件无效（太小）")  # 文件太小则返回 400 错误

@router.post("/ask")  # 注册 POST 路由：/api/vqa/ask，单次视觉问答
async def vqa_ask(req: VQARequest):  # 定义异步 VQA 提问接口，接收 VQARequest 请求体
    """
    医学影像视觉问答：上传一张医学影像并提出问题，AI 分析后给出专业回答
    示例: "影像中是否有肺部渗出性病变？" / "心脏大小是否正常？" / "有无骨折？"
    """
    fp = UPLOAD_DIR / req.image_filename  # 拼接上传目录与文件名，得到完整的图片文件路径
    _valid(fp)                                           # 校验文件：存在性、格式、大小
    qwen = get_qwen_client()                             # 获取千问多模态客户端实例
    sp = req.system_prompt if req.system_prompt else None # 可选自定义角色设定：有值则传入，无值则传 None
    r = qwen.vqa(str(fp), req.question, sp)              # 调用千问 VL 多模态：传入图片路径、问题和角色设定
    return VQAResponse(success="error" not in r, question=req.question,  # 构造并返回 VQAResponse：根据结果中是否有 error 字段判断成功
        answer=r["content"], model=r["model"], image_filename=req.image_filename,  # 返回 AI 回答内容、模型名称、原始影像文件名
        latency_ms=r.get("latency_ms",0), usage=r.get("usage",{}), error=r.get("error",""))  # 返回延迟、用量统计、错误信息（缺失时用默认值）

@router.post("/batch")  # 注册 POST 路由：/api/vqa/batch，批量视觉问答
async def vqa_batch(requests: List[VQARequest]):  # 定义异步批量 VQA 接口，接收 VQARequest 列表
    """批量 VQA：对同一张影像提多个问题，减少重复上传"""  # 接口文档字符串
    if not requests: raise HTTPException(400, detail="请求列表为空")  # 如果请求列表为空，返回 400 错误
    fp = UPLOAD_DIR / requests[0].image_filename  # 取第一个请求的影像文件名，拼接完整路径（批量操作使用同一张图）
    _valid(fp)  # 校验图片文件的有效性
    qwen = get_qwen_client()  # 获取千问多模态客户端实例
    results = []  # 初始化结果列表，用于收集每个问题的回答
    for req in requests:  # 遍历批量请求中的每个 VQA 请求
        r = qwen.vqa(str(fp), req.question)  # 对同一张图片调用千问 VL，传入图片路径和当前问题
        results.append({"question":req.question, "answer":r["content"], "latency_ms":r.get("latency_ms",0)})  # 收集结果：问题、回答、延迟
    return JSONResponse({"success":True, "image_filename":requests[0].image_filename,  # 返回批量结果：成功标志、影像文件名
                         "count":len(results), "results":results})  # 返回问题总数和所有问答结果列表
