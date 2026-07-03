"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
文件上传 API —— 图片(VQA/MRG) + 文档(RAG) | 防路径穿越 | MIME+扩展名双校验
================================================================================
"""
import uuid  # 导入 uuid 模块，用于生成唯一标识符，防止文件名冲突
from datetime import datetime  # 导入 datetime 模块，用于生成上传时间戳
from pathlib import Path  # 导入 Path 类，用于文件和路径的安全操作
from io import BytesIO  # 导入 BytesIO 类，用于在内存中操作图片字节流以验证尺寸
from fastapi import APIRouter, UploadFile, File, HTTPException  # 导入 FastAPI 核心组件：路由器、上传文件、文件参数、HTTP 异常
from fastapi.responses import JSONResponse  # 导入 JSONResponse，用于返回 JSON 格式的响应
from config import (  # 从项目配置模块导入上传相关的常量
    UPLOAD_DIR, MAX_UPLOAD_SIZE_MB,  # 上传目录路径、最大上传文件大小（MB）
    ALLOWED_IMAGE_TYPES, ALLOWED_IMAGE_EXTENSIONS,  # 允许的图片 MIME 类型集合、允许的图片扩展名集合
    ALLOWED_DOC_TYPES, ALLOWED_DOC_EXTENSIONS,  # 允许的文档 MIME 类型集合、允许的文档扩展名集合
)
router = APIRouter(prefix="/api/upload", tags=["文件上传"])  # 创建 API 路由器，设置路由前缀为 /api/upload，Swagger 标签为"文件上传"

def _ext_ok(filename: str, allowed: set) -> bool:
    """扩展名校验（MIME 不靠谱时的回退方案）"""  # 函数文档字符串：当 MIME 类型不可靠时，用扩展名兜底校验
    return Path(filename).suffix.lower() in allowed  # 提取文件扩展名并转小写，检查是否在允许的扩展名集合中

def _safe_name(filename: str) -> str:
    """防路径穿越 + 截断过长文件名"""  # 函数文档字符串：防止路径穿越攻击，并截断过长的文件名
    safe = Path(filename).name  # 只取文件名，丢弃目录部分，防止 ../ 路径穿越攻击
    if len(safe) > 200:  # 如果文件名超过 200 个字符
        safe = Path(safe).stem[:150] + Path(safe).suffix[:20]  # 截断文件名主体至 150 字符，扩展名至 20 字符
    return safe  # 返回安全的文件名

@router.post("/image")  # 注册 POST 路由：/api/upload/image，用于上传医学影像
async def upload_image(file: UploadFile = File(...)):  # 定义异步上传图片接口，file 参数为必填的上传文件
    """上传医学影像（JPEG/PNG/DICOM/TIFF），返回 {success, filename, url}"""  # 接口文档字符串
    # 1. 类型校验：MIME 优先，扩展名回退
    if file.content_type not in ALLOWED_IMAGE_TYPES and not _ext_ok(file.filename or "", ALLOWED_IMAGE_EXTENSIONS):  # MIME 类型校验失败时用扩展名校验兜底
        raise HTTPException(400, detail=f"不支持的图片格式: {file.content_type}")  # 两种校验均不通过则抛出 400 错误
    # 2. 大小校验
    content = await file.read()  # 异步读取上传文件的全部字节内容
    size_mb = len(content) / (1024*1024)  # 计算文件大小，字节转 MB
    if size_mb > MAX_UPLOAD_SIZE_MB:  # 如果文件大小超过配置的最大上传限制
        raise HTTPException(400, detail=f"文件过大({size_mb:.1f}MB > {MAX_UPLOAD_SIZE_MB}MB)")  # 抛出 400 错误并显示实际大小与限制
    if len(content) < 64:  # 如果文件内容不足 64 字节，显然不是有效的图片
        raise HTTPException(400, detail="文件太小，不是有效图片")  # 抛出 400 错误，拒绝过小文件
    # 3. 图片尺寸校验（千问 VL 要求 ≥10×10 像素）
    try:  # 使用 try 块捕获可能的图片格式异常
        from PIL import Image  # 动态导入 PIL.Image，懒加载以加快冷启动
        w, h = Image.open(BytesIO(content)).size  # 在内存中打开图片，获取宽度和高度
        if w < 10 or h < 10:  # 千问 VL 模型要求图片尺寸至少为 10×10 像素
            raise HTTPException(400, detail=f"图片尺寸太小({w}x{h})，最小10x10")  # 尺寸不满足要求则抛出 400 错误
    except HTTPException: raise  # 如果是 HTTPException，直接重新抛出（不做转换）
    except Exception: pass  # 非标准图片格式（如 DICOM）跳过尺寸检查，继续上传流程
    # 4. 保存
    ext = Path(_safe_name(file.filename or "image.jpg")).suffix or ".jpg"  # 安全处理后提取扩展名，无扩展名时默认 .jpg
    fname = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"  # 生成唯一文件名：时间戳_随机8位hex.扩展名
    (UPLOAD_DIR / fname).write_bytes(content)  # 将文件字节内容写入上传目录
    return {"success":True, "filename":fname, "original_name":file.filename,  # 返回成功响应：包含成功标志、存储的文件名、原始文件名
            "size_kb":round(size_mb*1024,1), "url":f"/api/images/{fname}",  # 返回文件大小（KB）、可访问的图片 URL
            "upload_time":datetime.now().isoformat()}  # 返回 ISO 格式的上传时间戳

@router.post("/document")  # 注册 POST 路由：/api/upload/document，用于上传知识文档
async def upload_document(file: UploadFile = File(...)):  # 定义异步上传文档接口，file 参数为必填的上传文件
    """上传知识文档（PDF/TXT/DOCX）用于 RAG 知识库"""  # 接口文档字符串
    if file.content_type not in ALLOWED_DOC_TYPES and not _ext_ok(file.filename or "", ALLOWED_DOC_EXTENSIONS):  # MIME 类型和扩展名双重校验
        raise HTTPException(400, detail=f"不支持的文档格式: {file.content_type}")  # 格式不支持则抛出 400 错误
    content = await file.read()  # 异步读取上传文件的全部字节内容
    size_mb = len(content) / (1024*1024)  # 计算文件大小（MB）
    if size_mb > MAX_UPLOAD_SIZE_MB:  # 检查文件大小是否超过限制
        raise HTTPException(400, detail=f"文件过大({size_mb:.1f}MB)")  # 文件过大则抛出 400 错误
    ext = Path(_safe_name(file.filename or "doc.pdf")).suffix  # 安全处理后提取文件扩展名
    fname = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"  # 生成唯一文件名：时间戳_随机8位hex.扩展名
    (UPLOAD_DIR / fname).write_bytes(content)  # 将文件字节内容写入上传目录
    return {"success":True, "filename":fname, "original_name":file.filename,  # 返回成功响应：成功标志、存储文件名、原始文件名
            "size_kb":round(size_mb*1024,1), "upload_time":datetime.now().isoformat()}  # 返回文件大小（KB）、上传时间戳
