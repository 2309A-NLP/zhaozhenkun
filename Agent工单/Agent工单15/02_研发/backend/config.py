"""
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.1
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-实时语音识别 V1.0
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-挂号管理 V1.1
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-健康咨询 V1.1
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-MCP V1.0
================================================================
系统配置模块 —— 所有可配置参数集中管理
支持 .env 文件加载 + 环境变量覆盖 + 硬编码默认值（最低优先级）
================================================================
"""
import os, logging  # 导入操作系统环境变量模块和日志记录模块
from pathlib import Path  # 导入 Path 用于跨平台路径处理

_log = logging.getLogger("medical_agent.config")  # 获取配置模块专用的日志记录器

# ============================================================
# 1. 加载 .env 文件（优先级最高，覆盖硬编码默认值）
# ============================================================
try:
    from dotenv import load_dotenv  # 尝试导入 python-dotenv 库的加载函数
    _p = Path(__file__).resolve().parent / ".env"  # 构建 .env 文件的绝对路径（与本配置文件同目录）
    if _p.exists():  # 检查 .env 文件是否实际存在
        load_dotenv(_p); _log.info("✅ 已加载: %s", _p)  # 加载 .env 文件到 os.environ，并记录成功日志
except ImportError:  # python-dotenv 库未安装
    pass  # 跳过 .env 加载，继续使用系统环境变量和默认值

# ============================================================
# 2. 项目路径（统一使用 Path 对象，跨平台兼容 Windows/Linux/Mac）
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # 项目根目录 Agent工单15/（向上三级）
DATA_DIR = BASE_DIR / "data"           # 数据根目录（所有持久化数据的存放位置）
KNOWLEDGE_DIR = DATA_DIR / "knowledge" # RAG 知识文档目录（存放 PDF/TXT/DOCX 等知识文档）
UPLOAD_DIR = DATA_DIR / "uploads"      # 用户上传的图片/文档临时存储目录
CHROMA_DIR = DATA_DIR / "chroma_db"    # ChromaDB 向量数据库的持久化存储目录

# 确保关键目录存在（启动时自动创建缺失的目录树）
for d in [DATA_DIR, KNOWLEDGE_DIR, UPLOAD_DIR, CHROMA_DIR]:  # 遍历所有需要的目录路径
    d.mkdir(parents=True, exist_ok=True)  # 递归创建目录，父目录不存在则一并创建，已存在则跳过

# ============================================================
# 3. 服务配置
# ============================================================
API_HOST = os.getenv("API_HOST", "0.0.0.0")              # 监听地址：0.0.0.0 表示监听所有网络接口
API_PORT = int(os.getenv("API_PORT", "8080"))             # 默认监听端口：8080（从环境变量读取并转为整数）
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",") # 跨域白名单：默认 "*" 允许所有来源（用逗号分隔多域名）

# ============================================================
# 4. 千问 API（多模态视觉模型，VQA + MRG）
#    base_url 是 OpenAI 兼容接口地址
# ============================================================
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")  # 千问 API 密钥（阿里云百炼/DashScope 获取）
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")  # 千问 OpenAI 兼容 API 地址
QWEN_VISION_MODEL = os.getenv("QWEN_VISION_MODEL", "qwen-vl-plus")  # 视觉模型名称：看图+文本的多模态推理
QWEN_TEXT_MODEL = os.getenv("QWEN_TEXT_MODEL", "qwen-plus")          # 文本模型名称：纯文本推理（更快更便宜）
QWEN_API_TIMEOUT = int(os.getenv("QWEN_API_TIMEOUT", "120"))         # API 调用超时时间秒数（超过此时间放弃等待）

# ============================================================
# 5. DeepSeek API（文本推理引擎，RAG + 挂号意图解析）
#    base_url 必须含 /v1，OpenAI SDK 要求
# ============================================================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")  # DeepSeek API 密钥（DeepSeek 开放平台获取）
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")  # DeepSeek API 地址（OpenAI 兼容格式）
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")  # 使用的 DeepSeek 模型名称
DEEPSEEK_API_TIMEOUT = int(os.getenv("DEEPSEEK_API_TIMEOUT", "120"))  # API 调用超时时间秒数

# ============================================================
# 6. Kimi API（Moonshot —— 需求分析 / 报告生成）
#    工单要求：使用 Kimi 进行需求分析，产出分析报告
# ============================================================
KIMI_API_KEY = os.getenv("KIMI_API_KEY", "")  # Kimi API 密钥（Moonshot 开放平台获取）
KIMI_BASE_URL = os.getenv("KIMI_BASE_URL", "https://api.moonshot.cn/v1")  # Kimi API 地址
KIMI_MODEL = os.getenv("KIMI_MODEL", "moonshot-v1-8k")  # Kimi 模型名称：8k 上下文窗口
KIMI_API_TIMEOUT = int(os.getenv("KIMI_API_TIMEOUT", "120"))  # API 调用超时时间秒数

# ============================================================
# 7. ChromaDB 向量数据库
# ============================================================
CHROMA_COLLECTION_NAME = "medical_knowledge"  # ChromaDB 集合名称：存放医疗知识文档的向量嵌入
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")  # 文本嵌入模型：多语言 MiniLM
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))                              # 知识检索返回的最相关文档数量
RAG_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.3"))  # 相似度阈值：低于此值的文档不返回

# ============================================================
# 7. 文件上传（编号重复但保持原样，实际为第 8 部分但原文如此）
# ============================================================
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))  # 单个文件最大上传大小（MB）

# 图片支持的 MIME 类型（浏览器上传时声明的 Content-Type）
ALLOWED_IMAGE_TYPES = {"image/jpeg","image/png","image/gif","image/webp",  # 常见图片 MIME 类型集合
    "image/tiff","image/x-tiff","application/dicom","application/octet-stream"}  # TIFF/DICOM 医学影像格式 + 通用二进制流
ALLOWED_IMAGE_EXTENSIONS = {".jpg",".jpeg",".png",".gif",".webp",".tiff",".tif",".dcm",".dicom"}  # 图片文件扩展名白名单（回退校验）

# 文档支持的 MIME 类型和扩展名
ALLOWED_DOC_TYPES = {"application/pdf","text/plain",  # PDF 和纯文本文件
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # DOCX 格式
    "application/msword","application/octet-stream"}  # 旧版 DOC 格式 + 通用二进制流
ALLOWED_DOC_EXTENSIONS = {".pdf",".txt",".docx",".doc",".md"}  # 文档文件扩展名白名单（含 Markdown）

# ============================================================
# 8. 通义听悟 / DashScope 实时语音识别
#    工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-实时语音识别 V1.0
#    DASHSCOPE_API_KEY:  DashScope WebSocket API Key（sk-ws-xxx 格式）
#    DASHSCOPE_WS_HOST:  MAAS 专有实例地址（WebSocket 实时转写）
#    DASHSCOPE_HTTP_URL: HTTP 文件转写 API 地址
#    TINGWU_APP_KEY:     应用 ID（通义听悟控制台 / MAAS 实例 ID）
# ============================================================
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")  # 通义听悟 WebSocket API 密钥（sk-ws-xxx 格式）
DASHSCOPE_WS_HOST = os.getenv("DASHSCOPE_WS_HOST", "dashscope.aliyuncs.com")  # WebSocket 服务的域名地址
DASHSCOPE_HTTP_URL = f"https://{DASHSCOPE_WS_HOST}/api/v1"  # 拼接 HTTP API 的完整地址
# WebSocket 实时转写端点
DASHSCOPE_WS_URL = f"wss://{DASHSCOPE_WS_HOST}/api-ws/v1/inference"  # 拼接 WebSocket 实时推理的连接地址
TINGWU_APP_KEY = os.getenv("TINGWU_APP_KEY", "")  # 通义听悟应用 ID（MAAS 实例中获取）
ASR_SAMPLE_RATE = int(os.getenv("ASR_SAMPLE_RATE", "16000"))  # 语音识别采样率：16000Hz 标准采样
ASR_LANGUAGE = os.getenv("ASR_LANGUAGE", "zh")  # 语音识别目标语言：中文

# ============================================================
# 9. 高德地图 API（MCP 对接 - 出行/住宿/餐饮查询）
#    工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-MCP V1.0
#    AMAP_API_KEY:         Web服务 Key（REST API 后端调用）
#    AMAP_JS_API_KEY:      Web端(JS API) Key（前端地图加载，默认复用 AMAP_API_KEY）
#    AMAP_SECURITY_CODE:   JS API 2.0 安全密钥（必填！在控制台「安全密钥」中获取）
# ============================================================
AMAP_API_KEY = os.getenv("AMAP_API_KEY", "")  # 高德 Web 服务 API 密钥（后端 REST API 调用使用）
AMAP_JS_API_KEY = os.getenv("AMAP_JS_API_KEY", AMAP_API_KEY)  # 高德 JS API 密钥：默认复用 Web 服务密钥
AMAP_SECURITY_CODE = os.getenv("AMAP_SECURITY_CODE", "")  # 高德 JS API 2.0 安全密钥（前端加载时必填）
AMAP_BASE_URL = "https://restapi.amap.com/v3"  # 高德 REST API 的基础地址
AMAP_API_TIMEOUT = int(os.getenv("AMAP_API_TIMEOUT", "10"))  # 高德 API 调用超时时间（秒，较短因为地图 API 需快速响应）

# ============================================================
# 10. 性能监控阈值（毫秒）
# ============================================================
RESPONSE_TIMEOUT_MS = int(os.getenv("RESPONSE_TIMEOUT_MS", "500"))  # 响应超时警告阈值（超过此值记录慢日志）


def _check():  # 启动时 API Key 配置检查函数
    """启动时检查 API Key 是否已配置"""
    ok = True  # 初始化检查标记为 True（假设全部配置正确）
    if not QWEN_API_KEY: _log.warning("缺少 QWEN_API_KEY"); ok = False  # 如果千问 Key 为空则输出警告并标记失败
    if not DEEPSEEK_API_KEY: _log.warning("缺少 DEEPSEEK_API_KEY"); ok = False  # 如果 DeepSeek Key 为空则输出警告
    if not KIMI_API_KEY: _log.warning("缺少 KIMI_API_KEY"); ok = False  # 如果 Kimi Key 为空则输出警告
    if ok: _log.info("API 密钥配置完成 (千问+DeepSeek+Kimi)")  # 如果全部配置则输出成功日志
    return ok  # 返回检查结果（True=全部配置，False=有缺失）

_check()  # 模块加载时自动执行 API Key 配置检查
