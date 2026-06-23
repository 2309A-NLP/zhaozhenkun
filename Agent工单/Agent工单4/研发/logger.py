# -*- coding: utf-8 -*-
"""
logger.py — 统一日志系统
功能: 控制台+文件双通道日志，支持UTF-8中文输出
工单编号: 人工智能NLP-Agent数字人项目-基金问答智能体任务
"""
import logging
import os
import sys


def setup_logging(level: str = "INFO", log_file: str = None, name: str = "fund_qa"):
    """初始化全局日志配置。"""
    log_level = getattr(logging, level.upper(), logging.INFO)
    fmt = "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s"
    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")
    root = logging.getLogger(name)
    root.handlers.clear()
    root.setLevel(log_level)
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.DEBUG if level.upper() == "DEBUG" else logging.INFO)
    ch.setFormatter(formatter)
    root.addHandler(ch)
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        root.addHandler(fh)
    return root


def get_logger(name: str = "fund_qa") -> logging.Logger:
    return logging.getLogger(name)
