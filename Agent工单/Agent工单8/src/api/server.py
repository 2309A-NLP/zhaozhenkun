"""
src/api/server.py - FastAPI Web服务器
功能: 负责装配首页、静态资源、REST API 与 WebSocket 路由。
说明: WebSocket 具体消息处理已经拆到独立模块，避免本文件继续膨胀。
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from src.api.routes import init as init_routes
from src.api.routes import router
from src.api.video_stream import init as init_video
from src.api.video_stream import router as video_router
from src.api.websocket_endpoint import init as init_websocket
from src.api.websocket_endpoint import register_websocket

logger = logging.getLogger(__name__)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def read_html():
    """读取前端页面，返回 HTML 字符串；文件缺失时返回错误页。"""
    path = os.path.join(ROOT, "static", "index.html")
    logger.info(f"HTML路径: {path} 存在={os.path.exists(path)}")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as file:
            return file.read()
    return "<h2>static/index.html 未找到</h2><p>路径: " + path + "</p>"


def start_server(config, session_manager, pipeline):
    """构建 FastAPI 应用并启动 uvicorn。"""
    app = FastAPI(title="实时数字人交互系统")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def index():
        """首页直接返回静态 HTML，确保首次启动就能访问。"""
        return HTMLResponse(content=read_html())

    @app.get("/ping")
    async def ping():
        """极简健康检查，便于部署后快速确认服务已启动。"""
        return {"ok": True, "root": ROOT}

    # 先注入 WebSocket 依赖，再注册统一入口，确保文本与语音都走同一处理器。
    init_websocket(session_manager, pipeline)
    register_websocket(app)

    static_dir = os.path.join(ROOT, "static")
    if os.path.exists(static_dir):
        from fastapi.staticfiles import StaticFiles

        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # REST API 与视频流继续沿用原有初始化方式，避免扩大改动面。
    init_routes(session_manager, pipeline, config)
    init_video(session_manager, pipeline, config)
    app.include_router(router)
    app.include_router(video_router)

    import uvicorn

    host = config.server.host
    port = config.server.port
    logger.info(f"服务启动: http://localhost:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")
