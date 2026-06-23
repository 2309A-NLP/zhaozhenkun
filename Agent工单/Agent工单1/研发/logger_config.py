# -*- coding: utf-8 -*-
"""
文件功能：日志模块 —— 统一配置控制台输出和文件写入的日志系统。
工单编号：人工智能NLP-Agent数字人项目-记账本任务

职责说明：
  1. 创建日志目录（部署/logs/）
  2. 配置根 logger，设置日志级别、格式、处理器
  3. 将日志同时输出到：
     - 控制台（StreamHandler）：方便开发调试时实时查看
     - 文件（FileHandler）：持久化保存，便于事后排查

日志格式化模板说明：
  %(asctime)s  日志时间戳（精确到毫秒）
  %(levelname)s 日志级别（INFO / WARNING / ERROR）
  %(name)s      logger 名称（模块层级标识）
  %(message)s   日志消息正文
"""

# ---------- 标准库导入 ----------
import logging          # Python 标准日志库
from pathlib import Path  # 跨平台路径处理


# ---------- 日志格式常量 ----------
# 定义统一的日志输出格式
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def setup_logging(base_dir: Path) -> Path:
    """
    初始化日志系统，创建日志目录和文件，配置输出格式。

    参数:
      base_dir: 项目根目录（Path 对象）

    返回:
      日志文件的完整路径
    """
    # ---------- 创建日志目录 ----------
    # 日志文件存放于 部署/logs/ 目录下
    log_dir = base_dir / "部署" / "logs"
    # parents=True: 如果父目录不存在则逐级创建
    # exist_ok=True: 如果目录已存在也不报错
    log_dir.mkdir(parents=True, exist_ok=True)

    # 日志文件完整路径
    log_path = log_dir / "agent_work_order_1.log"

    # ---------- 配置根 logger ----------
    # 获取 Python 的根 logger，后续所有模块的 logger 都继承此配置
    root_logger = logging.getLogger()
    # 设置全局最低日志级别为 INFO（DEBUG 级别的日志将不被输出）
    root_logger.setLevel(logging.INFO)
    # 清空已有的 handler，避免重复添加（多次调用 setup_logging 时安全）
    root_logger.handlers.clear()

    # ---------- 创建日志格式化器 ----------
    # 所有 handler 共用同一个 Formatter，确保格式一致
    formatter = logging.Formatter(LOG_FORMAT)

    # ---------- 文件日志处理器 ----------
    # FileHandler：将日志写入文件
    file_handler = logging.FileHandler(log_path, encoding="utf-8")  # 指定 UTF-8 编码确保中文不乱码
    file_handler.setLevel(logging.INFO)     # 文件记录 INFO 及以上级别的日志
    file_handler.setFormatter(formatter)    # 应用格式

    # ---------- 控制台日志处理器 ----------
    # StreamHandler：将日志输出到终端（stderr）
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)   # 终端也显示 INFO 及以上级别
    stream_handler.setFormatter(formatter)  # 应用格式

    # ---------- 注册处理器 ----------
    # 将两个 handler 添加到根 logger
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)
    # 阻止日志继续向父级传播（避免重复输出）
    root_logger.propagate = False

    # 返回日志文件路径，供调用方使用
    return log_path
