# -*- coding: utf-8 -*-
"""
logger.py — 统一日志模块
功能：全项目唯一日志配置，console + 文件双输出，支持日志轮转
用法：其他模块直接 import logger，用 logger.info() / logger.error() 等
工单编号：人工智能NLP-Agent数字人项目-基金问答智能体任务
"""

import logging
import logging.handlers
import os
import sys

# 项目根目录
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOG_DIR = os.path.join(_PROJECT_ROOT, "logs")
os.makedirs(_LOG_DIR, exist_ok=True)

# ============================================================
# 日志格式
# ============================================================
# console: 简洁带时间
_CONSOLE_FMT = logging.Formatter(
    "%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
# 文件: 详细，含文件名和行号
_FILE_FMT = logging.Formatter(
    "%(asctime)s  %(levelname)-7s  %(name)s:%(lineno)d  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ============================================================
# 全局 logger 实例
# ============================================================
logger = logging.getLogger("fund_dh")
logger.setLevel(logging.DEBUG)

# --- console handler ---
_console = logging.StreamHandler(sys.stdout)
_console.setLevel(logging.INFO)
_console.setFormatter(_CONSOLE_FMT)
logger.addHandler(_console)

# --- 文件 handler（每天一个，保留30天） ---
_file = logging.handlers.TimedRotatingFileHandler(
    filename=os.path.join(_LOG_DIR, "fund_dh.log"),
    when="midnight",
    interval=1,
    backupCount=30,
    encoding="utf-8",
)
_file.setLevel(logging.DEBUG)
_file.setFormatter(_FILE_FMT)
logger.addHandler(_file)

# ----- 单独的错误日志文件 -----
_error_file = logging.handlers.TimedRotatingFileHandler(
    filename=os.path.join(_LOG_DIR, "error.log"),
    when="midnight",
    interval=1,
    backupCount=30,
    encoding="utf-8",
)
_error_file.setLevel(logging.ERROR)
_error_file.setFormatter(_FILE_FMT)
logger.addHandler(_error_file)

logger.info(f"日志系统 OK，文件在这里: {os.path.join(_LOG_DIR, 'fund_dh.log')}")
logger.info(f"错误日志: {os.path.join(_LOG_DIR, 'error.log')}")
