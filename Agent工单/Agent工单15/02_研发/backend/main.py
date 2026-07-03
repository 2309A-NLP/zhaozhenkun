"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.1
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理 V1.1
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-健康咨询 V1.1
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-MCP V1.0
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-实时语音识别 V1.0
================================================================================
医疗智能体-影像分析系统 主入口
功能：VQA视觉问答 | MRG报告生成 | RAG知识检索 | 挂号管理 | 健康咨询 | 地图MCP | 实时语音识别
架构：FastAPI 单文件后端 + 内联前端（HTML/CSS/JS 全部从内存读取，零外部依赖）
启动：python main.py  或  uvicorn main:app --port 8080
================================================================================
"""
import time, re, logging  # 导入时间处理、正则表达式、日志记录模块
from collections import defaultdict  # 导入 defaultdict 用于速率限制存储的默认列表值
from pathlib import Path  # 导入 Path 用于跨平台的文件路径操作

from fastapi import FastAPI, Request  # 导入 FastAPI 框架和请求对象
from fastapi.middleware.cors import CORSMiddleware  # 导入 CORS 跨域中间件
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse  # 导入 JSON/文件/HTML 三种响应类型

from config import UPLOAD_DIR, API_HOST, API_PORT, CORS_ORIGINS  # 从配置模块导入上传目录和服务器参数
from config import AMAP_JS_API_KEY, AMAP_SECURITY_CODE  # 高德 JS API 配置（前端地图加载所需密钥）
from utils.logger import get_logger  # 导入统一日志工具函数
_log = get_logger("main")  # 获取当前主模块的日志记录器实例

# 文件名安全校验正则：只允许字母/数字/中文/下划线/点/横线（防止路径穿越攻击）
_SAFE = re.compile(r'^[\w一-鿿.-]+$')  # 编译正则表达式，匹配安全文件名（字母数字中文下划线点横线）

# 0. 简易速率限制器（内存实现，无需外部依赖）
#    防止 API 滥用，保护后端 LLM 调用费用
_RATE_LIMIT_WINDOW = 60       # 时间窗口（秒）：每60秒为一个计数周期
_RATE_LIMIT_MAX_REQUESTS = 30 # 每窗口最大请求数（每个客户端 IP 地址最多30次）
_rate_limit_store: dict = defaultdict(list)  # 速率限制存储字典：IP 地址 → 请求时间戳列表

def _check_rate_limit(client_ip: str) -> bool:
    """检查 IP 是否超出速率限制，返回 True=允许，False=拒绝"""
    now = time.time()  # 获取当前 Unix 时间戳（秒，浮点数）
    window_start = now - _RATE_LIMIT_WINDOW  # 计算时间窗口的起始截止时间
    # 清理过期记录（只保留窗口内的时间戳，窗口外的自动丢弃）
    _rate_limit_store[client_ip] = [  # 为该 IP 更新时间戳列表
        ts for ts in _rate_limit_store[client_ip] if ts > window_start  # 过滤：仅保留在窗口内的时间戳
    ]
    if len(_rate_limit_store[client_ip]) >= _RATE_LIMIT_MAX_REQUESTS:  # 如果窗口内请求数已达上限
        return False  # 拒绝该请求（返回 False 表示超出限制）
    _rate_limit_store[client_ip].append(now)  # 将当前请求时间戳追加到该 IP 的记录中
    return True  # 允许该请求（返回 True 表示未超限）

def _cleanup_rate_limit_store():
    """清理速率限制存储中所有过期的 IP 记录（防止内存泄漏）"""
    now = time.time()  # 获取当前 Unix 时间戳
    window_start = now - _RATE_LIMIT_WINDOW  # 计算时间窗口的起始截止时间
    expired_ips = []  # 初始化过期 IP 列表，用于收集需要清理的 IP
    for ip, timestamps in _rate_limit_store.items():  # 遍历速率限制存储中所有 IP 及其时间戳
        fresh = [ts for ts in timestamps if ts > window_start]  # 过滤：只保留窗口内的有效时间戳
        if fresh:  # 如果该 IP 还有有效记录
            _rate_limit_store[ip] = fresh  # 用过滤后的列表替换原有记录
        else:  # 如果该 IP 的所有时间戳都已过期
            expired_ips.append(ip)  # 将该 IP 加入待清理列表
    for ip in expired_ips:  # 遍历所有已过期的 IP
        del _rate_limit_store[ip]  # 从存储字典中彻底删除该 IP 的记录
    return len(expired_ips)  # 返回本次清理掉的 IP 数量

# 1. 导入所有 API 子路由
from api.upload import router as upload_router              # 文件上传模块（图片/文档上传处理）
from api.vqa import router as vqa_router                    # VQA 视觉问答模块（看图回答医学问题）
from api.mrg import router as mrg_router                    # MRG 报告生成模块（医学影像报告自动生成）
from api.rag import router as rag_router                    # RAG 知识检索模块（向量化知识库问答）
from api.assistant import router as assistant_router        # 健康助理对话模块（通用健康咨询）
from api.registration import router as registration_router  # 挂号管理模块（医院科室医生预约）
from api.consultation import router as consultation_router  # 健康咨询模块（基于知识图谱的推理）
from api.asr import router as asr_router                    # 实时语音识别模块（通义听悟 WebSocket 对接）
from api.avatar import router as avatar_router               # 数字人形象模块（SadTalker 面部动画驱动）
from api.map import router as map_router                      # 高德地图 MCP 对接模块（出行/住宿/餐饮查询）
from api.kimi import router as kimi_router                    # Kimi 需求分析模块（Moonshot 推理引擎）

# 2. 预加载前端所有文件到内存
#    为什么这样做？Windows 下文件路径编码问题可能导致 FileResponse 失败
#    直接读到内存，启动时一次性完成，请求时直接返回字符串，100% 可靠
FDIR = Path(__file__).resolve().parent.parent / "frontend"  # 定位前端文件目录（项目根目录下的 frontend 文件夹）

def _r(name):
    """读取前端文件，不存在则返回空字符串（不抛异常）"""
    p = FDIR / name  # 拼接前端文件完整路径
    return p.read_text(encoding="utf-8") if p.exists() else ""  # 文件存在则读取 UTF-8 文本，否则返回空串

# 逐文件读取（启动时一次性加载所有前端资源到内存）
html = _r("index.html")        # 读取主页面 HTML 模板（包含页头、Tab 导航、内容容器）
css  = _r("css/style.css")     # 读取样式表（全局布局、配色、动画效果）
js_a = _r("js/app.js")         # 读取主应用逻辑脚本（文件上传、Tab 切换、消息渲染）
js_v = _r("js/vqa.js")         # 读取 VQA 问答脚本（视觉问答的请求和响应处理）
js_m = _r("js/mrg.js")         # 读取 MRG 报告脚本（报告生成的业务流程控制）
js_r = _r("js/rag.js")         # 读取 RAG 检索脚本（知识库检索的交互逻辑）
js_ast = _r("js/assistant.js") # 读取健康助理脚本（挂号+咨询功能的入口协调）
js_map = _r("js/map.js")       # 读取高德地图脚本（出行/住宿/餐饮查询交互）
js_asr = _r("js/asr.js")       # 读取实时语音识别脚本（通义听悟语音转文字）
js_avatar = _r("js/avatar.js") # 读取数字人形象脚本（上传照片或拍照生成数字人）
js_voice = _r("js/voice.js")   # 读取语音管道脚本（ASR 识别→Agent 处理→TTS 合成 统一流水线）
js_tw = _r("js/tingwu.js")    # 🎙️ 通义听悟脚本（实时语音识别+多语言翻译+会议纪要生成）
js_digi = _r("js/digital.js")  # 🤖 数字人脚本（语音识别+对话+TTS+唇形动画 统一交互）

# 3. 构建完全自包含的单文件 HTML（CSS + JS 全部内联）
#    浏览器只需一个 HTTP 请求即可获取全部内容，零外部依赖
FULL = "<!DOCTYPE html>\n<html lang='zh-CN'>\n<head>\n<meta charset='UTF-8'>\n"  # 构建 HTML5 文档头（声明文档类型、中文语言、UTF-8 编码）
FULL += "<meta name='viewport' content='width=device-width,initial-scale=1.0'>\n"  # 添加移动端视口元标签（适配手机屏幕宽度）
FULL += "<title>医疗智能体-影像分析系统</title>\n"  # 设置浏览器标签页标题
if css: FULL += "<style>\n" + css + "\n</style>\n"          # 如果 CSS 文件存在，将其内联到 <style> 标签中
FULL += "</head>\n<body>\n<div id='app-root'>\n"  # 结束 head 标签，开始 body，创建应用根容器

# 从 HTML 模板中提取 <body> 标签内的内容
bs = html.find("<body>"); be = html.find("</body>")  # 定位 <body> 开始和结束标签的位置
if bs >= 0 and be >= 0:  # 如果两个标签都找到了
    FULL += html[bs+6:be] + "\n"  # +6 跳过 "<body>" 标签，提取标签之间的内容并追加
else:  # 如果 HTML 模板格式异常（缺少 body 标签）
    FULL += "<h1 style='color:red;text-align:center;padding:100px'>❌ 前端加载失败</h1>\n"  # 显示红色的错误提示信息
FULL += '</div>\n'  # 关闭 app-root 容器 div 标签

# 内联所有 JS 文件（按依赖加载顺序排列，确保 app.js 最先执行）
all_js = [js_a, js_v, js_m, js_r, js_ast, js_map, js_asr, js_avatar, js_voice, js_tw, js_digi]  # 将所有 JS 内容按顺序放入列表
for js in all_js:  # 遍历每个 JS 文件的内容
    if js: FULL += "<script>\n" + js + "\n</script>\n"  # 如果非空，将其包裹在 <script> 标签中并追加到 HTML
FULL += "</body>\n</html>"  # 关闭 body 和 html 标签，完成完整页面的构建

# 统计信息（用于启动日志输出）
total_js = sum(len(j) for j in all_js if j)  # 计算所有 JS 文件的总字节数（仅统计非空的文件）
_log.info("单文件HTML: %d bytes (CSS:%d JS:%d)",  # 记录整个自包含 HTML 的字节数
    len(FULL), len(css), total_js)  # 参数：HTML总大小、CSS大小、JS总大小

# 4. FastAPI 应用初始化
app = FastAPI(  # 创建 FastAPI 应用实例
    title="医疗智能体-影像分析系统",  # API 文档标题
    version="1.0.0",  # 服务版本号
    docs_url="/docs",    # Swagger UI 文档页面的访问路径
    redoc_url=None,      # 不启用 ReDoc 文档页面（减少启动内存占用）
)

# CORS 跨域中间件（允许前端页面从不同域名/端口访问后端 API）
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS,  # 注册 CORS 中间件，指定允许的来源域名列表
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])  # 允许携带凭据、所有 HTTP 方法、所有请求头

# 速率限制中间件 —— 防止 API 滥用（每 IP 每分钟最多 N 次请求）
@app.middleware("http")  # 使用装饰器注册 HTTP 请求中间件
async def rate_limit_middleware(request: Request, call_next):  # 异步中间件函数，接收请求和下一个处理函数
    """简易速率限制：每 IP 每分钟最多 N 次请求（本地回环地址豁免）"""
    # 获取客户端 IP（考虑代理/负载均衡：优先从转发头获取真实 IP）
    client_ip = (  # 按优先级解析客户端真实 IP 地址
        request.headers.get("x-forwarded-for", "").split(",")[0].strip() or  # 先尝试从 x-forwarded-for 头获取（反向代理设置）
        request.headers.get("x-real-ip", "") or  # 其次尝试从 x-real-ip 头获取（nginx 设置）
        (request.client.host if request.client else "unknown")  # 最后从直连的客户端地址获取
    )
    # 健康检查、API 文档、静态资源和本地回环地址不限制（跳过速率检查）
    path = request.url.path  # 获取当前请求的 URL 路径
    if path in ("/api/health", "/docs", "/openapi.json") or client_ip in ("127.0.0.1", "::1", "localhost", "testclient"):  # 判断是否为白名单路径或本机
        return await call_next(request)  # 直接放行，不经过速率检查

    if not _check_rate_limit(client_ip):  # 调用速率检查函数，判断该 IP 是否已超限
        _log.warning("速率限制触发: IP=%s path=%s", client_ip, path)  # 记录触发速率限制的警告日志
        return JSONResponse(  # 返回 HTTP 429（Too Many Requests）JSON 响应
            status_code=429,  # HTTP 状态码：请求过多
            content={  # 响应体内容
                "error": "请求过于频繁，请稍后再试",  # 错误提示消息（中文）
                "retry_after_seconds": _RATE_LIMIT_WINDOW,  # 建议客户端等待的秒数
            },
            headers={"Retry-After": str(_RATE_LIMIT_WINDOW)},  # 添加 Retry-After 响应头
        )

    return await call_next(request)  # 速率检查通过，调用下一个处理器处理请求

# 5. 响应时间监控中间件
@app.middleware("http")  # 使用装饰器注册 HTTP 请求中间件
async def timer(request: Request, call_next):  # 异步计时中间件函数
    """记录每个请求的处理时间，注入 X-Process-Time-Ms 响应头"""
    t0 = time.time()  # 记录请求开始时间（Unix 时间戳，秒）
    resp = await call_next(request)                 # 执行实际的请求处理（调用路由处理器）
    ms = (time.time() - t0) * 1000                  # 计算处理耗时并转换为毫秒
    resp.headers["X-Process-Time-Ms"]  = f"{ms:.2f}" # 将处理耗时（保留2位小数）注入自定义响应头
    return resp  # 返回处理完成的响应对象

# 6. 注册所有 API 路由（将各功能模块的路由挂载到 FastAPI 应用上）
app.include_router(upload_router)        # POST /api/upload/image  /document —— 文件上传接口
app.include_router(vqa_router)          # POST /api/vqa/ask —— VQA 视觉问答接口
app.include_router(mrg_router)          # POST /api/mrg/generate —— MRG 报告生成接口
app.include_router(rag_router)          # POST /api/rag/query  /ingest  GET /stats —— RAG 知识检索接口
app.include_router(assistant_router)    # POST /api/assistant/chat —— 健康助理对话接口
app.include_router(registration_router) # POST /api/registration/chat —— 挂号管理对话接口
app.include_router(consultation_router) # POST /api/consultation/chat —— 健康咨询对话接口
app.include_router(asr_router)            # WS /api/asr/ws/realtime  POST /api/asr/process —— 语音识别接口
app.include_router(avatar_router)        # POST /api/avatar/upload|speak  GET /api/avatar/video —— 数字人接口
app.include_router(map_router)            # POST /api/map/search|nearby|directions|chat —— 地图 MCP 接口
app.include_router(kimi_router)           # POST /api/kimi/analyze|chat —— Kimi 需求分析接口

# 7. 前端页面路由
@app.get("/")  # 注册根路径（首页）的 GET 请求处理
def index():  # 首页视图函数
    """返回自包含的单文件 HTML（CSS+JS 全部内联）"""
    return HTMLResponse(content=FULL, headers={  # 返回 HTML 响应，内容为预构建的完整页面
        "Cache-Control": "no-cache, no-store, must-revalidate",  # 禁止浏览器缓存（始终请求最新版本）
        "Pragma": "no-cache", "Expires": "0"  # 额外的禁用缓存头（兼容旧浏览器）
    })

@app.get("/map")  # 注册 /map 路径的 GET 请求处理
def map_nav():  # 地图导航页视图函数
    """就医导航地图页面（高德地图 JS API 交互式地图）
    Key 和 securityJsCode 从环境变量/配置动态注入，不硬编码。"""
    map_html = _r("map_nav.html")  # 从内存缓存读取地图导航页 HTML
    if not map_html:  # 如果地图 HTML 文件不存在或为空
        return HTMLResponse(content="<h1>地图页面加载失败</h1>", status_code=500)  # 返回 500 错误页面

    # 注入高德 JS API Key 和 securityJsCode（使用 {{PLACEHOLDER}} 占位符替换为实际值）
    map_html = map_html.replace("__AMAP_JS_KEY__", AMAP_JS_API_KEY)  # 将占位符替换为高德 JS API 密钥
    map_html = map_html.replace("__AMAP_SECURITY_CODE__", AMAP_SECURITY_CODE)  # 将占位符替换为高德安全密钥

    # 如果 Key 为空，在日志中记录警告
    if not AMAP_JS_API_KEY:  # 检查高德 JS API 密钥是否已配置
        _log.warning("AMAP_JS_API_KEY 未配置，地图无法加载！请在 .env 中设置 AMAP_JS_API_KEY")  # 输出配置缺失警告

    return HTMLResponse(content=map_html)  # 返回注入密钥后的地图 HTML 页面

@app.get("/api/images/{filename}")  # 注册图片文件访问路由（路径参数 filename 为文件名）
async def get_image(filename: str):  # 异步图片获取视图函数
    """安全地返回用户上传的图片（防路径穿越）"""
    # 文件名只能是安全字符，且不能含 ..（防止目录遍历攻击）
    if not _SAFE.match(filename) or ".." in filename:  # 检查文件名是否匹配安全正则且不包含父目录符号
        return JSONResponse(status_code=400, content={"error":"非法文件名"})  # 返回 400 错误
    fp = (UPLOAD_DIR / filename).resolve()  # 拼接完整文件路径并解析为绝对路径（消除符号链接）
    # 确保解析后的绝对路径还在 UPLOAD_DIR 内（防符号链接穿越攻击）
    if not str(fp).startswith(str(UPLOAD_DIR.resolve())):  # 检查文件路径是否在允许的上传目录内
        return JSONResponse(status_code=403, content={"error":"禁止访问"})  # 返回 403 禁止访问
    if not fp.is_file():  # 检查目标路径是否是一个实际存在的文件
        return JSONResponse(status_code=404, content={"error":"文件不存在"})  # 返回 404 文件未找到
    return FileResponse(fp)  # FastAPI 自动根据文件扩展名设置正确的 Content-Type 响应头

@app.get("/api/health")  # 注册健康检查端点
def health():  # 健康检查视图函数
    """健康检查端点：返回服务状态 + 知识库文档数"""
    try:  # 尝试获取向量数据库的文档数量
        from rag.vector_store import get_vector_store  # 延迟导入向量存储模块（避免循环依赖）
        docs = get_vector_store().count()  # 查询 ChromaDB 中已索引的文档数量
    except:  # 如果 ChromaDB 连接失败或其他异常
        docs = -1  # ChromaDB 故障时返回 -1 作为占位（不影响其他功能正常运行）
    return {"status":"healthy", "knowledge_base_docs":docs,  # 返回健康状态和文档数
            "service":"医疗智能体-影像分析系统", "version":"1.0.0"}  # 返回服务名称和版本号

# 8. 全局异常处理（捕获所有未被局部 try/except 处理的异常）
@app.exception_handler(Exception)  # 注册全局异常处理器，捕获所有 Exception 及其子类
async def on_error(request: Request, exc: Exception):  # 异常处理函数，接收请求对象和异常对象
    """捕获所有未处理的异常，记录日志并返回统一 JSON 错误格式"""
    eid = str(int(time.time()*1000))[-8:]  # 生成 8 位错误追踪 ID（取当前毫秒时间戳的后 8 位）
    _log.exception("[%s] %s %s", eid, request.method, request.url.path)  # 记录完整的异常堆栈信息
    return JSONResponse(status_code=500, content={  # 返回 HTTP 500 内部服务器错误
        "error":"服务器错误", "error_id":eid})  # 响应体包含错误描述和追踪 ID

# 9. 启动入口（当直接运行 python main.py 时执行）
if __name__ == "__main__":  # 判断当前脚本是否作为主程序运行（而非被导入）
    import uvicorn, socket, asyncio, threading  # 导入 ASGI 服务器、网络、异步和线程模块

    port = API_PORT  # 以配置的默认端口为起始端口
    for offset in range(10):  # 尝试 10 个连续端口（从默认端口开始递增）
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # 创建 TCP 套接字用于端口检测
        try:
            s.bind(("127.0.0.1", port+offset)); s.close(); port += offset; break  # 绑定成功则使用该端口并退出循环
        except OSError:  # 端口被占用导致绑定失败
            s.close()  # 关闭套接字释放资源
    else:  # for 循环正常结束（未 break），说明 10 个端口都不可用
        _log.error("无法绑定端口 %d-%d", API_PORT, API_PORT+9); exit(1)  # 输出错误日志并以退出码 1 结束程序

    # 后台定期清理速率限制存储（每 300 秒运行一次，防止过期 IP 累积导致内存泄漏）
    def _start_rate_cleanup():  # 速率限制清理线程的启动函数
        async def _loop():  # 异步清理循环协程
            while True:  # 无限循环执行清理
                await asyncio.sleep(300)  # 休眠 300 秒（5 分钟执行一次清理）
                if (n := _cleanup_rate_limit_store()): _log.debug("清理 %d IP", n)  # 执行清理，有结果则记录日志
        loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop)  # 为新线程创建独立的事件循环
        loop.run_until_complete(_loop())  # 在新线程的事件循环中运行清理协程
    cleanup_thread = threading.Thread(target=_start_rate_cleanup, daemon=True)  # 创建守护线程（主线程退出时自动结束）
    cleanup_thread.start()  # 启动清理线程

    _log.info("="*50)  # 输出分隔线日志
    _log.info("医疗智能体-影像分析系统 V1.0 | 速率限制: %d请求/%ds | http://127.0.0.1:%d", _RATE_LIMIT_MAX_REQUESTS, _RATE_LIMIT_WINDOW, port)  # 输出系统启动 Banner（含速率限制参数和服务地址）
    _log.info("="*50)  # 输出分隔线日志
    uvicorn.run("main:app", host=API_HOST, port=port, reload=False, log_level="info")  # 使用 uvicorn 启动 ASGI 服务器（不开启热重载，生产模式）
