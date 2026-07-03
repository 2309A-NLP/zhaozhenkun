"""
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
================================================================
系统配置模块 —— 所有可配置参数集中管理
支持 .env 文件加载 + 环境变量覆盖 + 硬编码默认值（最低优先级）
================================================================
"""
import os, logging
from pathlib import Path

_log = logging.getLogger("medical_agent.config")

# ============================================================
# 1. 加载 .env 文件（优先级最高，覆盖硬编码默认值）
# ============================================================
try:
    from dotenv import load_dotenv
    _p = Path(__file__).resolve().parent / ".env"
    if _p.exists():
        load_dotenv(_p); _log.info("✅ 已加载: %s", _p)
except ImportError:
    pass  # python-dotenv 未安装则跳过

# ============================================================
# 2. 项目路径（统一使用 Path 对象，跨平台兼容）
# ============================================================
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # Agent工单13/
DATA_DIR = BASE_DIR / "data"           # 数据根目录
KNOWLEDGE_DIR = DATA_DIR / "knowledge" # RAG 知识文档
UPLOAD_DIR = DATA_DIR / "uploads"      # 用户上传的图片/文档
CHROMA_DIR = DATA_DIR / "chroma_db"    # ChromaDB 向量库

# 确保关键目录存在
for d in [DATA_DIR, KNOWLEDGE_DIR, UPLOAD_DIR, CHROMA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ============================================================
# 3. 服务配置
# ============================================================
API_HOST = os.getenv("API_HOST", "0.0.0.0")              # 监听地址
API_PORT = int(os.getenv("API_PORT", "8080"))             # 默认端口 8080
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",") # 跨域白名单

# ============================================================
# 4. 千问 API（多模态视觉模型，VQA + MRG）
#    base_url 是 OpenAI 兼容接口地址
# ============================================================
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
QWEN_VISION_MODEL = os.getenv("QWEN_VISION_MODEL", "qwen-vl-plus")  # 看图+文本
QWEN_TEXT_MODEL = os.getenv("QWEN_TEXT_MODEL", "qwen-plus")          # 纯文本
QWEN_API_TIMEOUT = int(os.getenv("QWEN_API_TIMEOUT", "120"))         # 超时秒数

# ============================================================
# 5. DeepSeek API（文本推理引擎，RAG + 挂号意图解析）
#    base_url 必须含 /v1，OpenAI SDK 要求
# ============================================================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
DEEPSEEK_API_TIMEOUT = int(os.getenv("DEEPSEEK_API_TIMEOUT", "120"))

# ============================================================
# 6. ChromaDB 向量数据库
# ============================================================
CHROMA_COLLECTION_NAME = "medical_knowledge"  # 集合名
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))                              # 检索数量
RAG_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.3"))  # 相似度阈值

# ============================================================
# 7. 文件上传
# ============================================================
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))

# 图片支持的 MIME（浏览器传来）和扩展名（回退校验）
ALLOWED_IMAGE_TYPES = {"image/jpeg","image/png","image/gif","image/webp",
    "image/tiff","image/x-tiff","application/dicom","application/octet-stream"}
ALLOWED_IMAGE_EXTENSIONS = {".jpg",".jpeg",".png",".gif",".webp",".tiff",".tif",".dcm",".dicom"}

# 文档支持的 MIME 和扩展名
ALLOWED_DOC_TYPES = {"application/pdf","text/plain",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword","application/octet-stream"}
ALLOWED_DOC_EXTENSIONS = {".pdf",".txt",".docx",".doc",".md"}

# ============================================================
# 8. 性能监控阈值（毫秒）
# ============================================================
RESPONSE_TIMEOUT_MS = int(os.getenv("RESPONSE_TIMEOUT_MS", "500"))


def _check():
    """启动时检查 API Key 是否已配置"""
    ok = True
    if not QWEN_API_KEY: _log.warning("缺少 QWEN_API_KEY"); ok = False
    if not DEEPSEEK_API_KEY: _log.warning("缺少 DEEPSEEK_API_KEY"); ok = False
    if ok: _log.info("API 密钥配置完成")
    return ok

_check()
