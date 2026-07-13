# -*- coding: utf-8 -*-  # 工单18：指定源码编码为 UTF-8。
"""main.py - 工单18智能助教项目的 FastAPI 启动入口。"""  # 工单18：声明当前文件功能。

from __future__ import annotations  # 工单18：启用延迟类型注解。

from contextlib import asynccontextmanager  # 工单18：导入生命周期上下文工具。

import uvicorn  # 工单18：导入 Uvicorn 运行器。
from fastapi import FastAPI  # 工单18：导入 FastAPI 应用类。
from fastapi.middleware.cors import CORSMiddleware  # 工单18：导入跨域中间件。
from fastapi.responses import FileResponse  # 工单18：导入文件响应类。
from fastapi.staticfiles import StaticFiles  # 工单18：导入静态文件挂载类。

from app.config import HOST  # 工单18：导入服务监听地址。
from app.config import PORT  # 工单18：导入服务监听端口。
from app.config import STATIC_DIR  # 工单18：导入静态目录配置。
from app.config import ensure_directories  # 工单18：导入目录初始化函数。
from app.config import public_origin_list  # 工单18：导入跨域来源函数。
from app.routes import router  # 工单18：导入业务路由对象。
from app.state import ensure_state_file  # 工单18：导入状态文件初始化函数。


@asynccontextmanager  # 工单18：声明应用生命周期管理器。
async def lifespan(app: FastAPI):  # 工单18：定义应用启动与关闭过程。
    ensure_directories()  # 工单18：启动时确保运行目录存在。
    ensure_state_file()  # 工单18：启动时确保状态文件存在。
    yield  # 工单18：将控制权交回给应用主循环。


app = FastAPI(  # 工单18：创建 FastAPI 应用实例。
    title="工单18-教育智能体-智能助教V1.0",  # 工单18：设置应用标题。
    description="支持教师/学生私有知识库、公有知识库、混合检索、双模型切换与前端工作台。",  # 工单18：设置应用描述。
    version="1.0.0",  # 工单18：设置应用版本号。
    lifespan=lifespan,  # 工单18：挂载生命周期管理器。
)  # 工单18：结束应用实例创建。
app.add_middleware(  # 工单18：为应用添加跨域支持。
    CORSMiddleware,  # 工单18：指定跨域中间件类型。
    allow_origins=public_origin_list(),  # 工单18：设置允许访问来源列表。
    allow_credentials=True,  # 工单18：允许携带凭证访问。
    allow_methods=["*"],  # 工单18：允许全部 HTTP 方法。
    allow_headers=["*"],  # 工单18：允许全部请求头。
)  # 工单18：结束跨域中间件配置。
app.include_router(router)  # 工单18：注册主业务路由。
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")  # 工单18：挂载静态资源目录。


@app.get("/")  # 工单18：注册首页路由。
def index():  # 工单18：返回前端主页文件。
    return FileResponse(STATIC_DIR / "index.html")  # 工单18：输出静态首页。


@app.get("/health")  # 工单18：注册健康检查接口。
def health() -> dict:  # 工单18：返回应用健康状态。
    return {"status": "ok", "port": PORT}  # 工单18：输出服务可用信息。


if __name__ == "__main__":  # 工单18：判断是否以脚本方式直接运行。
    uvicorn.run("main:app", host=HOST, port=PORT, reload=False)  # 工单18：启动本地开发服务。
