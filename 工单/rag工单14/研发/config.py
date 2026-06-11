"""
配置文件模块
功能：集中管理所有全局配置——API密钥、模型路径、文件路径、分块参数、检索参数
说明：本模块被其他所有模块 import 引用，修改配置只需改这一个文件
"""
import os              # 路径拼接和目录创建
import platform        # 检测操作系统(Win/Linux)，兼容双平台路径
import sys             # stdout 重定向到日志


# ======================== 项目根路径 ========================
# __file__ 的上级目录作为项目根目录，兼容 Windows 和 WSL
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 上两级才是项目根


# ======================== 小米 MiMo API 配置 ========================

# API 密钥
MIMO_API_KEY = "tp-cx2rczcnaoae6bytkvs50kormwv69c101zar0nn4pu702wde"

# API 基础地址
MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"

# 使用的模型名称（全小写）
MIMO_MODEL = "mimo-v2.5-pro"

# API 请求超时（秒，MiMo 响应较慢）
MIMO_TIMEOUT = 300

# LLM 生成参数
MIMO_TEMPERATURE = 0.3   # 偏低温度，让回答更精确
MIMO_MAX_TOKENS = 500   # 每次回答的最大 token 数


# ======================== BGE-M3 模型路径 ========================

# 检测操作系统，自动适配路径
if platform.system() == "Windows":
    # Windows 原生 Python 下的路径
    BGE_MODEL_PATH = r"C:\Users\31326\Desktop\bge-m3"
    RERANKER_PATH = r"C:\Users\31326\Desktop\bge-reranker-base"
else:
    # WSL/Linux 下的路径（映射到 Windows 桌面）
    BGE_MODEL_PATH = "/mnt/c/Users/31326/Desktop/bge-m3"
    RERANKER_PATH = "/mnt/c/Users/31326/Desktop/bge-reranker-base"


# ======================== 嵌入模型安全参数 ========================

# batch_size: 每次编码的文本数，RTX5060(8GB)安全配置为2
EMBED_BATCH_SIZE = 2

# max_seq_length: 最大序列长度，安全配置为1024（BGE-M3支持到8192但卡会爆）
EMBED_MAX_LENGTH = 1024

# 使用 FP16 半精度显存减半
EMBED_USE_FP16 = True

# 编码维度（BGE-M3的默认维度）
EMBED_DIM = 1024


# ======================== PDF 文件路径 ========================

# 测试用的静电除尘器专利 PDF（真实数据路径，数据在测试/目录）
TEST_PDF_PATH = os.path.join(
    PROJECT_ROOT, "测试", "original_problems", "original_problems",
    "documents", "CN100342976C.pdf"
)

# 补充用的文本型PDF（含完整图示描述，弥补扫描件OCR信息丢失）
SUPPLEMENT_PDF_PATH = os.path.join(PROJECT_ROOT, "测试", "CN100342976C_text.pdf")


# ======================== 文本分块参数 ========================

# 每个块的最大字符数
CHUNK_SIZE = 256

# 相邻块之间的重叠字符数
CHUNK_OVERLAP = 32


# ======================== 检索参数 ========================

# 向量检索返回的候选块数量（增大以确保补充PDF块也能进入候选池）
TOP_K_RETRIEVAL = 10

# 重排序后保留的最终块数量
TOP_K_RERANK = 3


# ======================== 向量存储目录 ========================

# 保存向量索引和分块文本的目录（纯英文路径，避免 Windows 下 Unicode 兼容问题）
VECTOR_STORE_DIR = os.path.join(
    os.path.expanduser("~"), ".rag_workorder14_cache"
)
os.makedirs(VECTOR_STORE_DIR, exist_ok=True)  # 确保目录存在


# ======================== 测试问题列表（供参考） ========================

# 6个测试问题对应的专利文档名
TEST_DOCUMENT = "CN100342976C.pdf"

# 向量检索+重排序后最终送入LLM的块数（给LLM充足上下文推理）
FINAL_CONTEXT_COUNT = 3

# 检索模式：hybrid=混合检索, dense=仅向量检索
RETRIEVAL_MODE = "dense"


# ======================== 调试与日志配置 ========================

# 是否打印详细的调试日志
VERBOSE = True

# 是否缓存模型的编码结果（True=快，False=每次都重新编码）
USE_CACHE = True


_LOGGING_INITIALIZED = False


_TEE_DONE = False

def setup_logging():
    """初始化统一日志：控制台 + .rag_workorder14_cache/系统日志.log"""
    global _LOGGING_INITIALIZED, _TEE_DONE
    if _LOGGING_INITIALIZED:
        return
    _LOGGING_INITIALIZED = True
    import logging
    log_dir = os.path.join(PROJECT_ROOT, "output", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "rag工单14_系统日志.log")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # 始终创建 FileHandler（即使已有其他 handler）
    already_has_file = any(
        isinstance(h, logging.FileHandler) for h in root.handlers
    )
    if not already_has_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            "[%(asctime)s] [%(levelname)-5s] [%(name)s] %(message)s",
            "%Y-%m-%d %H:%M:%S"))
        root.addHandler(fh)
    # 控制台 handler
    has_console = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        for h in root.handlers
    )
    if not has_console:
        ch = logging.StreamHandler(); ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter(
            "[%(asctime)s] [%(levelname)-5s] [%(name)s] %(message)s", "%H:%M:%S"))
        root.addHandler(ch)
    for lib in ["pymilvus","sentence_transformers","urllib3","openai","httpx"]:
        logging.getLogger(lib).setLevel(logging.WARNING)
    # 确保用户知道日志文件在哪
    
        # --- print 输出自动同步到日志文件 ---
        if not _TEE_DONE:
            _TEE_DONE = True
            _orig_stdout = sys.stdout
            _log_fd = open(log_file, 'a', encoding='utf-8', buffering=1)

            class _Tee:
                def __init__(self, *files):
                    self.files = files
                def write(self, data):
                    for f in self.files:
                        f.write(data); f.flush()
                def flush(self):
                    for f in self.files:
                        f.flush()

            sys.stdout = _Tee(_orig_stdout, _log_fd)

        print(f"[日志] 系统日志: {log_file}")


setup_logging()
