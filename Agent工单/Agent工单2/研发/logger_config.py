# -*- coding: utf-8 -*-
"""
文件功能：日志模块 —— 统一配置控制台输出和文件写入的日志系统。

职责说明：
  1. 创建日志目录（部署/logs/）
  2. 配置根 logger，设置日志级别、格式、处理器
  3. 将日志同时输出到：
     - 文件（FileHandler）：记录 DEBUG 及以上全部日志，便于事后排查
     - 控制台（StreamHandler）：只显示 INFO 及以上，避免 DEBUG 信息刷屏

日志格式化模板说明：
  %(asctime)s   时间戳（精确到秒）
  %(levelname)-5s 日志级别，左对齐占 5 位
  %(name)s      logger 模块名（层级标识）
  %(message)s   日志消息正文

项目背景：
  工单编号：人工智能 NLP-Agent 数字人项目-日程提醒智能体任务
"""

# ---------- 标准库导入 ----------
import logging          # Python 标准日志库
from pathlib import Path  # 跨平台路径处理


# ---------- 日志格式化常量 ----------
# 日志输出格式：时间 | 级别 | 模块名 | 消息
LOG_FORMAT = "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s"
# 时间格式化：年-月-日 时:分:秒
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(base_dir: Path) -> Path:
    """
    初始化日志系统，创建日志目录和文件，配置双通道输出。

    参数:
      base_dir: 项目根目录（Path 对象）

    返回:
      日志文件的完整路径
    """
    # ---------- 创建日志目录 ----------
    # 日志文件存放于 部署/logs/ 目录
    log_dir = base_dir / "部署" / "logs"
    # parents=True: 自动创建不存在的父目录
    # exist_ok=True: 目录已存在也不报错
    log_dir.mkdir(parents=True, exist_ok=True)

    # 日志文件完整路径：部署/logs/agent_work_order_2.log
    log_path = log_dir / "agent_work_order_2.log"

    # ---------- 配置根 logger ----------
    # 获取 Python 根 logger，后续所有子 logger 都继承此配置
    root_logger = logging.getLogger()
    # 根日志设为 DEBUG 级别（最宽松），各 handler 自行决定过滤级别
    root_logger.setLevel(logging.DEBUG)
    # 清空已有的 handler，避免重复添加（支持多次调用）
    root_logger.handlers.clear()

    # ---------- 创建格式化器 ----------
    # 所有 handler 共用同一个 Formatter，指定时间格式
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # ---------- 文件日志处理器 ----------
    # 将日志写入文件，UTF-8 编码确保中文正常
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    # 文件记录 DEBUG 及以上（用于事后详细排查）
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # ---------- 控制台日志处理器 ----------
    # 将日志输出到终端（stderr）
    stream_handler = logging.StreamHandler()
    # 控制台只显示 INFO 及以上（避免 DEBUG 信息刷屏）
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    # ---------- 注册处理器 ----------
    # 将两个 handler 添加到根 logger
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)
    # 阻止日志向父级传播（避免重复输出）
    root_logger.propagate = False

    # ---------- 日志系统初始化完成确认 ----------
    # 单独获取一个 logger 来输出初始化完成信息
    logger = logging.getLogger("agent_work_order_2.logger")
    logger.info("日志系统初始化完成")
    logger.debug("日志文件：%s", log_path)
    logger.debug("文件日志级别：DEBUG，控制台日志级别：INFO")

    # 返回日志文件路径供调用方使用
    return log_path
