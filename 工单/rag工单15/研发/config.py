# -*- coding: utf-8 -*-
"""
配置文件 — 集中管理所有路径、API密钥、模型参数。

功能说明：
- BGE-M3 模型路径（用于文本向量化）
- MiMo API 密钥和接口地址
- PDF 文件路径和输出目录
- 检索参数（Top-K、RRF融合权重等）
"""
import os  # 导入os模块，用于环境变量和路径操作
import sys  # stdout 重定向到日志
from pathlib import Path  # 导入Path类，用于跨平台路径操作

# ==================== 项目路径 ====================
# 获取当前文件所在目录的上两级目录（项目根目录，因文件在研发/子目录下）
BASE_DIR = Path(__file__).resolve().parent.parent

# ==================== BGE-M3 模型配置 ====================
# BGE-M3 嵌入模型的本地路径（用于文本向量化）
BGE_M3_PATH = os.getenv("BGE_M3_PATH", r"C:\Users\31326\Desktop\bge-m3")
# WSL环境下自动转换Windows路径
if os.name == "posix" and BGE_M3_PATH.startswith("C:"):
    BGE_M3_PATH = BGE_M3_PATH.replace("C:", "/mnt/c").replace("\\", "/")
# 向量维度（BGE-M3 输出为1024维）
VECTOR_DIM = 1024
# 批处理大小（显存不足时可调小）
BATCH_SIZE = 2
# 最大序列长度（超过的文本会被截断）
MAX_SEQ_LEN = 256

# ==================== MiMo API 配置 ====================
# MiMo 大模型 API 密钥
MIMO_API_KEY = "tp-cx2rczcnaoae6bytkvs50kormwv69c101zar0nn4pu702wde"
# MiMo API 基础地址
MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
# 使用的模型名称（v2.5-pro 是推理模型，content为空，reasoning_content有输出）
MIMO_MODEL = "mimo-v2.5-pro"
# v2-omni 适合结构化输出评估（content 有值）
MIMO_EVAL_MODEL = "mimo-v2-omni"
# API 调用超时时间（秒）
MIMO_TIMEOUT = 45

# ==================== PDF 配置 ====================
# 专利 PDF 文件路径（在测试/目录下）
PDF_PATH = str(BASE_DIR / "测试" / "CN100347506C.pdf")
# 输出目录（在测试/目录下）
OUTPUT_DIR = str(BASE_DIR / "测试" / "output")

# ==================== 检索参数 ====================
# 检索返回的候选结果数量
RETRIEVE_TOP_K = 10
# 重排后返回的最终结果数量
RERANK_TOP_K = 5
# RRF（倒数排名融合）的常数k
RRF_K = 60
# 文本检索权重（融合时）
TEXT_WEIGHT = 0.5
# 图像增强检索权重（融合时）
IMAGE_WEIGHT = 0.5

# ==================== 6个测试问题 ====================
# 工单要求的6个测试问题（文本+图文混合）
TEST_QUESTIONS = [
    # Q1: 纯文本问题
    {"question": "根据专利文本，本发明主要涉及哪种物料的分配装置？",
     "answer": "块状散料", "type": "text"},
    # Q2: 纯文本问题
    {"question": "根据专利文本，本发明的分散装置包含以下哪个组件？",
     "answer": "链条", "type": "text"},
    # Q3: 图文混合问题
    {"question": "在文件中第11页图3中，编号13的部件相对于编号12的部件的位置关系是？",
     "answer": "位于编号12的部件之内", "type": "image_text"},
    # Q4: 图文混合问题
    {"question": "在文件中第11页图3中，编号14的部件位于整个装置的哪个位置？",
     "answer": "顶部", "type": "image_text"},
    # Q5: 图文混合问题
    {"question": "根据文件中第11页图3，散料从部件14进入后，下一步会经过哪个部件？",
     "answer": "部件13", "type": "image_text"},
    # Q6: 图文混合问题
    {"question": "在文件中第11页图3的装置中，如果需要调整链条的位置，需要操作哪个部件？",
     "answer": "部件11", "type": "image_text"},
]

_LOGGING_DONE = False


_TEE_DONE = False

def setup_logging():
    """初始化统一日志：控制台 + output/logs/rag工单15_系统日志.log"""
    global _LOGGING_DONE, _TEE_DONE
    if _LOGGING_DONE:
        return
    _LOGGING_DONE = True
    import logging
    import os as _os
    log_dir = _os.path.join(str(BASE_DIR), "output", "logs")
    _os.makedirs(log_dir, exist_ok=True)
    log_file = _os.path.join(log_dir, "rag工单15_系统日志.log")
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
