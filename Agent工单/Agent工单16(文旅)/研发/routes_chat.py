# -*- coding: utf-8 -*-
# 工单编号：人工智能CV-AIGC-16-【必选】文旅Agent任务工单-需求分析与功能设计V1.1-20260306
"""
routes_chat.py - AI对话相关路由
功能：注册 /api/chat（流式对话）、/api/quick-command（快捷指令）、/api/search（知识检索）
所有对话接口均使用SSE流式输出，前端实时渲染AI回复
"""

from fastapi import APIRouter  # FastAPI路由分组
from fastapi.responses import StreamingResponse  # SSE流式响应
from pydantic import BaseModel  # 请求体数据模型

# 导入提示词模块和LLM调用模块
from prompts import SYSTEM_PROMPT, QUICK_COMMAND_PROMPTS  # 系统提示词和快捷指令提示词
from llm_client import stream_llm  # 流式LLM调用函数

# ============================================================
# 创建路由组 - 前缀 /api
# ============================================================
router = APIRouter(prefix="/api", tags=["AI对话"])  # 路由前缀/api


# ============================================================
# 请求体数据模型
# ============================================================
class ChatRequest(BaseModel):
    """对话请求模型"""
    message: str  # 用户消息内容
    provider: str = "kimi"  # 模型选择，默认kimi


class QuickCommandRequest(BaseModel):
    """快捷指令请求模型"""
    command: str  # 指令名称
    provider: str = "kimi"  # 模型选择


# ============================================================
# POST /api/chat - AI对话接口（流式SSE）
# ============================================================
@router.post("/chat")  # 注册POST路由
async def chat(req: ChatRequest):
    """处理AI对话请求，返回SSE流式响应"""
    # 构建消息列表：系统提示词 + 用户消息
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},  # 设定AI角色
        {"role": "user", "content": req.message},  # 用户输入
    ]
    # 返回SSE流式响应
    return StreamingResponse(
        stream_llm(req.provider, messages),  # 流式LLM异步生成器
        media_type="text/event-stream",  # SSE内容类型
        headers={
            "Cache-Control": "no-cache",  # 禁用缓存
            "Connection": "keep-alive",  # 保持连接
            "X-Accel-Buffering": "no",  # 禁用nginx缓冲
        },
    )


# ============================================================
# POST /api/quick-command - 快捷指令接口（流式SSE）
# ============================================================
@router.post("/quick-command")  # 注册POST路由
async def quick_command(req: QuickCommandRequest):
    """执行5个快捷指令之一，返回SSE流式响应"""
    # 获取指令对应的提示词，找不到则默认用资源挖掘
    cmd_prompt = QUICK_COMMAND_PROMPTS.get(req.command, QUICK_COMMAND_PROMPTS["资源挖掘"])
    # 构建消息：系统提示词 + 指令专用提示词
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},  # AI角色
        {"role": "user", "content": cmd_prompt},  # 指令专用prompt
    ]
    # 返回流式响应（temperature=0.8增加创意性）
    return StreamingResponse(
        stream_llm(req.provider, messages, temperature=0.8),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


# ============================================================
# POST /api/search - 知识检索接口（流式SSE）
# ============================================================
@router.post("/search")  # 注册POST路由
async def search_knowledge(req: ChatRequest):
    """文旅知识检索，LLM模拟RAG效果"""
    topic = req.message  # 搜索主题
    # 构造检索prompt（用字符串拼接避免弯引号编码问题）
    line1 = "请以文旅知识库专家的身份，搜索并整理关于 [" + topic + "] 的相关信息。\n"
    line2 = "要求：\n"
    line3 = "1. 提供准确的历史文化背景\n"
    line4 = "2. 包含实用的游览信息（如有）\n"
    line5 = "3. 关联相关的文化元素（建筑、民俗、美食等）\n"
    line6 = "4. 给出进一步探索的建议\n"
    line7 = "请输出结构化的知识检索结果。"
    search_prompt = line1 + line2 + line3 + line4 + line5 + line6 + line7  # 拼接完整prompt

    # 构建消息
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},  # AI角色
        {"role": "user", "content": search_prompt},  # 检索任务
    ]
    # 返回流式响应（temperature=0.5保证准确性）
    return StreamingResponse(
        stream_llm(req.provider, messages, temperature=0.5),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
