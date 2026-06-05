"""
config.py - RAG工单6 配置模块
需求: 向量检索(召回+重排) / 全文检索 / 混合检索 — 统一配置
功能: 管理路径、API密钥、模型参数、检索策略配置，自动适配Windows/WSL双环境
"""
import os, sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.resolve()
DESKTOP_DIR = Path("/mnt/c/Users/31326/Desktop") if sys.platform != "win32" \
    else Path(os.environ["USERPROFILE"]) / "Desktop"

# PDF文件路径
PDF_PATHS = [PROJECT_DIR / "招股说明书2.pdf", PROJECT_DIR / "招股说明书1.pdf"]
PDF_NAMES = ["招股说明书2.pdf", "招股说明书1.pdf"]
OUTPUT_DIR = PROJECT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ===== 小米MiMo API（OpenAI兼容） =====
MIMO_API_KEY = "tp-czex5np7bgf6duyuyvqntmw44xcunseatmblffiw9lk9w0jy"
MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
MIMO_MODEL = "mimo-v2.5-pro"
MIMO_TIMEOUT = 60
MIMO_MAX_TOKENS = 2048

# ===== 备用DeepSeek API（保留） =====
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# ===== BGE-M3 向量模型（FP16安全配置） =====
BGE_M3_PATH = str(DESKTOP_DIR / "bge-m3")
BGE_M3_BATCH = 2
BGE_M3_MAX_LEN = 1024
BGE_M3_DEVICE = "cuda"
BGE_M3_FP16 = True

# ===== BGE-Reranker 重排序 =====
RERANKER_PATH = str(DESKTOP_DIR / "bge-reranker-base")
RERANKER_DEVICE = "cuda"

# ===== Milvus 向量库 =====
MILVUS_HOST = "localhost"
MILVUS_PORT = "19530"
MILVUS_COLL = "rag_work_order_6"
MILVUS_DIM = 1024

# ===== 分块 & 检索参数 =====
CHUNK_SIZE = 300
CHUNK_OVERLAP = 50
TOP_K = 10
RERANK_TOP_K = 5
FULLTEXT_TOP_K = 10

# ===== 检索策略配置 =====
RETRIEVAL_MODES = ["vector", "fulltext", "hybrid"]
RERANK_METHODS = ["llm", "tfidf", "adaptive"]
HYBRID_WEIGHT_VECTOR = 0.5
HYBRID_WEIGHT_FULLTEXT = 0.5

LOG_FMT = "%(asctime)s | %(levelname)-7s | %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"
WO_ID = "人工智能NLP-RAG-混合检索任务"
