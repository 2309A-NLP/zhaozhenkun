# -*- coding: utf-8 -*-
"""
config.py — 项目配置文件
功能：集中管理所有路径、API密钥、模型参数等常量
工单编号：人工智能NLP-Agent数字人项目-基金问答智能体任务
"""

import os  # 操作系统路径处理

# ============================================================
# 数据集路径配置
# ============================================================
# 数据集根目录（bs_challenge_financial_14b_dataset）
# 自动检测路径：兼容WSL环境和Windows原生环境
_user_home = os.path.expanduser("~")  # 获取当前用户主目录
# 候选路径列表（按优先级排列）
_candidates = [  # 多个可能的路径
    os.path.join(_user_home, "bs_challenge_financial_14b_dataset"),  # ~/bs_challenge...
    "/mnt/c/Users/31326/bs_challenge_financial_14b_dataset",  # WSL挂载Windows路径
    "C:/Users/31326/bs_challenge_financial_14b_dataset"  # Windows原生路径
]
DATASET_DIR = _user_home  # 默认值
for _path in _candidates:  # 遍历候选路径
    if os.path.exists(_path):  # 路径存在
        DATASET_DIR = _path  # 使用该路径
        break  # 找到即停止

# SQLite数据库文件完整路径（1.46GB，10张表）
DB_PATH = os.path.join(  # 拼接数据库文件路径
    DATASET_DIR,  # 数据集根目录
    "dataset",  # 数据子目录
    "博金杯比赛数据.db"  # 数据库文件名
)

# 问题文件路径（1000道题目，JSONL格式每行一个JSON）
QUESTION_PATH = os.path.join(  # 拼接问题文件路径
    DATASET_DIR,  # 数据集根目录
    "question.json"  # 问题文件名（虽然扩展名是.json但是JSONL格式）
)

# PDF解析后的文本文件目录（80个TXT文件，用于招股书类问题）
PDF_TXT_DIR = os.path.join(  # 拼接PDF文本目录路径
    DATASET_DIR,  # 数据集根目录
    "pdf_txt_file"  # PDF文本文件子目录
)

# 输出答案文件路径（补全answer字段后的JSONL文件）
OUTPUT_PATH = os.path.join(  # 拼接输出文件路径
    os.path.dirname(os.path.abspath(__file__)),  # 当前脚本所在目录（Agent工单4）
    "answer_result.jsonl"  # 输出结果文件名
)

# ============================================================
# DeepSeek API 配置
# ============================================================
# DeepSeek API基础URL
DEEPSEEK_BASE_URL = "https://api.deepseek.com"  # API服务地址

# DeepSeek API密钥（用于身份认证）
DEEPSEEK_API_KEY = ""  # API密钥

# 使用的DeepSeek模型名称
DEEPSEEK_MODEL = "deepseek-v4-pro"  # 模型版本

# API调用超时时间（秒）
API_TIMEOUT = 120  # 单次API请求最长等待时间

# API调用最大重试次数
MAX_RETRIES = 3  # 失败后最多重试3次

# ============================================================
# NL2SQL Prompt 配置
# ============================================================
# 每个表取样的行数（用于给LLM展示示例数据）
SAMPLE_ROWS = 3  # 每张表取3行示例数据

# SQL查询超时时间（秒）
SQL_TIMEOUT = 60  # 单条SQL最长执行时间

# 最大SQL结果行数（防止返回过多数据）
MAX_RESULT_ROWS = 100  # 最多返回100行结果

# ============================================================
# 批次处理配置
# ============================================================
# 每处理多少题打印一次进度
PROGRESS_INTERVAL = 10  # 每10题汇报一次进度

# 是否启用PDF文本检索（对于无法用SQL回答的题目）
ENABLE_PDF_SEARCH = True  # 启用PDF文本搜索作为后备方案

# 打印配置信息（调试用）
if __name__ == "__main__":  # 如果直接运行本脚本
    print(f"数据集目录: {DATASET_DIR}")  # 打印数据集路径
    print(f"数据库路径: {DB_PATH}")  # 打印数据库路径
    print(f"问题文件: {QUESTION_PATH}")  # 打印问题文件路径
    print(f"输出路径: {OUTPUT_PATH}")  # 打印输出路径
    print(f"模型: {DEEPSEEK_MODEL}")  # 打印模型名称
