#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
02_研发 — 智能体桥接 API 服务 + 对话界面
==============================================================================
启动: python agent_bridge.py
访问: http://localhost:8008  (内置聊天UI)
API:  http://localhost:8008/docs (Swagger文档)
==============================================================================
"""

import json, sys, os, socket, traceback  # 标准库
from typing import Optional, List  # 类型注解
from contextlib import asynccontextmanager  # lifespan上下文管理器

# 确保能导入同目录下的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, Query, Request  # FastAPI框架
from fastapi.middleware.cors import CORSMiddleware  # CORS跨域
from fastapi.responses import HTMLResponse  # HTML响应
from pydantic import BaseModel, Field  # 数据验证
import uvicorn  # ASGI服务器

from memory_processor import MemoryProcessor  # 记忆处理器(内含LLM客户端)

# ============================================================
# 数据模型
# ============================================================
class ConversationRequest(BaseModel):
    """对话记忆写入请求。"""
    domain: str = Field(..., description="领域: medical/tourism/education")
    user_id: str = Field(..., description="用户唯一标识")
    conversation: str = Field(..., description="完整对话文本")
    run_id: Optional[str] = Field(None, description="会话ID")
    metadata: Optional[dict] = Field(None, description="附加元数据")


class MemoryResponse(BaseModel):
    """通用响应模型。"""
    success: bool = Field(..., description="是否成功")
    message: str = Field("", description="结果描述")
    data: Optional[dict] = Field(None, description="返回数据")


# ============================================================
# 应用初始化
# ============================================================
processor: MemoryProcessor = None  # 全局处理器，lifespan中初始化

@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时初始化，关闭时释放。"""
    global processor
    print("[Bridge] 正在初始化记忆处理器...")
    processor = MemoryProcessor()
    if processor.memory.health():
        print("[Bridge] mem0 服务连接成功")
    else:
        print("[Bridge] mem0 服务未响应")
    print("[Bridge] 服务启动完成")
    yield
    print("[Bridge] 服务已关闭")


app = FastAPI(
    title="多领域智能体长期记忆系统",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 首页 — 读取 frontend/index.html（纯文件读取，无内嵌HTML）
# ============================================================
@app.get("/", response_class=HTMLResponse)
def root():
    """返回对话页面（从 frontend/index.html 读取）。"""
    path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "frontend", "index.html"
    )
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1 style='color:#fff;text-align:center;margin-top:100px'>前端文件未找到<br>请确认 frontend/index.html 存在</h1>"

# ============================================================
# API 端点
# ============================================================

@app.post("/api/memory/process", response_model=MemoryResponse)
def api_process(req: ConversationRequest):
    """处理对话并写入记忆（提取→摘要→存储）。"""
    valid = ["medical", "tourism", "education"]
    if req.domain not in valid:
        raise HTTPException(400, detail=f"无效领域: {req.domain}")
    result = processor.process_conversation(
        domain=req.domain, user_id=req.user_id,
        conversation=req.conversation,
        run_id=req.run_id, metadata=req.metadata,
    )
    if result.get("success"):
        return MemoryResponse(success=True, message="记忆已存储",
            data={
                "summary": result.get("summary", ""),
                "extracted": result.get("extracted", {}),
                "validation": result.get("validation", {}),
                "metadata": result.get("metadata", {}),
            })
    return MemoryResponse(success=False,
        message=f"存储失败: {result.get('error', '未知')}")


@app.get("/api/memory/context", response_model=MemoryResponse)
def api_context(
    domain: str = Query(..., description="领域"),
    user_id: str = Query(..., description="用户ID"),
    query: str = Query(..., description="查询文本"),
    top_k: int = Query(5, description="返回条数"),
):
    """检索历史记忆上下文。"""
    valid = ["medical", "tourism", "education"]
    if domain not in valid:
        raise HTTPException(400, detail=f"无效领域: {domain}")
    memories = processor.retrieve_context(domain, user_id, query, top_k)
    ctx = processor.build_context_prompt(memories, domain)
    return MemoryResponse(success=True,
        message=f"检索到 {len(memories)} 条记忆",
        data={"memories": memories, "context_prompt": ctx, "count": len(memories)})


@app.get("/api/memory/list", response_model=MemoryResponse)
def api_list(
    domain: str = Query(..., description="领域"),
    user_id: str = Query(..., description="用户ID"),
):
    """列出用户所有记忆。"""
    valid = ["medical", "tourism", "education"]
    if domain not in valid:
        raise HTTPException(400, detail=f"无效领域: {domain}")
    memories = processor.get_all_memories(domain, user_id)
    return MemoryResponse(success=True,
        message=f"共 {len(memories)} 条记忆",
        data={"memories": memories, "count": len(memories)})


@app.delete("/api/memory/reset", response_model=MemoryResponse)
def api_reset(
    domain: str = Query(..., description="领域"),
    user_id: str = Query(..., description="用户ID"),
):
    """清空用户记忆。"""
    valid = ["medical", "tourism", "education"]
    if domain not in valid:
        raise HTTPException(400, detail=f"无效领域: {domain}")
    ok = processor.reset_user_memory(domain, user_id)
    return MemoryResponse(success=ok,
        message="已清空" if ok else "清空失败")


@app.post("/api/chat")
async def api_chat(request: Request):
    """调用 DeepSeek 生成回复，后端自动注入长期记忆并同步写回。
    请求: {"messages":[...], "domain":"medical", "user_id":"P1", "inject_memory":true}
    响应: {"reply":"...", "stored":true, "used_memory_count":1}"""
    body = await request.json()
    messages = body.get("messages", [])
    domain = body.get("domain", "medical")
    user_id = body.get("user_id", "default")
    inject_memory = body.get("inject_memory", True)
    memory_injected = body.get("memory_injected", False)
    memory_query = body.get("memory_query")
    top_k = body.get("top_k")
    try:
        chat_result = processor.chat_with_memory(
            domain=domain,
            user_id=user_id,
            messages=messages,
            top_k=top_k,
            memory_query=memory_query,
            inject_memory=inject_memory,
            memory_injected=memory_injected,
            temperature=0.7,
            max_tokens=2000,
        )
        reply = chat_result["reply"]
        prepared_messages = chat_result["messages"]

        conv_text = "\n".join(
            f"{'用户' if m['role']=='user' else '助手'}：{m['content']}"
            for m in prepared_messages if m['role'] in ('user', 'assistant')
        )
        conv_text += f"\n助手：{reply}"
        processor.process_conversation(domain, user_id, conv_text, metadata={
            "source": "api_chat",
            "memory_query": chat_result.get("memory_query", ""),
            "used_memory_count": chat_result.get("used_memory_count", 0),
        })
        return {
            "reply": reply,
            "stored": True,
            "used_memory_count": chat_result.get("used_memory_count", 0),
            "memory_context": chat_result.get("memory_context", ""),
        }
    except Exception as e:
        traceback.print_exc()
        return {
            "reply": f"AI服务暂不可用: {str(e)[:200]}",
            "stored": False,
            "used_memory_count": 0,
            "memory_context": "",
        }


@app.get("/api/health")
def api_health():
    """健康检查。"""
    ok = processor.memory.health() if processor else False
    return {"status": "ok" if ok else "degraded", "mem0": "connected" if ok else "down"}


# ============================================================
# 启动入口
# ============================================================
def resolve_bridge_port():
    """解析并选择可用的桥接端口。"""
    try:
        requested_port = int(os.getenv("BRIDGE_PORT", "8008"))
    except ValueError:
        requested_port = 8008

    for port in range(requested_port, requested_port + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return requested_port, port

    return requested_port, requested_port


if __name__ == "__main__":
    requested_port, port = resolve_bridge_port()

    print("=" * 55)
    print("  多领域智能体长期记忆系统")
    if port != requested_port:
        print(f"  默认端口 {requested_port} 已占用，自动切换到 {port}")
    print(f"  对话页面: http://localhost:{port}")
    print(f"  API文档:  http://localhost:{port}/docs")
    print("=" * 55)
    uvicorn.run(app, host="0.0.0.0", port=port)
