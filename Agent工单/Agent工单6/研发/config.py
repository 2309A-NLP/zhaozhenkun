# -*- coding: utf-8 -*-
"""
config.py — Agent智能体配置文件
功能：DeepSeek(文本问答/意图识别) + Qwen(文生图) 双模型配置
工单编号：人工智能NLP-Agent数字人项目-智能体任务
"""

import os  # 路径处理

# ============================================================
# 项目根目录
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Agent工单6目录

# ============================================================
# DeepSeek — 文本问答、意图识别、NL2SQL、RAG
# ============================================================
DEEPSEEK_BASE_URL = "https://api.deepseek.com"  # API地址
DEEPSEEK_API_KEY = ""  # API密钥
DEEPSEEK_MODEL = "deepseek-v4-pro"  # 模型名称

# ============================================================
# Qwen (通义千问) — 文生图
# ============================================================
QWEN_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"  # API地址
QWEN_API_KEY = ""  # API密钥
QWEN_MODEL = "qwen-vl-plus"  # 多模态模型（支持图像理解）
QWEN_IMAGE_MODEL = "qwen-vl-plus"  # 文生图模型

# ============================================================
# 工具路径（工单1-5已存在的项目）
# ============================================================
# Agent工单1-5 与 Agent工单6 平级，都在 Desktop 下
# BASE_DIR = .../Agent工单6/研发 → 上溯两层到 Desktop → 找到平级目录
_PROJECTS_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))  # Desktop 目录
TOOL_PATHS = {  # 5个工具的根路径
    "01_记账本": os.path.join(_PROJECTS_ROOT, "Agent工单1"),  # 记账本
    "02_日程提醒": os.path.join(_PROJECTS_ROOT, "Agent工单2"),  # 日程提醒
    "03_文生图": os.path.join(_PROJECTS_ROOT, "Agent工单3"),  # 文生图
    "04_基金问答": os.path.join(_PROJECTS_ROOT, "Agent工单4"),  # 基金NL2SQL
    "05_招股书问答": os.path.join(_PROJECTS_ROOT, "Agent工单5"),  # 招股书RAG
}

# ============================================================
# Agent 参数
# ============================================================
API_TIMEOUT = 120  # API超时（秒）
MAX_RETRIES = 2  # 最大重试次数
MAX_HISTORY = 10  # 多轮对话保留最近N条消息

# ============================================================
# 数据库路径（记账本和日程提醒共用SQLite）
# ============================================================
LEDGER_DB = os.path.join(TOOL_PATHS["01_记账本"], "money_notes.db")  # 记账本数据库
SCHEDULE_DB = os.path.join(TOOL_PATHS["02_日程提醒"], "schedule_notes.db")  # 日程数据库
# 本地回退DB（Agent工单2的DB不存在时自动创建在本地）
SCHEDULE_LOCAL_DB = os.path.join(BASE_DIR, "schedule_notes.db")

# 打印配置（调试用）
if __name__ == "__main__":  # 直接运行
    import logging  # 日志
    logging.basicConfig(level=logging.INFO, format="%(message)s")  # 配置
    log = logging.getLogger(__name__)  # 日志器
    log.info("DeepSeek: %s / %s", DEEPSEEK_BASE_URL, DEEPSEEK_MODEL)  # 打印
    log.info("Qwen: %s / %s", QWEN_BASE_URL, QWEN_IMAGE_MODEL)  # 打印
    for k, v in TOOL_PATHS.items():  # 遍历工具
        log.info("%s: %s (存在=%s)", k, v, os.path.exists(v))  # 打印路径
