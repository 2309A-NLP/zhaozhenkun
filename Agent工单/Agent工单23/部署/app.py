#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
部署 — PAI-EAS HTTP 服务主程序
==============================================================================
功能: 将 Research Agent 部署为标准的 PAI-EAS HTTP 服务。
      提供 POST /api/answer 接口，接收自然语言问题，返回文本答案。
      根路径 / 返回交互式网页聊天界面。
      符合阿里云天池竞赛评测接口规范。
用法: python app.py  → 服务启动在 http://0.0.0.0:8000
     浏览器打开 http://localhost:8000 即可使用网页界面
==============================================================================
"""
import json  # JSON 解析
import os  # 环境变量和文件路径
import sys  # 系统接口
import time  # 计时
import traceback  # 异常跟踪
from contextlib import asynccontextmanager  # 异步上下文管理器
from typing import Optional  # 类型注解

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 项目根目录

from fastapi import FastAPI, HTTPException, Request  # FastAPI 框架
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse  # JSON、HTML 和流式响应
from pydantic import BaseModel, Field  # 数据验证模型
import uvicorn  # ASGI 服务器

from 研发.agent_core import ResearchAgent  # 导入 Research Agent
from 研发.agent_stream import StreamAgent  # 导入流式 Agent
from 研发.config import (  # 导入配置
    EAS_SERVICE_PORT, EAS_SERVICE_HOST, VERBOSE,  # 服务配置
    validate_config, print_config,  # 配置函数
)
from 优化.answer_normalizer import normalize_answer  # 答案归一化


# ============================================================
# 一、Pydantic 数据模型
# ============================================================

class QuestionRequest(BaseModel):  # 问题请求模型
    """问题请求体模型。"""
    question: str = Field(..., description="自然语言问题", min_length=1)  # 问题文本（必填）
    id: Optional[int] = Field(None, description="题目 ID（可选）")  # 题目 ID
    lang: Optional[str] = Field("auto", description="搜索语言: auto/zh/en")  # 搜索语言偏好


class AnswerResponse(BaseModel):  # 答案响应模型
    """答案响应体模型。"""
    id: Optional[int] = Field(None, description="题目 ID")  # 题目 ID
    answer: str = Field("", description="答案文本")  # 答案文本
    success: bool = Field(True, description="是否成功")  # 成功标志


# ============================================================
# 二、全局 Agent 单例
# ============================================================

_agent_instance: Optional[ResearchAgent] = None  # Agent 单例（懒加载）


def get_agent() -> ResearchAgent:  # 获取或创建 Agent 实例
    """获取全局 Research Agent 单例（懒加载，首次调用时初始化）。"""
    global _agent_instance  # 声明全局变量
    if _agent_instance is None:  # 未初始化
        _agent_instance = ResearchAgent(verbose=VERBOSE)  # 创建实例
    return _agent_instance  # 返回实例


# ============================================================
# 三、应用生命周期管理
# ============================================================

@asynccontextmanager  # 将函数转为异步上下文管理器
async def lifespan(app: FastAPI):  # 应用生命周期回调
    """管理应用启动和关闭时的初始化/清理操作。"""
    # === 启动逻辑 ===
    print("=" * 50)  # 分隔线
    print("  Research Agent Service 启动中...")  # 启动提示
    print("=" * 50)  # 分隔线
    print_config()  # 打印配置
    validate_config()  # 验证配置

    # 预热 Agent 实例
    try:  # 尝试初始化 Agent
        agent = get_agent()  # 初始化 Agent
        print("  Agent 实例初始化成功")  # 初始化成功
    except Exception as e:  # 初始化失败
        print(f"  Agent 初始化警告: {e}")  # 打印警告（不阻止启动）

    print(f"  服务地址: http://{EAS_SERVICE_HOST}:{EAS_SERVICE_PORT}")  # 打印服务地址
    print(f"  网页界面: http://localhost:{EAS_SERVICE_PORT}")  # 打印网页地址
    print("=" * 50)  # 分隔线

    yield  # 服务运行中（此处挂起直到关闭）

    # === 关闭逻辑 ===
    print("Research Agent Service 正在关闭...")  # 关闭提示


# ============================================================
# 四、FastAPI 应用创建
# ============================================================

app = FastAPI(  # 创建 FastAPI 应用实例（含生命周期）
    title="Research Agent Service",  # 服务名称
    description="基于 ReAct 模式的 Research Agent，支持多步推理和联网搜索",  # 服务描述
    version="1.0.0",  # 版本号
    lifespan=lifespan,  # 生命周期回调
)


# ============================================================
# 五、API 路由
# ============================================================

@app.get("/", response_class=HTMLResponse)  # 根路由，返回网页界面
async def root():  # 服务网页界面
    """返回 Research Agent 交互网页界面。"""
    html_path = os.path.join(  # 构建 HTML 文件路径
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),  # 项目根目录
        "frontend", "agent.html"  # 前端 HTML 文件
    )
    if os.path.exists(html_path):  # 文件存在
        with open(html_path, "r", encoding="utf-8") as f:  # 打开文件
            return f.read()  # 返回 HTML 内容
    # 备用：返回简单提示页面
    return """<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Research Agent</title></head>
<body style="font-family:sans-serif;max-width:600px;margin:100px auto;text-align:center;background:#0d1117;color:#c9d1d9">
<h1>🔬 Research Agent</h1><p>服务运行中，但前端文件未找到。</p>
<p>请使用 API: <code style="background:#161b22;padding:4px 8px;border-radius:4px">POST /api/answer</code></p>
<pre style="background:#161b22;padding:12px;border-radius:6px;text-align:left;color:#58a6ff">
curl -X POST http://localhost:8000/api/answer \
  -H "Content-Type: application/json" \
  -d '{"question": "你的问题"}'</pre>
</body></html>"""  # 返回备用 HTML


@app.get("/api/health")  # 健康检查接口
async def health_check():  # 健康检查处理函数
    """健康检查接口，返回服务状态。"""
    try:  # 检查 Agent 可用性
        agent = get_agent()  # 获取 Agent（验证初始化）
        return {  # 健康状态
            "status": "healthy",  # 状态正常
            "agent_ready": True,  # Agent 已就绪
            "timestamp": time.time(),  # 时间戳
        }
    except Exception as e:  # Agent 初始化失败
        return JSONResponse(  # 返回异常状态
            status_code=503,  # HTTP 503
            content={"status": "unhealthy", "error": str(e)},  # 异常信息
        )


@app.post("/api/answer", response_model=AnswerResponse)  # 核心答案接口
async def answer_question(request: QuestionRequest):  # 处理问题请求
    """接收自然语言问题，返回 Research Agent 的答案。"""
    if not request.question or not request.question.strip():  # 问题为空
        raise HTTPException(status_code=400, detail="问题不能为空")  # 返回 400 错误

    try:  # 执行 Agent 研究
        agent = get_agent()  # 获取 Agent 实例
        result = agent.research(request.question.strip())  # 执行研究
        raw_answer = result.get("answer", "")  # 获取原始答案
        normalized = normalize_answer(raw_answer, request.question)  # 归一化

        return AnswerResponse(  # 返回答案响应
            id=request.id,  # 保持原 ID
            answer=normalized,  # 归一化后的答案
            success=True,  # 成功
        )
    except Exception as e:  # 处理异常
        if VERBOSE:  # 详细日志模式
            print(f"[API Error] {traceback.format_exc()}")  # 打印错误堆栈
        return AnswerResponse(  # 返回错误答案
            id=request.id,  # 保持原 ID
            answer="",  # 空答案
            success=False,  # 失败
        )


@app.post("/api/answer/stream")  # SSE 流式答案接口
async def answer_stream(request: QuestionRequest):  # 流式返回 Agent 推理过程
    """SSE (Server-Sent Events) 流式接口，实时推送 Agent 推理每一步进度。

    事件类型: start | thinking | searching | results | answer | error
    前端使用 EventSource 或 fetch + ReadableStream 接收。
    """
    import asyncio  # 异步 IO

    async def event_generator():  # 异步生成器，逐事件推送
        stream_agent = StreamAgent()  # 创建流式 Agent（独立实例）
        lang = request.lang or "auto"  # 获取语言偏好，默认自动
        loop = asyncio.get_event_loop()  # 获取事件循环

        try:  # 执行流式推理
            gen = stream_agent.research_stream(request.question.strip(), lang=lang)  # 传入语言偏好
            while True:  # 循环消费
                try:  # 获取下一个事件
                    event = await loop.run_in_executor(None, next, gen)  # 线程池执行
                    json_str = json.dumps(event, ensure_ascii=False)  # 序列化
                    yield f"data: {json_str}\n\n"  # SSE 推送
                    if event.get("type") in ("answer", "error"):  # 终止事件
                        break  # 结束
                except StopIteration:  # 生成器耗尽
                    break  # 结束
        except Exception as e:  # 异常处理
            yield f"data: {json.dumps({'type':'error','content':str(e)},ensure_ascii=False)}\n\n"  # 推送错误
        finally:  # 清理
            yield "data: [DONE]\n\n"  # 结束标记

    return StreamingResponse(  # 返回流式响应
        event_generator(),  # 事件生成器
        media_type="text/event-stream",  # SSE MIME 类型
        headers={  # SSE 相关头
            "Cache-Control": "no-cache",  # 禁用缓存
            "Connection": "keep-alive",  # 保持连接
            "X-Accel-Buffering": "no",  # 禁用 Nginx 缓冲
        },
    )


@app.post("/api/batch")  # 批量处理接口
async def batch_answer(request: Request):  # 批量处理
    """批量处理问题接口。请求体: [{"id": 0, "question": "..."}, ...]"""
    try:  # 解析请求体
        body = await request.json()  # 获取 JSON 数据
    except json.JSONDecodeError:  # JSON 解析失败
        raise HTTPException(status_code=400, detail="请求体必须是 JSON 数组")  # 返回 400

    if not isinstance(body, list):  # 不是数组
        raise HTTPException(status_code=400, detail="请求体必须是 JSON 数组")  # 返回 400
    if len(body) > 100:  # 批量限制
        raise HTTPException(status_code=400, detail="单次批量请求最多 100 道题")  # 返回 400

    agent = get_agent()  # 获取 Agent 实例
    results = []  # 结果列表

    for item in body:  # 遍历每道题
        qid = item.get("id", -1)  # 获取 ID
        question = item.get("question", "")  # 获取问题
        if not question:  # 问题为空
            results.append({"id": qid, "answer": "", "error": "问题为空"})  # 空答案
            continue  # 跳过

        try:  # 执行研究
            result = agent.research(question)  # Agent 研究
            answer = normalize_answer(result.get("answer", ""), question)  # 归一化
            results.append({"id": qid, "answer": answer})  # 添加结果
        except Exception as e:  # 处理失败
            results.append({"id": qid, "answer": "", "error": str(e)})  # 错误结果

    return JSONResponse(content=results)  # 返回结果列表


# ============================================================
# 六、入口
# ============================================================
if __name__ == "__main__":  # 脚本直接运行入口
    import socket  # 用于检测端口是否可用

    def _find_free_port(start_port: int) -> int:  # 自动寻找可用端口
        """如果默认端口被占用，自动尝试下一个端口。"""
        for port in range(start_port, start_port + 100):  # 尝试 100 个端口
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:  # 创建测试 socket
                if s.connect_ex(('127.0.0.1', port)) != 0:  # 端口可用（连接失败=端口空闲）
                    return port  # 返回可用端口
        return start_port  # 全部占用则返回默认端口

    actual_port = _find_free_port(EAS_SERVICE_PORT)  # 自动查找可用端口
    if actual_port != EAS_SERVICE_PORT:  # 端口变化
        print(f"  ⚠️ 端口 {EAS_SERVICE_PORT} 被占用，自动使用端口 {actual_port}")  # 提示

    uvicorn.run(  # 启动 uvicorn 服务器
        app,  # FastAPI 应用
        host=EAS_SERVICE_HOST,  # 监听地址
        port=actual_port,  # 使用可用端口
        log_level="info",  # 日志级别
        access_log=True,  # 启用访问日志
    )
