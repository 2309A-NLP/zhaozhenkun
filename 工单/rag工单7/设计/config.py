"""
config.py - RAG工单7 配置模块
工单编号: 人工智能NLP-RAG-功能测试及评估
功能: 管理路径、API密钥、模型参数、CCF竞赛PDF路径等
      路径自动适配Windows/WSL双环境
"""

import os, sys
from pathlib import Path

# 项目根目录
PROJECT_DIR = Path(__file__).parent.resolve()

# 桌面路径（自动适配Windows/WSL）
DESKTOP_DIR = Path("/mnt/c/Users/31326/Desktop") if sys.platform != "win32" \
    else Path(os.environ["USERPROFILE"]) / "Desktop"

# ===== CCF竞赛PDF路径（年报PDF） =====
CCF_PDF_DIR = DESKTOP_DIR / "工单" / "RAG 工单" / "附件" / "ccf_competition" / "pdf"
CCF_PDF_DIR_SIMPLE = DESKTOP_DIR / "ccf_competition" / "pdf"

# ===== 测试问题PDF =====
SAMPLE_QUESTIONS_PDF = DESKTOP_DIR / "工单" / "RAG 工单" / "附件" / "sample_questions.pdf"
SAMPLE_QUESTIONS_FALLBACK = PROJECT_DIR / "sample_questions.pdf"

# ===== 输出目录 =====
OUTPUT_DIR = PROJECT_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ===== 小米MiMo API (默认) =====
MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "tp-czex5np7bgf6duyuyvqntmw44xcunseatmblffiw9lk9w0jy")
MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
MIMO_MODEL = "mimo-v2.5-pro"
EVAL_MODEL = "mimo-v2-omni"  # 非推理模型，用于LLM评估（需要结构化输出）

# ===== DeepSeek API (备选) =====
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# ===== 默认LLM提供商 =====
LLM_PROVIDER = "mimo"  # "mimo" 或 "deepseek"

# ===== BGE-M3 向量模型 =====
BGE_M3_PATH = str(DESKTOP_DIR / "bge-m3")
BGE_M3_BATCH = 2
BGE_M3_MAX_LEN = 1024
BGE_M3_DEVICE = "cuda"
BGE_M3_FP16 = True

# ===== BGE-Reranker =====
RERANKER_PATH = str(DESKTOP_DIR / "bge-reranker-base")
RERANKER_DEVICE = "cuda"

# ===== Milvus =====
MILVUS_HOST = "localhost"
MILVUS_PORT = "19530"
MILVUS_COLL = "rag_work_order_7"
MILVUS_DIM = 1024

# ===== 检索参数 =====
TOP_K = 10
RERANK_TOP_K = 8

# ===== 分块参数 =====
CHUNK_SIZE = 500
CHUNK_OVERLAP = 80

# ===== 评估配置 =====
EVAL_METRICS = ["accuracy", "recall", "f1", "response_time"]

# ===== 日志 =====
LOG_FMT = "%(asctime)s | %(levelname)-7s | %(message)s"
LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"
WO_ID = "人工智能NLP-RAG-功能测试及评估"
