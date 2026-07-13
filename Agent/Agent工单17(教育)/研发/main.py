from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import get_settings, get_data_dirs
from knowledge_base import knowledge_base_service
from routes_core import router as core_router
from routes_export import router as export_router
from routes_knowledge import router as knowledge_router
from routes_lesson_prep import router as lesson_prep_router
from routes_ui import router as ui_router
from routes_version_collab import router as version_collab_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 60)
    print("教育Agent智能备课系统 v1.0 正在启动...")
    print(f"工单编号：{get_settings().WORK_ORDER_ID[:40]}")
    get_data_dirs()
    knowledge_base_service.init_demo_knowledge()
    port = get_settings().PORT
    print(f"前端首页：http://localhost:{port}/")
    print(f"前端首页：http://127.0.0.1:{port}/")
    print(f"API文档：http://localhost:{port}/docs")
    print(f"API文档：http://127.0.0.1:{port}/docs")
    print("=" * 60)
    yield
    print("应用正在关闭...")


app = FastAPI(
    title="教育Agent智能备课系统",
    description="工单17：教育Agent-教学场景功能分析及智能备课模块",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=get_settings().BASE_STATIC_DIR), name="static")

for router in [
    ui_router,
    core_router,
    lesson_prep_router,
    knowledge_router,
    export_router,
    version_collab_router,
]:
    app.include_router(router)


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else settings.WORKERS,
        log_level=settings.LOG_LEVEL.lower(),
    )
