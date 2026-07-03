"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
================================================================================
医疗智能体-影像分析系统 主入口
功能：VQA视觉问答 | MRG报告生成 | RAG知识检索 | 挂号管理 | 健康咨询
架构：FastAPI 单文件后端 + 内联前端（HTML/CSS/JS 全部从内存读取，零外部依赖）
启动：python main.py  或  uvicorn main:app --port 8080
================================================================================
"""
import time, re, logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse

from config import UPLOAD_DIR, API_HOST, API_PORT, CORS_ORIGINS
from utils.logger import get_logger
_log = get_logger("main")  # 主模块日志

# 文件名安全校验正则：只允许字母/数字/中文/下划线/点/横线
_SAFE = re.compile(r'^[\w一-鿿.-]+$')

# ============================================================
# 1. 导入所有 API 子路由
# ============================================================
from api.upload import router as upload_router              # 文件上传
from api.vqa import router as vqa_router                    # VQA 视觉问答
from api.mrg import router as mrg_router                    # MRG 报告生成
from api.rag import router as rag_router                    # RAG 知识检索
from api.assistant import router as assistant_router        # 健康助理对话
from api.registration import router as registration_router  # 挂号管理
from api.consultation import router as consultation_router  # 健康咨询（知识图谱）

# ============================================================
# 2. 预加载前端所有文件到内存
#    为什么这样做？Windows 下文件路径编码问题可能导致 FileResponse 失败
#    直接读到内存，启动时一次性完成，请求时直接返回字符串，100% 可靠
# ============================================================
FDIR = Path(__file__).resolve().parent.parent / "frontend"  # 前端目录

def _r(name):
    """读取前端文件，不存在则返回空字符串（不抛异常）"""
    p = FDIR / name
    return p.read_text(encoding="utf-8") if p.exists() else ""

# 逐文件读取
html = _r("index.html")        # 主页面 HTML
css  = _r("css/style.css")     # 样式表
js_a = _r("js/app.js")         # 主应用逻辑（上传、Tab切换、消息渲染）
js_v = _r("js/vqa.js")         # VQA 问答
js_m = _r("js/mrg.js")         # MRG 报告
js_r = _r("js/rag.js")         # RAG 检索
js_ast = _r("js/assistant.js") # 健康助理（挂号+咨询入口）

# ============================================================
# 3. 构建完全自包含的单文件 HTML（CSS + JS 全部内联）
#    浏览器只需一个 HTTP 请求即可获取全部内容，零外部依赖
# ============================================================
FULL = "<!DOCTYPE html>\n<html lang='zh-CN'>\n<head>\n<meta charset='UTF-8'>\n"
FULL += "<meta name='viewport' content='width=device-width,initial-scale=1.0'>\n"
FULL += "<title>医疗智能体-影像分析系统</title>\n"
if css: FULL += "<style>\n" + css + "\n</style>\n"          # 内联 CSS
FULL += "</head>\n<body>\n<div id='app-root'>\n"

# 从原始 HTML 中提取 <body> 内容（去掉 <!DOCTYPE>, <html>, <head> 标签）
bs = html.find("<body>"); be = html.find("</body>")
if bs >= 0 and be >= 0:
    FULL += html[bs+6:be] + "\n"  # +6 跳过 "<body>" 标签
else:
    FULL += "<h1 style='color:red;text-align:center;padding:100px'>❌ 前端加载失败</h1>\n"
FULL += '</div>\n'

# 内联所有 JS 文件（按加载顺序）
for js in [js_a, js_v, js_m, js_r, js_ast]:
    if js: FULL += "<script>\n" + js + "\n</script>\n"
FULL += "</body>\n</html>"

# 统计信息
_log.info("单文件HTML: %d bytes (CSS:%d JS:%d)",
    len(FULL), len(css), len(js_a)+len(js_v)+len(js_m)+len(js_r)+len(js_ast))

# ============================================================
# 4. FastAPI 应用初始化
# ============================================================
app = FastAPI(
    title="医疗智能体-影像分析系统",
    version="1.0.0",
    docs_url="/docs",    # Swagger UI
    redoc_url=None,      # 不启用 ReDoc（减少启动时间）
)

# CORS 跨域中间件
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS,
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# ============================================================
# 5. 响应时间监控中间件
# ============================================================
@app.middleware("http")
async def timer(request: Request, call_next):
    """记录每个请求的处理时间，注入 X-Process-Time-Ms 响应头"""
    t0 = time.time()
    resp = await call_next(request)                 # 执行实际的请求处理
    ms = (time.time() - t0) * 1000                  # 计算耗时（毫秒）
    resp.headers["X-Process-Time-Ms"] = f"{ms:.2f}" # 注入响应头
    return resp

# ============================================================
# 6. 注册所有 API 路由
# ============================================================
app.include_router(upload_router)        # POST /api/upload/image  /document
app.include_router(vqa_router)          # POST /api/vqa/ask
app.include_router(mrg_router)          # POST /api/mrg/generate
app.include_router(rag_router)          # POST /api/rag/query  /ingest  GET /stats
app.include_router(assistant_router)    # POST /api/assistant/chat
app.include_router(registration_router) # POST /api/registration/chat
app.include_router(consultation_router) # POST /api/consultation/chat

# ============================================================
# 7. 前端页面路由
# ============================================================
@app.get("/")
def index():
    """返回自包含的单文件 HTML（CSS+JS 全部内联）"""
    return HTMLResponse(content=FULL)

@app.get("/api/images/{filename}")
async def get_image(filename: str):
    """安全地返回用户上传的图片（防路径穿越）"""
    # 文件名只能是安全字符，且不能含 ..
    if not _SAFE.match(filename) or ".." in filename:
        return JSONResponse(status_code=400, content={"error":"非法文件名"})
    fp = (UPLOAD_DIR / filename).resolve()
    # 确保解析后的绝对路径还在 UPLOAD_DIR 内（防符号链接穿越）
    if not str(fp).startswith(str(UPLOAD_DIR.resolve())):
        return JSONResponse(status_code=403, content={"error":"禁止访问"})
    if not fp.is_file():
        return JSONResponse(status_code=404, content={"error":"文件不存在"})
    return FileResponse(fp)  # FastAPI 自动设置正确的 Content-Type

@app.get("/api/health")
def health():
    """健康检查端点：返回服务状态 + 知识库文档数"""
    try:
        from rag.vector_store import get_vector_store
        docs = get_vector_store().count()
    except:
        docs = -1  # ChromaDB 故障时返回 -1，不影响其他功能
    return {"status":"healthy", "knowledge_base_docs":docs,
            "service":"医疗智能体-影像分析系统", "version":"1.0.0"}

# ============================================================
# 8. 全局异常处理
# ============================================================
@app.exception_handler(Exception)
async def on_error(request: Request, exc: Exception):
    """捕获所有未处理的异常，记录日志并返回统一 JSON 错误格式"""
    eid = str(int(time.time()*1000))[-8:]  # 生成8位错误ID
    _log.exception("[%s] %s %s", eid, request.method, request.url.path)
    return JSONResponse(status_code=500, content={
        "error":"服务器错误", "error_id":eid})

# ============================================================
# 9. 启动入口
# ============================================================
if __name__ == "__main__":
    import uvicorn, socket

    # 检测端口是否可用，被占用则自动尝试下一个
    port = API_PORT
    for offset in range(10):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", port+offset)); s.close(); port += offset; break
        except OSError:
            s.close()
    else:
        _log.error("无法绑定端口 %d-%d", API_PORT, API_PORT+9); exit(1)

    _log.info("="*50)
    _log.info("医疗智能体-影像分析系统 V1.0")
    _log.info("请在浏览器打开: http://127.0.0.1:%d", port)
    _log.info("="*50)
    uvicorn.run("main:app", host=API_HOST, port=port, reload=False, log_level="info")
