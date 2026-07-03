"""
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
统一日志模块 —— 同时输出到控制台和文件，支持日志轮转
"""
import logging, sys  # 导入 Python 标准日志模块和系统模块
from pathlib import Path  # 导入 Path 用于跨平台路径处理
from datetime import datetime  # 导入日期时间处理模块
from logging.handlers import RotatingFileHandler  # 导入日志轮转文件处理器

# 日志目录：项目根目录/data/logs/（所有日志文件统一存放）
LOG_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "logs"  # 构建日志目录绝对路径
LOG_DIR.mkdir(parents=True, exist_ok=True)  # 自动创建日志目录（递归创建，已存在则跳过）

# 日志文件按日期命名，方便按天查找和清理（例如：agent_20250703.log）
LOG_FILE = LOG_DIR / f"agent_{datetime.now().strftime('%Y%m%d')}.log"  # 拼接带日期的日志文件完整路径

# 日志轮转配置
MAX_LOG_SIZE = 10 * 1024 * 1024  # 单个日志文件最大大小：10MB（超过此值自动轮转）
BACKUP_COUNT = 30                 # 轮转文件保留数量：最多保留最近 30 个备份文件
LOG_LEVEL = logging.INFO          # 全局日志级别：INFO（DEBUG 信息不输出）

# 两种日志格式：控制台简洁（仅级别+消息），文件详细（含时间戳、模块名等完整信息）
CONSOLE_FORMAT = "%(levelname)-5s %(message)s"  # 控制台格式：左对齐5字符级别 + 日志消息
FILE_FORMAT = "%(asctime)s | %(levelname)-5s | %(name)s | %(message)s"  # 文件格式：时间|级别|模块名|消息


def _create_root_logger() -> logging.Logger:  # 创建根日志器的函数
    """创建根日志器，所有子模块通过 getLogger('medical_agent.xxx') 获取"""
    root = logging.getLogger("medical_agent")  # 获取/创建统一的 logger 命名空间（根日志器）
    root.setLevel(LOG_LEVEL)  # 设置根日志器的日志级别

    if root.handlers:  # 如果已添加过处理器（uvicorn reload 会多次导入模块，防止重复添加）
        return root  # 直接返回已有的根日志器，不重复添加处理器

    # 控制台 Handler：将日志输出到标准输出流，格式简洁
    console = logging.StreamHandler(sys.stdout)  # 创建控制台日志处理器（输出到 stdout）
    console.setLevel(LOG_LEVEL)  # 设置控制台处理器的日志级别
    console.setFormatter(logging.Formatter(CONSOLE_FORMAT))  # 设置控制台的格式化器（简洁格式）
    root.addHandler(console)  # 将控制台处理器注册到根日志器

    # 文件 Handler：带自动轮转，将完整日志记录持久化到磁盘文件
    file_handler = RotatingFileHandler(  # 创建日志轮转文件处理器
        str(LOG_FILE), encoding="utf-8",  # 日志文件路径和 UTF-8 编码（支持中文）
        maxBytes=MAX_LOG_SIZE,  # 单个文件大小上限（字节）
        backupCount=BACKUP_COUNT,  # 备份文件保留个数
    )
    file_handler.setLevel(LOG_LEVEL)  # 设置文件处理器的日志级别
    file_handler.setFormatter(logging.Formatter(  # 设置文件格式化器
        FILE_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"))  # 文件详细格式 + 日期时间显示格式
    root.addHandler(file_handler)  # 将文件处理器注册到根日志器

    # 初始化日志（记录一条启动日志确认日志系统已正常工作）
    root.info("日志系统初始化: %s (max=%dMB, backups=%d)",  # 输出日志系统初始化信息
              LOG_FILE.name, MAX_LOG_SIZE // (1024*1024), BACKUP_COUNT)  # 参数：文件名、最大MB数、备份数

    return root  # 返回配置完成后的根日志器


# 模块加载时立即创建根日志器（导入本模块时自动初始化日志系统）
_root = _create_root_logger()  # 调用创建函数并将根日志器保存为模块级变量


def get_logger(name: str = None) -> logging.Logger:  # 获取子模块日志器的公共函数
    """获取子模块日志器，用法: _log = get_logger('模块名')"""
    if name:  # 如果指定了子模块名称
        return _root.getChild(name)  # 生成 medical_agent.模块名 的子 logger（继承根处理器的配置）
    return _root  # 未指定名称则直接返回根日志器
