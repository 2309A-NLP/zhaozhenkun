"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
文件上传 API —— 图片(VQA/MRG) + 文档(RAG) | 防路径穿越 | MIME+扩展名双校验
================================================================================
"""
import uuid
from datetime import datetime
from pathlib import Path
from io import BytesIO
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from config import (
    UPLOAD_DIR, MAX_UPLOAD_SIZE_MB,
    ALLOWED_IMAGE_TYPES, ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_DOC_TYPES, ALLOWED_DOC_EXTENSIONS,
)
router = APIRouter(prefix="/api/upload", tags=["文件上传"])

def _ext_ok(filename: str, allowed: set) -> bool:
    """扩展名校验（MIME 不靠谱时的回退方案）"""
    return Path(filename).suffix.lower() in allowed

def _safe_name(filename: str) -> str:
    """防路径穿越 + 截断过长文件名"""
    safe = Path(filename).name  # 只取文件名，丢弃目录部分
    if len(safe) > 200:
        safe = Path(safe).stem[:150] + Path(safe).suffix[:20]
    return safe

@router.post("/image")
async def upload_image(file: UploadFile = File(...)):
    """上传医学影像（JPEG/PNG/DICOM/TIFF），返回 {success, filename, url}"""
    # 1. 类型校验：MIME 优先，扩展名回退
    if file.content_type not in ALLOWED_IMAGE_TYPES and not _ext_ok(file.filename or "", ALLOWED_IMAGE_EXTENSIONS):
        raise HTTPException(400, detail=f"不支持的图片格式: {file.content_type}")
    # 2. 大小校验
    content = await file.read()
    size_mb = len(content) / (1024*1024)
    if size_mb > MAX_UPLOAD_SIZE_MB:
        raise HTTPException(400, detail=f"文件过大({size_mb:.1f}MB > {MAX_UPLOAD_SIZE_MB}MB)")
    if len(content) < 64:
        raise HTTPException(400, detail="文件太小，不是有效图片")
    # 3. 图片尺寸校验（千问 VL 要求 ≥10×10 像素）
    try:
        from PIL import Image
        w, h = Image.open(BytesIO(content)).size
        if w < 10 or h < 10:
            raise HTTPException(400, detail=f"图片尺寸太小({w}x{h})，最小10x10")
    except HTTPException: raise
    except Exception: pass  # 非标准图片格式跳过尺寸检查
    # 4. 保存
    ext = Path(_safe_name(file.filename or "image.jpg")).suffix or ".jpg"
    fname = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
    (UPLOAD_DIR / fname).write_bytes(content)
    return {"success":True, "filename":fname, "original_name":file.filename,
            "size_kb":round(size_mb*1024,1), "url":f"/api/images/{fname}",
            "upload_time":datetime.now().isoformat()}

@router.post("/document")
async def upload_document(file: UploadFile = File(...)):
    """上传知识文档（PDF/TXT/DOCX）用于 RAG 知识库"""
    if file.content_type not in ALLOWED_DOC_TYPES and not _ext_ok(file.filename or "", ALLOWED_DOC_EXTENSIONS):
        raise HTTPException(400, detail=f"不支持的文档格式: {file.content_type}")
    content = await file.read()
    size_mb = len(content) / (1024*1024)
    if size_mb > MAX_UPLOAD_SIZE_MB:
        raise HTTPException(400, detail=f"文件过大({size_mb:.1f}MB)")
    ext = Path(_safe_name(file.filename or "doc.pdf")).suffix
    fname = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
    (UPLOAD_DIR / fname).write_bytes(content)
    return {"success":True, "filename":fname, "original_name":file.filename,
            "size_kb":round(size_mb*1024,1), "upload_time":datetime.now().isoformat()}
