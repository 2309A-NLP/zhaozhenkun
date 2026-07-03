"""
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
RAG（检索增强生成）API —— 使用 DeepSeek 文本推理
"""

import os  # 导入 os 模块，用于检查知识库目录是否存在
from fastapi import APIRouter, UploadFile, File, HTTPException  # 导入 FastAPI 核心组件：路由器、上传文件、文件参数、HTTP 异常
from fastapi.responses import JSONResponse  # 导入 JSONResponse，用于返回 JSON 格式响应
from pydantic import BaseModel, Field  # 导入 Pydantic 的 BaseModel 和 Field，用于数据模型定义和字段校验

from config import UPLOAD_DIR, KNOWLEDGE_DIR  # 从配置导入上传目录路径和知识库文档目录路径
from services.llm_client import get_deepseek_client  # 导入 DeepSeek 客户端工厂函数，用于文本推理
from rag.vector_store import get_vector_store  # 导入向量存储实例工厂函数，用于文档检索
from rag.document_loader import load_document, load_directory  # 导入文档加载函数：单文档加载和目录批量加载

router = APIRouter(prefix="/api/rag", tags=["RAG 检索增强生成"])  # 创建 API 路由器，前缀 /api/rag，Swagger 标签为"RAG 检索增强生成"


class RAGQueryRequest(BaseModel):  # 定义 RAG 查询请求数据模型
    """RAG 查询请求"""  # 模型文档字符串
    question: str = Field(..., description="医学问题", min_length=1, max_length=2000)  # 必填：医学问题文本，长度 1-2000 字符
    top_k: int = Field(default=5, description="检索文档数量", ge=1, le=20)  # 返回的检索文档数量，默认 5，范围 1-20


class RAGQueryResponse(BaseModel):  # 定义 RAG 查询响应数据模型
    """RAG 查询响应"""  # 模型文档字符串
    success: bool  # 响应字段：是否成功
    question: str  # 响应字段：原始问题文本
    answer: str  # 响应字段：AI 生成的回答
    model: str  # 响应字段：使用的模型名称
    retrieved_docs: list  # 响应字段：检索到的相关文档列表
    retrieval_count: int  # 响应字段：检索到的文档数量
    latency_ms: float  # 响应字段：请求延迟（毫秒）
    usage: dict  # 响应字段：API 用量统计字典
    error: str = ""  # 响应字段：错误信息，默认为空字符串


class DocumentIngestRequest(BaseModel):  # 定义文档入库请求数据模型
    """文档入库请求"""  # 模型文档字符串
    filename: str = Field(..., description="已上传的文档文件名")  # 必填：待入库的文档文件名


@router.post("/query")  # 注册 POST 路由：/api/rag/query，RAG 检索增强生成查询
async def rag_query(req: RAGQueryRequest):  # 定义异步 RAG 查询接口，接收 RAGQueryRequest 请求体
    """
    RAG 检索增强生成

    基于医学知识库检索相关文档，结合 DeepSeek 推理生成回答。
    """
    vs = get_vector_store()  # 获取向量存储实例（ChromaDB/FAISS 等）
    deepseek = get_deepseek_client()  # 获取 DeepSeek 客户端实例，用于文本推理生成

    # Step 1: 检索相关文档
    retrieved = vs.search(req.question, top_k=req.top_k)  # 在向量库中搜索与问题最相关的 top_k 篇文档
    context_docs = [doc["content"] for doc in retrieved]  # 提取检索结果中的文档内容文本，组成上下文列表

    # Step 2: 使用 DeepSeek 生成回答
    result = deepseek.rag_query(req.question, context_docs)  # 调用 DeepSeek RAG 接口：传入问题和检索到的上下文文档

    return RAGQueryResponse(  # 构造并返回 RAGQueryResponse 响应对象
        success="error" not in result,  # 根据结果字典中是否包含 error 字段判断是否成功
        question=req.question,  # 返回原始问题文本
        answer=result["content"],  # 返回 AI 生成的回答内容
        model=result["model"],  # 返回使用的模型名称
        retrieved_docs=[  # 构建检索文档列表，每个文档截取前 200 字符并添加省略号
            {
                "content": doc["content"][:200] + "...",  # 文档内容截取前 200 字符，末尾加省略号
                "score": doc["score"],  # 文档与问题的相似度得分
                "metadata": doc["metadata"],  # 文档的元数据信息
            }
            for doc in retrieved  # 遍历所有检索到的文档
        ],
        retrieval_count=len(retrieved),  # 返回检索到的文档总数
        latency_ms=result.get("latency_ms", 0),  # 返回请求延迟，缺失时默认为 0
        usage=result.get("usage", {}),  # 返回 API 用量统计，缺失时为空字典
        error=result.get("error", ""),  # 返回错误信息，缺失时为空字符串
    )


@router.post("/ingest")  # 注册 POST 路由：/api/rag/ingest，将已上传文档入库到向量知识库
async def ingest_document(req: DocumentIngestRequest):  # 定义异步文档入库接口，接收 DocumentIngestRequest 请求体
    """
    将已上传的文档入库到向量知识库
    """
    file_path = UPLOAD_DIR / req.filename  # 拼接上传目录与文件名，得到完整的文档文件路径
    if not file_path.exists():  # 检查文档文件是否存在于磁盘
        raise HTTPException(status_code=404, detail=f"文档不存在: {req.filename}")  # 文件不存在则返回 404 错误

    try:  # 使用 try 块捕获文档加载和入库过程中的异常
        chunks, metadata = load_document(str(file_path))  # 调用文档加载器，将文档切分为文本块并提取元数据
        if not chunks:  # 如果文档切分后没有产生任何文本块（文档内容为空）
            return JSONResponse({  # 返回 JSON 响应，提示文档内容为空
                "success": False,  # 成功标志设为 False
                "message": "文档内容为空",  # 提示信息
            })

        vs = get_vector_store()  # 获取向量存储实例
        metadatas = [{**metadata, "source_file": req.filename} for _ in chunks]  # 为每个文本块生成元数据，附加来源文件名
        count = vs.add_documents(chunks, metadatas)  # 将文本块和元数据批量添加到向量库，返回成功入库的数量

        return JSONResponse({  # 返回成功入库的 JSON 响应
            "success": True,  # 成功标志
            "message": f"成功入库 {count} 个文本块",  # 提示已入库的文本块数量
            "chunks": count,  # 文本块数量
            "source_file": req.filename,  # 来源文件名
            "metadata": metadata,  # 文档元数据
            "total_documents": vs.count(),  # 向量库中的文档总数
        })
    except Exception as e:  # 捕获所有异常
        raise HTTPException(status_code=500, detail=f"文档入库失败: {str(e)}")  # 返回 500 错误并携带异常信息


@router.post("/ingest/batch")  # 注册 POST 路由：/api/rag/ingest/batch，批量导入知识库目录下的所有文档
async def ingest_directory():  # 定义异步批量文档入库接口
    """
    批量导入 knowledge 目录下的所有文档
    """
    if not os.path.exists(KNOWLEDGE_DIR):  # 检查知识库目录是否存在
        return JSONResponse({"success": False, "message": "知识库目录不存在"})  # 目录不存在则返回失败响应

    docs = load_directory(str(KNOWLEDGE_DIR))  # 批量加载知识库目录下的所有文档，返回 (chunks, metadata) 列表
    if not docs:  # 如果未加载到任何文档
        return JSONResponse({"success": False, "message": "未找到任何文档"})  # 返回失败响应

    vs = get_vector_store()  # 获取向量存储实例
    total_chunks = 0  # 初始化累计文本块计数器
    for chunks, metadata in docs:  # 遍历每个文档的文本块列表和元数据
        if chunks:  # 如果该文档有文本块内容
            metadatas = [metadata for _ in chunks]  # 为每个文本块复制一份相同的元数据
            vs.add_documents(chunks, metadatas)  # 将文本块和元数据添加到向量库
            total_chunks += len(chunks)  # 累加文本块数量

    return JSONResponse({  # 返回批量导入结果 JSON 响应
        "success": True,  # 成功标志
        "message": f"批量导入完成",  # 提示信息
        "files_processed": len(docs),  # 已处理的文档文件数量
        "total_chunks": total_chunks,  # 总共入库的文本块数量
        "total_documents": vs.count(),  # 向量库中的文档总数
    })


@router.get("/stats")  # 注册 GET 路由：/api/rag/stats，获取 RAG 知识库统计信息
async def get_rag_stats():  # 定义异步统计信息查询接口
    """获取 RAG 知识库统计信息"""  # 接口文档字符串
    vs = get_vector_store()  # 获取向量存储实例
    return vs.get_stats()  # 调用向量库的统计方法，返回知识库统计信息


@router.delete("/clear")  # 注册 DELETE 路由：/api/rag/clear，清空知识库
async def clear_knowledge_base():  # 定义异步清空知识库接口
    """清空知识库"""  # 接口文档字符串
    vs = get_vector_store()  # 获取向量存储实例
    vs.delete_all()  # 调用向量库的全部删除方法，清空所有文档数据
    return JSONResponse({"success": True, "message": "知识库已清空"})  # 返回清空成功的 JSON 响应
