"""
配置管理模块（设计层）
功能：集中管理所有全局配置项——模型路径、API密钥、PDF路径、输出目录、参数常量
完成：为全部 12 个模块提供统一的配置入口，支持 Windows 和 WSL 双平台路径自动切换
"""
import sys, os
# 将项目根目录加入路径，支持从任意子目录导入其他模块
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _sub in ["设计", "研发", "测试", "部署", "优化"]:
    _p = os.path.join(_root, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ======================== 基础路径配置 ========================

# 项目根目录（本文件位于 设计/ 子目录，dirname 两次回到项目根）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ======================== BGE-M3 嵌入模型路径配置 ========================

# BGE-M3 本地模型路径（Windows 默认路径）
BGE_MODEL_PATH = r"C:\Users\31326\Desktop\bge-m3"
# WSL/Linux 环境下自动转换为 Linux 路径格式
import sys as _sys
if hasattr(_sys, 'platform') and 'linux' in _sys.platform.lower():
    BGE_MODEL_PATH = "/mnt/c/Users/31326/Desktop/bge-m3"

# BGE-M3 编码参数：适配 RTX 5060 8GB 显存的安全配置
ENCODE_KWARGS = {
    "batch_size": 2,           # 批大小：8GB 显存 OOM 边界约 batch=4，安全取 2
    "max_length": 1024,        # 最大序列长度：BGE-M3 支持 8192，限制 1024 控制显存
    "show_progress_bar": True  # 显示编码进度条
}

# ======================== 小米 MiMo Token Plan API 配置 ========================

API_KEY = "tp-cx2rczcnaoae6bytkvs50kormwv69c101zar0nn4pu702wde"  # Token Plan API 密钥
BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"               # API 基础端点
LLM_MODEL = "mimo-v2.5-pro"          # 使用的模型名称（全小写，MiMo API 要求）
LLM_TEMPERATURE = 0.1                # 低温度保证实体提取和问答的确定性
LLM_MAX_TOKENS = 8192                # 最大生成长度（批量实体提取需要更多输出）
LLM_TIMEOUT = 120                    # 单次请求超时秒数（批量提取需更长时间）

# ======================== PDF 数据源配置 ========================

# 两份招股说明书 PDF 的完整路径映射
PDF_PATHS = {
    "招股说明书1.pdf": os.path.join(BASE_DIR, "招股说明书1.pdf"),
    "招股说明书2.pdf": os.path.join(BASE_DIR, "招股说明书2.pdf")
}

# ======================== 文本分块配置 ========================

CHUNK_SIZE = 300      # 每块最大字符数（招股书页均300-500字符，取300平衡粒度）
CHUNK_OVERLAP = 50    # 块间重叠字符数（防止关键信息在边界被切断）

# ======================== 知识图谱配置 ========================

ENTITY_BATCH_SIZE = 5       # 每次 LLM 调用处理的 chunk 数量（太少→API调用多，太多→输出超限）
GRAPH_EXPAND_HOPS = 2       # 图谱检索时 BFS 邻居扩展的跳数

# ======================== 检索配置 ========================

VECTOR_TOP_K = 10            # RAG 模式：向量检索返回前 k 个最相似块
LIGHTRAG_LOCAL_K = 5         # LightRAG 模式：局部（向量）检索返回数量
LIGHTRAG_GLOBAL_K = 5        # LightRAG 模式：全局（图谱扩展）检索返回数量

# ======================== 输出路径配置 ========================

OUTPUT_DIR = os.path.join(BASE_DIR, "output")     # 输出根目录
os.makedirs(OUTPUT_DIR, exist_ok=True)            # 确保目录存在
EVAL_OUTPUT = os.path.join(OUTPUT_DIR, "eval_report.json")    # 评估报告输出路径
GRAPH_VIZ_PATH = os.path.join(OUTPUT_DIR, "knowledge_graph.html")  # 图谱可视化路径

# ======================== 缓存路径配置 ========================

CACHE_DIR = os.path.join(BASE_DIR, "cache")       # 缓存根目录（存放中间结果，避免重复计算）
os.makedirs(CACHE_DIR, exist_ok=True)
CHUNKS_CACHE = os.path.join(CACHE_DIR, "chunks.json")                # 文本块缓存
VECTORS_CACHE = os.path.join(CACHE_DIR, "vectors.npy")               # BGE-M3 向量缓存
EMBEDDINGS_META = os.path.join(CACHE_DIR, "embeddings_meta.json")    # 向量元数据缓存
GRAPH_CACHE = os.path.join(CACHE_DIR, "graph.json")                  # 知识图谱 JSON 缓存
PARSED_PAGES = os.path.join(CACHE_DIR, "parsed_pages.json")          # PDF 解析结果缓存
ENTITY_EXTRACTIONS = os.path.join(CACHE_DIR, "entity_extractions.json")  # 实体提取结果缓存

# ======================== 测试问题配置 ========================

# 工单规定的 16 个测试问题（招股说明书1: 6题 + 招股说明书2: 10题）
TEST_QUESTIONS = [
    # ── 招股说明书1：武汉力源信息技术股份有限公司 ──
    {"id": 1, "question": "武汉力源信息技术股份有限公司本次发行股数是多少，占发行后总股本的比例是多少？"},
    {"id": 2, "question": "武汉力源信息技术股份有限公司本次募集资金拟投资哪些项目？"},
    {"id": 3, "question": "与武汉力源信息技术股份有限公司存在控制关系的关联方是谁，持股比例和本公司关系是什么？"},
    {"id": 4, "question": "与武汉力源信息技术股份有限公司不存在控制关系的关联方企业有哪些？"},
    {"id": 5, "question": "武汉力源信息技术股份有限公司组织结构图中，销售部有几个部门构成，其中大客户销售部有几个销售处构成？"},
    {"id": 6, "question": "武汉力源信息技术股份有限公司招股意向书中，从2008年中国IC市场应用结构与增长图中可以看出，增长率最快的是哪个行业？负增长的是哪个行业？"},
    # ── 招股说明书2：武汉兴图新科电子股份有限公司 ──
    {"id": 260, "question": "报告期内，武汉兴图新科电子股份有限公司来自军用领域的收入分别是多少？"},
    {"id": 95, "question": "武汉兴图新科电子股份有限公司参与制定了哪个技术标准？"},
    {"id": 33, "question": "报告期内，武汉兴图新科电子股份有限公司来自军用领域的收入占主营业务收入的比重分别是多少？"},
    {"id": 34, "question": "根据武汉兴图新科电子股份有限公司招股意向书，电子信息行业的上游涉及哪些企业？"},
    {"id": 957, "question": "武汉兴图新科电子股份有限公司在哪个领域已经成为重要供应商？"},
    {"id": 793, "question": "根据武汉兴图新科电子股份有限公司招股意向书，电子信息行业的下游主要包括哪些行业？"},
    {"id": 795, "question": "武汉兴图新科电子股份有限公司参与的哪个工程荣获了国家科技进步一等奖？"},
    {"id": 543, "question": "武汉兴图新科电子股份有限公司注册资本是多少？"},
    {"id": 531, "question": "武汉兴图新科电子股份有限公司法定代表人是谁？"},
    {"id": 207, "question": "武汉兴图新科电子股份有限公司计划使用本次发行募集资金的多少用于补充流动资金？"}
]

# 测试模式：只跑前2题快速验证（--test 参数触发）
TEST_MODE_QUESTIONS = 2


_LOG_OK = False
_TEE_DONE = False


def setup_logging():
    """初始化统一日志：控制台 + output/logs/rag工单12_系统日志.log"""
    global _LOG_OK, _TEE_DONE
    if _LOG_OK:
        return
    _LOG_OK = True
    import logging
    log_dir = os.path.join(OUTPUT_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "rag工单12_系统日志.log")
    root = logging.getLogger(); root.setLevel(logging.INFO)
    if not any(isinstance(h, logging.FileHandler) for h in root.handlers):
        fh = logging.FileHandler(log_file, encoding="utf-8"); fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)-5s] [%(name)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
        root.addHandler(fh)
    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in root.handlers):
        ch = logging.StreamHandler(); ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)-5s] [%(name)s] %(message)s", "%H:%M:%S"))
        root.addHandler(ch)
    for lib in ["pymilvus","sentence_transformers","urllib3","openai","httpx","transformers"]:
        logging.getLogger(lib).setLevel(logging.WARNING)
    
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
