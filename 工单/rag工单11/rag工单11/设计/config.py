"""
配置管理模块（设计层）
功能：集中管理所有全局配置——模型路径、API密钥、PDF数据源、训练/评估参数
完成：为全部 10 个模块提供统一配置入口，支持 Windows/WSL 双平台路径自动适配
工单编号：人工智能NLP-RAG项目-11-Embeddings模型微调任务V1.0
"""
import os                           # 操作系统路径操作
import re                           # 正则表达式（WSL路径转换）
import sys                          # 系统参数（stdout重定向）
from pathlib import Path            # 跨平台路径对象

# ======================== 基础路径配置 ========================

# 项目根目录（config.py位于设计/子目录，parent两次回到根）
BASE_DIR = Path(__file__).parent.parent.resolve()

# 输出目录结构
OUTPUT_DIR = BASE_DIR / "output"    # 所有产出根目录
DATA_DIR = OUTPUT_DIR / "data"      # 训练数据（三元组/问答对）
MODEL_DIR = OUTPUT_DIR / "models"   # 微调后的 LoRA 权重
EVAL_DIR = OUTPUT_DIR / "eval"      # 评估结果和对比报告

# ======================== PDF 数据源配置 ========================

# 招股说明书 PDF（Embedding微调的目标领域数据）
PDF_PATHS = [
    r"C:\Users\31326\Desktop\rag工单12\招股说明书1.pdf",   # 武汉力源信息
    r"C:\Users\31326\Desktop\rag工单12\招股说明书2.pdf",   # 武汉兴图新科
]


def normalize_path(path: str) -> str:
    """
    将 Windows 路径转换为当前系统可用的路径（自动适配 WSL/Linux）
    参数：path - Windows 格式路径（如 C:/Users/...）
    返回：当前系统可用的路径
    """
    if os.name == "nt":                      # Windows 原生环境
        return path
    # WSL 环境：C:\xxx\yyy → /mnt/c/xxx/yyy
    wsl = re.sub(r'^([A-Za-z]):[\\/]',       # 匹配盘符 C:\ 或 C:/
                 lambda m: f'/mnt/{m.group(1).lower()}/', path)
    wsl = wsl.replace("\\", "/")             # 反斜杠转正斜杠
    return wsl

# ======================== BGE-M3 模型路径配置 ========================

# BGE-M3 本地模型路径（Windows格式）
BGE_M3_PATH = r"C:\Users\31326\Desktop\bge-m3"


def get_model_path() -> str:
    """
    返回当前系统可用的 BGE-M3 模型路径（自动适配 WSL/Windows）
    返回：模型目录的绝对路径字符串
    """
    if os.name == "nt":                      # Windows 原生
        return BGE_M3_PATH
    # WSL：将 C:\ → /mnt/c/
    return BGE_M3_PATH.replace("C:\\", "/mnt/c/").replace("\\", "/")

# ======================== 小米 MiMo Token Plan API 配置 ========================

# 小米 MiMo API（用于智能问答对生成和质量评分）
MIMO_API_KEY = "tp-cx2rczcnaoae6bytkvs50kormwv69c101zar0nn4pu702wde"
MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
MIMO_MODEL = "mimo-v2.5-pro"
MIMO_TIMEOUT = 45          # API 请求超时秒数
MIMO_MAX_TOKENS = 512      # 最大生成长度（问答对生成不需要太长）

# ======================== 训练数据生成参数 ========================

CHUNK_SIZE = 512           # PDF文本切分的块大小（字符数）
CHUNK_OVERLAP = 64         # 切分重叠字符数（避免信息在边界断裂）
TRAIN_RATIO = 0.8          # 训练集比例（其余为评估集）
MAX_TRIPLETS = 500         # 最大生成三元组数量
QA_PAIRS_PER_CHUNK = 2     # 每段文本生成的问答对数量

# ======================== LoRA 微调参数 ========================

LORA_CONFIG = {
    "r": 4,                              # LoRA秩：越大可学习参数越多（8GB显存推荐4-8）
    "lora_alpha": 8,                     # LoRA缩放系数（一般为r的2倍）
    "lora_dropout": 0.05,                # Dropout比例，防止过拟合
    "target_modules": ["query", "key", "value"],  # 作用模块：注意力层的Q/K/V
    "bias": "none",                      # 不训练偏置项
}

# ======================== 训练超参数 ========================

TRAIN_CONFIG = {
    "epochs": 3,                         # 训练轮数：3轮+低学习率效果最佳
    "batch_size": 2,                     # 批次大小：8GB显存上限
    "max_seq_length": 512,               # 最大序列长度（降低显存占用）
    "learning_rate": 1e-5,               # 学习率：LoRA微调不宜太大
    "warmup_ratio": 0.1,                 # 预热比例：前10%步数线性增加学习率
    "weight_decay": 0.01,                # 权重衰减（L2正则化）
    "fp16": True,                        # 混合精度训练（FP16节省显存加速）
    "gradient_accumulation": 2,          # 梯度累积步数（等效增大batch）
    "save_steps": 50,                    # 每N步保存检查点
    "eval_steps": 50,                    # 每N步评估验证集
    "logging_steps": 10,                 # 每N步打印训练日志
    "max_grad_norm": 1.0,                # 梯度裁剪阈值
    "temperature": 0.05,                 # 对比学习温度参数
    # 损失函数选择：triplet / contrastive / cosine_sim / matryoshka
    "loss_type": "triplet",
    "triplet_margin": 0.3,               # Triplet Loss的margin
    "contrastive_margin": 0.5,           # Contrastive Loss的margin
    "cosine_target": 0.8,                # Cosine Similarity Loss目标相似度
    "matryoshka_dims": [128, 256, 512, 1024],  # Matryoshka Loss的维度列表
}

# ======================== 评估参数 ========================

EVAL_CONFIG = {
    "top_k": [1, 3, 5, 10],              # Recall@K的K值列表
    "test_size": 50,                      # 评估查询数量
}

# ======================== 测试问题（RAG检索评估用） ========================

# 招股说明书领域测试问题（验证微调后Embedding在真实RAG检索中的效果）
RAG_TEST_QUESTIONS = [
    "武汉力源信息技术股份有限公司本次发行股数是多少？",
    "武汉力源信息技术股份有限公司募集资金拟投资哪些项目？",
    "与武汉力源信息技术股份有限公司存在控制关系的关联方是谁？",
    "武汉力源信息技术股份有限公司组织结构图中销售部有几个部门？",
    "报告期内武汉兴图新科电子股份有限公司来自军用领域的收入分别是多少？",
    "武汉兴图新科电子股份有限公司参与制定了哪个技术标准？",
    "武汉兴图新科电子股份有限公司注册资本是多少？",
    "武汉兴图新科电子股份有限公司法定代表人是谁？",
]

# ======================== 路径初始化 ========================


def ensure_dirs():
    """创建所有必需的输出目录（首次运行时调用）"""
    for d in [OUTPUT_DIR, DATA_DIR, MODEL_DIR, EVAL_DIR]:
        d.mkdir(parents=True, exist_ok=True)


_LOG_OK = False
_TEE_DONE = False


def setup_logging():
    """初始化统一日志：控制台 + output/logs/rag工单11_系统日志.log"""
    global _LOG_OK, _TEE_DONE
    if _LOG_OK:
        return
    _LOG_OK = True
    import logging
    log_dir = OUTPUT_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = str(log_dir / "rag工单11_系统日志.log")
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
