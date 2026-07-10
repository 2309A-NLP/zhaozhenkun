# -*- coding: utf-8 -*-
# 工单编号：人工智能CV-AIGC-16-【必选】文旅Agent任务工单-需求分析与功能设计V1.1-20260306
"""
server.py - 文旅创新智脑AI智能体服务端入口
功能：启动FastAPI服务，注册所有API路由，提供前端静态页面
启动后访问 http://localhost:8765 进入交互界面
依赖模块：prompts(提示词) / llm_client(LLM调用) / ppt_generator(PPT生成)
          / routes_chat(对话路由) / routes_generate(生成路由)
"""

from pathlib import Path  # 路径处理

from fastapi import FastAPI  # FastAPI框架
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse  # HTML/JSON/文件响应
from fastapi.middleware.cors import CORSMiddleware  # 跨域中间件
from fastapi.staticfiles import StaticFiles  # 静态文件服务

# 导入路由模块
from routes_chat import router as chat_router  # 对话相关路由
from routes_generate import router as generate_router  # 内容生成相关路由

# ============================================================
# 项目根目录
# ============================================================
PROJECT_ROOT = Path(__file__).parent  # 当前文件所在目录（研发/）

# ============================================================
# 创建FastAPI应用
# ============================================================
app = FastAPI(
    title="文旅创新智脑 AI智能体",  # API文档标题
    version="2.0",  # 版本号
    description="工单CV-AIGC-16 · 数字人导览 · 多模态RAG · AIGC生成 · Kimi/DeepSeek/千问驱动",
)  # 创建FastAPI实例

# ============================================================
# CORS跨域配置 - 允许前端跨域访问
# ============================================================
app.add_middleware(
    CORSMiddleware,  # CORS中间件
    allow_origins=["*"],  # 允许所有来源（开发阶段）
    allow_credentials=True,  # 允许携带凭证
    allow_methods=["*"],  # 允许所有HTTP方法
    allow_headers=["*"],  # 允许所有请求头
)  # 使用CORSMiddleware处理跨域

# ============================================================
# 注册路由
# ============================================================
app.include_router(chat_router)  # 注册对话路由（/api/chat, /api/quick-command, /api/search）
app.include_router(generate_router)  # 注册生成路由（/api/generate-ppt, /api/generate-flowchart, /api/download）

# ============================================================
# GET /api/health - 健康检查
# ============================================================
@app.get("/api/health")  # 注册GET路由
async def health():
    """返回服务健康状态和可用模型列表"""
    return {
        "status": "ok",  # 服务状态
        "agent": "文旅小智",  # AI智能体名称
        "version": "2.0",  # 版本号
        "providers": ["kimi", "deepseek", "qwen"],  # 可用模型列表
    }  # JSON响应


# ============================================================
# GET / - 前端入口页面
# ============================================================
@app.get("/")  # 根路径
async def serve_frontend():
    """提供前端HTML页面"""
    html_path = PROJECT_ROOT / "prototype" / "index.html"  # 前端文件路径
    if html_path.exists():  # 文件存在
        return HTMLResponse(html_path.read_text(encoding="utf-8"))  # 返回HTML内容
    return HTMLResponse("<h1>前端文件未找到</h1>")  # 文件缺失提示


# ============================================================
# 挂载静态文件 - 让CSS/JS/Mermaid等文件可被浏览器加载
# ============================================================
prototype_dir = PROJECT_ROOT / "prototype"  # 原型目录路径
if prototype_dir.exists():  # 目录存在
    app.mount("/", StaticFiles(directory=str(prototype_dir), html=False), name="static")  # 挂载静态文件


# ============================================================
# 启动入口
# ============================================================
if __name__ == "__main__":  # 直接运行此文件时
    import uvicorn  # ASGI服务器

    # 打印启动横幅
    print("=" * 56)  # 分隔线
    print("  🧠 文旅创新智脑 - AI智能体服务端 v2.0")  # 项目名
    print("  工单编号: CV-AIGC-16")  # 工单编号
    print("=" * 56)  # 分隔线
    print()
    print("  🌐 前端页面: http://localhost:8765")  # 访问地址
    print("  📡 API文档:  http://localhost:8765/docs")  # API文档
    print("  🤖 模型: Kimi / DeepSeek / 千问")  # 可用模型
    print()
    print("  启动中...")  # 启动提示
    # 启动uvicorn服务器
    uvicorn.run(app, host="0.0.0.0", port=8765, log_level="info")  # 监听8765端口
