"""
config.py - RAG工单13 配置管理模块
需求: 集中管理API密钥/模型路径/PDF路径/测试问题等全部配置项 — 工单第1节"基本信息"要求
功能: 1.BGE-M3路径+编码参数 2.MiMo API认证 3.PDF数据源 4.RAG分块策略 5.检索参数 6.测试问题 7.输出目录
"""
import os                     # 文件路径和目录操作（需求：跨平台路径兼容）
import sys as _sys            # 检测运行平台（WSL vs Windows）

# ======================== 基础路径 ========================
# 需求：项目根目录，所有相对路径基于此
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ======================== BGE-M3 嵌入模型 ========================
# 需求：使用BGE-M3模型进行文本向量化（工单"嵌入模型"部分）
BGE_MODEL_PATH = r"C:\Users\31326\Desktop\bge-m3"
if hasattr(_sys, 'platform') and 'linux' in _sys.platform.lower():
    BGE_MODEL_PATH = "/mnt/c/Users/31326/Desktop/bge-m3"

# 编码参数：适配RTX5060(8GB)的安全配置（需求：避免OOM，batch=2, seq=1024）
ENCODE_KWARGS = {
    "batch_size": 2,        # 推理批大小
    "max_length": 1024,     # 最大序列长度
    "show_progress_bar": False  # 禁用进度条（不干扰计时）
}

# ======================== 小米MiMo API ========================
# 需求：调用远程LLM进行答案生成（工单"LLM生成"阶段）
API_KEY = "tp-cx2rczcnaoae6bytkvs50kormwv69c101zar0nn4pu702wde"
BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
LLM_MODEL = "mimo-v2.5-pro"         # 推理模型（全小写，content可能为空）
LLM_TEMPERATURE = 0.3               # 生成温度（低温度=更确定性）
LLM_MAX_TOKENS=1024              # 最大生成长度
LLM_TIMEOUT = 60                    # API请求超时（秒）

# ======================== 数据源 ========================
# 需求：PDF作为RAG知识库（工单"数据准备"——使用已有教师语文课本）
PDF_PATH = r"C:\Users\31326\Desktop\adsd\教师(语文).pdf"
if hasattr(_sys, 'platform') and 'linux' in _sys.platform.lower():
    PDF_PATH = "/mnt/c/Users/31326/Desktop/adsd/教师(语文).pdf"

# ======================== RAG分块策略 ========================
# 需求：将PDF文本分割成块供检索（工单"检索阶段"——分块策略影响检索精度）
CHUNK_SIZE = 200            # 每块字符数（小块=检索快但上下文少）
CHUNK_OVERLAP = 30          # 块间重叠（避免切断完整语义）

# ======================== 检索配置 ========================
# 需求：向量检索时返回Top-K个最相关块（工单"检索阶段"参数）
VECTOR_TOP_K = 5

# ======================== 测试问题 ========================
# 需求：基准测试用的10个语文问题（工单"验收标准"——测试数据）
TEST_QUESTIONS = [
    "屈原的《离骚》表达了怎样的思想感情？",
    "课文中提到的先秦诸子散文有哪些主要流派？",
    "《论语》中孔子关于'君子'的论述有哪些？",
    "苏轼的《赤壁赋》创作背景是什么？",
    "《红楼梦》中林黛玉的性格特点是什么？",
    "鲁迅的《祝福》反映了什么社会问题？",
    "杜甫的诗歌风格被称为什么？",
    "这篇课文中提到的唐宋八大家是哪几个人？",
    "《诗经》的主要内容分为哪几类？",
    "老舍的《茶馆》反映了哪个时代的社会变迁？"
]
BENCHMARK_RUNS = 2  # 基准测试运行轮数

# ======================== 输出路径 ========================
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)
CACHE_DIR = os.path.join(BASE_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)
BENCHMARK_OUTPUT = os.path.join(OUTPUT_DIR, "benchmark_results.json")
REPORT_OUTPUT = os.path.join(OUTPUT_DIR, "optimization_report.md")


_LOG_OK = False


_TEE_DONE = False

def setup_logging():
    """初始化统一日志：控制台 + output/logs/rag工单13_系统日志.log"""
    global _LOG_OK, _TEE_DONE
    if _LOG_OK:
        return
    _LOG_OK = True
    import logging
    log_dir = os.path.join(OUTPUT_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "rag工单13_系统日志.log")
    root = logging.getLogger(); root.setLevel(logging.INFO)
    if not any(isinstance(h, logging.FileHandler) for h in root.handlers):
        fh = logging.FileHandler(log_file, encoding="utf-8"); fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)-5s] [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
        root.addHandler(fh)
    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in root.handlers):
        ch = logging.StreamHandler(); ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)-5s] [%(name)s] %(message)s", "%H:%M:%S"))
        root.addHandler(ch)
    for lib in ["pymilvus","sentence_transformers","urllib3","openai","httpx"]:
        logging.getLogger(lib).setLevel(logging.WARNING)
    
        # --- print 输出自动同步到日志文件 ---
        if not _TEE_DONE:
            _TEE_DONE = True
            _orig_stdout = _sys.stdout
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

            _sys.stdout = _Tee(_orig_stdout, _log_fd)

        print(f"[日志] 系统日志: {log_file}")


setup_logging()
