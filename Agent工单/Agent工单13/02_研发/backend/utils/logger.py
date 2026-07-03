"""
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
统一日志模块 —— 同时输出到控制台和文件，所有模块共享一个日志器
"""
import logging, sys
from pathlib import Path
from datetime import datetime

# 日志目录：项目根目录/data/logs/
LOG_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)  # 自动创建日志目录

# 日志文件按日期命名，方便按天查找
LOG_FILE = LOG_DIR / f"agent_{datetime.now().strftime('%Y%m%d')}.log"

# 两种格式：控制台简洁，文件详细（含时间戳和模块名）
CONSOLE_FORMAT = "%(levelname)-5s %(message)s"
FILE_FORMAT = "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s"
LOG_LEVEL = logging.INFO  # 全局日志级别


def _create_root_logger() -> logging.Logger:
    """创建根日志器，所有子模块通过 getLogger('medical_agent.xxx') 获取"""
    root = logging.getLogger("medical_agent")  # 统一的 logger 命名空间
    root.setLevel(LOG_LEVEL)

    if root.handlers:  # 避免重复添加（uvicorn reload 会多次 import）
        return root

    # 控制台 Handler：只显示级别和消息
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(LOG_LEVEL)
    console.setFormatter(logging.Formatter(CONSOLE_FORMAT))
    root.addHandler(console)

    # 文件 Handler：记录完整信息到磁盘
    file_handler = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
    file_handler.setLevel(LOG_LEVEL)
    file_handler.setFormatter(logging.Formatter(FILE_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"))
    root.addHandler(file_handler)

    return root


# 模块加载时立即创建根日志器
_root = _create_root_logger()


def get_logger(name: str = None) -> logging.Logger:
    """获取子模块日志器，用法: _log = get_logger('模块名')"""
    if name:
        return _root.getChild(name)  # 生成 medical_agent.模块名 的子 logger
    return _root
