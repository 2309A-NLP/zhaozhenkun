"""
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
RAG（检索增强生成）API —— 使用 DeepSeek 文本推理
"""

import os
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from config import UPLOAD_DIR, KNOWLEDGE_DIR
from services.llm_client import get_deepseek_client
from rag.vector_store import get_vector_store
from rag.document_loader import load_document, load_directory

router = APIRouter(prefix="/api/rag", tags=["RAG 检索增强生成"])


class RAGQueryRequest(BaseModel):
    """RAG 查询请求"""
    question: str = Field(..., description="医学问题", min_length=1, max_length=2000)
    top_k: int = Field(default=5, description="检索文档数量", ge=1, le=20)


class RAGQueryResponse(BaseModel):
    """RAG 查询响应"""
    success: bool
    question: str
    answer: str
    model: str
    retrieved_docs: list
    retrieval_count: int
    latency_ms: float
    usage: dict
    error: str = ""


class DocumentIngestRequest(BaseModel):
    """文档入库请求"""
    filename: str = Field(..., description="已上传的文档文件名")


@router.post("/query")
async def rag_query(req: RAGQueryRequest):
    """
    RAG 检索增强生成

    基于医学知识库检索相关文档，结合 DeepSeek 推理生成回答。
    """
    vs = get_vector_store()
    deepseek = get_deepseek_client()

    # Step 1: 检索相关文档
    retrieved = vs.search(req.question, top_k=req.top_k)
    context_docs = [doc["content"] for doc in retrieved]

    # Step 2: 使用 DeepSeek 生成回答
    result = deepseek.rag_query(req.question, context_docs)

    return RAGQueryResponse(
        success="error" not in result,
        question=req.question,
        answer=result["content"],
        model=result["model"],
        retrieved_docs=[
            {
                "content": doc["content"][:200] + "...",
                "score": doc["score"],
                "metadata": doc["metadata"],
            }
            for doc in retrieved
        ],
        retrieval_count=len(retrieved),
        latency_ms=result.get("latency_ms", 0),
        usage=result.get("usage", {}),
        error=result.get("error", ""),
    )


@router.post("/ingest")
async def ingest_document(req: DocumentIngestRequest):
    """
    将已上传的文档入库到向量知识库
    """
    file_path = UPLOAD_DIR / req.filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"文档不存在: {req.filename}")

    try:
        chunks, metadata = load_document(str(file_path))
        if not chunks:
            return JSONResponse({
                "success": False,
                "message": "文档内容为空",
            })

        vs = get_vector_store()
        metadatas = [{**metadata, "source_file": req.filename} for _ in chunks]
        count = vs.add_documents(chunks, metadatas)

        return JSONResponse({
            "success": True,
            "message": f"成功入库 {count} 个文本块",
            "chunks": count,
            "source_file": req.filename,
            "metadata": metadata,
            "total_documents": vs.count(),
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文档入库失败: {str(e)}")


@router.post("/ingest/batch")
async def ingest_directory():
    """
    批量导入 knowledge 目录下的所有文档
    """
    if not os.path.exists(KNOWLEDGE_DIR):
        return JSONResponse({"success": False, "message": "知识库目录不存在"})

    docs = load_directory(str(KNOWLEDGE_DIR))
    if not docs:
        return JSONResponse({"success": False, "message": "未找到任何文档"})

    vs = get_vector_store()
    total_chunks = 0
    for chunks, metadata in docs:
        if chunks:
            metadatas = [metadata for _ in chunks]
            vs.add_documents(chunks, metadatas)
            total_chunks += len(chunks)

    return JSONResponse({
        "success": True,
        "message": f"批量导入完成",
        "files_processed": len(docs),
        "total_chunks": total_chunks,
        "total_documents": vs.count(),
    })


@router.get("/stats")
async def get_rag_stats():
    """获取 RAG 知识库统计信息"""
    vs = get_vector_store()
    return vs.get_stats()


@router.delete("/clear")
async def clear_knowledge_base():
    """清空知识库"""
    vs = get_vector_store()
    vs.delete_all()
    return JSONResponse({"success": True, "message": "知识库已清空"})
