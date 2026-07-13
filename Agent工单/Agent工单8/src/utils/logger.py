"""
src/utils/logger.py - 日志系统模块
功能: 提供统一的日志配置和输出，支持控制台和文件两种输出方式。
      所有模块通过 get_logger() 获取各自命名的 logger 实例。
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import logging
import sys
import os
from pathlib import Path


def setup_logging(level: str = "INFO", fmt: str = None, log_file: str = None) -> None:
    """
    初始化全局日志配置。

    参数:
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR)
        fmt: 自定义日志格式
        log_file: 日志文件路径，None 时仅输出到控制台
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    if fmt is None:
        fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")

    # 清除已有 handlers，避免重复
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(log_level)

    # 控制台 handler
    console_h = logging.StreamHandler(sys.stderr)
    console_h.setFormatter(formatter)
    root.addHandler(console_h)

    # 文件 handler（可选）
    if log_file:
        os.makedirs(Path(log_file).parent, exist_ok=True)
        file_h = logging.FileHandler(log_file, encoding="utf-8")
        file_h.setFormatter(formatter)
        root.addHandler(file_h)


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的 logger 实例，通常传入 __name__。"""
    return logging.getLogger(name)
