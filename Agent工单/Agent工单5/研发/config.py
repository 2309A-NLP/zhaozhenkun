# -*- coding: utf-8 -*-
"""
config.py — 招股书RAG问答系统配置文件
功能：管理所有路径、API密钥、模型参数、索引参数
工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务
"""

import os  # 操作系统路径处理

# ============================================================
# 数据集路径
# ============================================================
# 数据集根目录（自动检测Windows/WSL路径）
_candidates = [  # 候选路径列表
    "C:/Users/31326/bs_challenge_financial_14b_dataset",  # Windows原生路径
    "/mnt/c/Users/31326/bs_challenge_financial_14b_dataset",  # WSL挂载路径
    os.path.join(os.path.expanduser("~"), "bs_challenge_financial_14b_dataset")  # 用户主目录
]
DATASET_DIR = ""  # 数据集根路径
for _p in _candidates:  # 遍历候选
    if os.path.exists(_p):  # 路径存在
        DATASET_DIR = _p  # 使用此路径
        break  # 找到即停

# PDF解析后的TXT文本目录（80个文件，共44MB）
PDF_TXT_DIR = os.path.join(DATASET_DIR, "pdf_txt_file")  # 招股书TXT文本存放目录

# 问题文件路径（JSONL格式，每行一个{"id":..., "question":...}）
QUESTION_PATH = os.path.join(DATASET_DIR, "question.json")  # 问题文件

# 输出答案文件路径
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "answer_result.jsonl")  # 输出JSONL

# 索引缓存文件路径（避免每次启动重新索引）
INDEX_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index_cache")  # 索引缓存目录
os.makedirs(INDEX_CACHE_DIR, exist_ok=True)  # 自动创建缓存目录

# ============================================================
# DeepSeek API 配置
# ============================================================
DEEPSEEK_BASE_URL = "https://api.deepseek.com"  # DeepSeek API地址
DEEPSEEK_API_KEY = ""  # API密钥
DEEPSEEK_MODEL = "deepseek-v4-pro"  # 模型名称
API_TIMEOUT = 120  # API请求超时（秒）
MAX_RETRIES = 3  # API调用最大重试次数

# ============================================================
# 文本分块参数
# ============================================================
CHUNK_SIZE = 1200  # 每个文本块的目标字符数
CHUNK_OVERLAP = 200  # 相邻块之间的重叠字符数

# ============================================================
# 检索参数
# ============================================================
TOP_K = 10  # 每次检索返回的文本块数（招股书答案常埋在文件深处，需要更多块覆盖）

# ============================================================
# TF-IDF向量化参数
# ============================================================
MAX_FEATURES = 20000  # 词汇表最大特征数（2万保证专有名词覆盖）
NGRAM_RANGE = (2, 4)  # 字符级2-4gram（长公司名需要更长n-gram匹配）

# ============================================================
# 批量处理参数
# ============================================================
PROGRESS_INTERVAL = 10  # 每处理N题打印一次进度
SAVE_INTERVAL = 100  # 每N题自动保存一次

# 打印配置信息
if __name__ == "__main__":  # 直接运行本脚本
    import logging  # 日志
    logging.basicConfig(level=logging.INFO, format="%(message)s")  # 配置
    log = logging.getLogger(__name__)  # 日志器
    log.info("PDF文本目录: %s", PDF_TXT_DIR)  # 打印路径
    log.info("问题文件: %s", QUESTION_PATH)  # 打印路径
    log.info("输出路径: %s", OUTPUT_PATH)  # 打印路径
    log.info("索引缓存: %s", INDEX_CACHE_DIR)  # 打印路径
    log.info("模型: %s", DEEPSEEK_MODEL)  # 打印模型
    log.info("分块: %d, 重叠: %d, Top-K: %d", CHUNK_SIZE, CHUNK_OVERLAP, TOP_K)  # 打印参数
