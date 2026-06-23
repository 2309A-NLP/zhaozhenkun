# -*- coding: utf-8 -*-
"""
文件功能：项目统一入口 —— 启动日程提醒智能体 Web 服务。

职责说明：
  1. 加载配置文件（部署/config.json），缺失时使用默认配置
  2. 初始化日志系统（控制台 + 文件双输出）
  3. 初始化 SQLite 数据库（自动建表）
  4. 启动后台定时调度器（每 10 秒检查一次到期日程）
  5. 创建 Flask Web 应用并启动 HTTP 服务

运行方式：
  python run.py              # 默认在 5051 端口启动
  python run.py --port 8080  # 指定端口启动

项目背景：
  工单编号：人工智能 NLP-Agent 数字人项目-日程提醒智能体任务
"""

# ---------- 标准库导入 ----------
import argparse    # 命令行参数解析（--web, --port）
import json        # 读取 JSON 配置文件
import logging     # 日志记录
import sys         # 系统相关（修改 sys.path、退出程序）
import traceback   # 打印异常堆栈，便于排查问题
from pathlib import Path  # 跨平台路径处理

# ---------- 项目根目录常量 ----------
# 获取当前文件所在目录（即项目根目录）
BASE_DIR = Path(__file__).resolve().parent
# 配置文件路径：部署/config.json
CONFIG_PATH = BASE_DIR / "部署" / "config.json"

# ---------- 路径修正 ----------
# 确保项目根目录在 Python 模块搜索路径中
# 这样无论从哪里运行 run.py 都能正确 import 研发.xxx
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# 获取当前模块的 logger（日志输出带模块名前缀标识）
logger = logging.getLogger("agent_work_order_2.run")


def load_config() -> dict:
    """
    读取项目配置文件，返回配置字典。

    优先从 部署/config.json 读取，如果文件不存在或解析失败则使用默认配置。
    """
    logger.debug("加载配置文件：%s", CONFIG_PATH)

    # 配置文件存在时尝试读取
    if CONFIG_PATH.exists():
        try:
            # 以 UTF-8 编码读取 JSON 文件（支持中文内容）
            config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            # 日志输出配置时隐藏 debug 敏感信息
            logger.info("配置加载成功：%s", {k: v for k, v in config.items() if k != "debug"})
            return config
        except (json.JSONDecodeError, IOError) as e:
            # JSON 格式错误或文件读取失败
            logger.error("配置文件解析失败：%s，使用默认配置", e)
    else:
        # 配置文件不存在
        logger.warning("配置文件不存在：%s，使用默认配置", CONFIG_PATH)

    # 硬编码的默认配置（兜底）
    defaults = {
        "project_name": "Agent工单2",       # 项目名称
        "db_name": "schedule_notes.db",      # SQLite 数据库文件名
        "host": "127.0.0.1",                 # Web 服务监听地址（仅本机）
        "port": 5051,                        # Web 服务默认端口
        "debug": False,                      # Flask 调试模式开关
        "llm_base_url": "https://api.deepseek.com",  # LLM API 地址
        "llm_api_key": "",                   # LLM API 密钥（为空则禁用 LLM）
        "llm_model": "deepseek-chat",        # LLM 模型名称
        "llm_temperature": 0.1,              # LLM 温度参数
        "llm_max_tokens": 1024,              # LLM 最大 token 数
    }
    logger.info("使用默认配置：%s", defaults)
    return defaults


def main() -> None:
    """
    程序主入口：按顺序初始化日志→数据库→调度器→Web 服务。

    初始化顺序很重要：
      1. 日志先初始化，后续所有模块的日志才能正常输出
      2. 数据库在调度器和 Web 之前初始化，因为它们都依赖数据库
      3. 调度器在 Web 启动前开始运行，确保启动后立即能检查提醒
    """
    # ---------- 延迟导入（避免循环依赖） ----------
    # 在函数内部导入，等 sys.path 修正完成后再加载
    from 研发.logger_config import setup_logging    # 日志配置函数
    from 研发.scheduler import ReminderScheduler     # 后台提醒调度器
    from 研发.database import ScheduleDatabase       # 日程数据库操作类

    # ====== 第 1 步：初始化日志系统 ======
    # 必须最先执行，后续所有 logger.info/error 才能正常输出
    log_path = setup_logging(BASE_DIR)
    logger.info("=" * 50)
    logger.info("Agent工单2 - 日程提醒智能体 启动中...")
    logger.info("日志文件：%s", log_path)
    logger.info("项目路径：%s", BASE_DIR)

    # ====== 第 2 步：加载配置 ======
    config = load_config()
    logger.info("项目名称：%s", config.get("project_name"))
    logger.info("数据库文件：%s", config.get("db_name"))
    logger.info("监听地址：%s:%s", config.get("host"), config.get("port"))

    # ====== 第 3 步：解析命令行参数 ======
    parser = argparse.ArgumentParser(description="日程提醒智能体 Agent")
    parser.add_argument("--web", action="store_true", help="启动 Web 界面")       # --web 标志
    parser.add_argument("--port", type=int, default=config.get("port", 5051), help="服务端口")  # --port 端口号
    args = parser.parse_args()
    logger.debug("命令行参数：web=%s, port=%s", args.web, args.port)

    # ====== 第 4 步：初始化数据库 ======
    logger.info("初始化数据库...")
    try:
        # 数据库文件路径（项目根目录下）
        db_path = BASE_DIR / config.get("db_name", "schedule_notes.db")
        # 创建数据库实例（自动建表）
        database = ScheduleDatabase(db_path)
        logger.info("数据库初始化完成：%s", db_path)
    except Exception as e:
        # 数据库初始化失败是致命错误，直接退出
        logger.error("数据库初始化失败：%s", e)
        logger.debug("异常堆栈：%s", traceback.format_exc())
        sys.exit(1)

    # ====== 第 5 步：启动后台提醒调度器 ======
    logger.info("启动后台提醒调度器...")
    try:
        # 传入 lambda 延迟获取数据库实例（确保每次都拿到最新引用）
        scheduler = ReminderScheduler(lambda: database)
        scheduler.start()  # 启动守护线程，开始后台轮询
    except Exception as e:
        logger.error("调度器启动失败：%s", e)
        logger.debug("异常堆栈：%s", traceback.format_exc())
        sys.exit(1)

    # ====== 第 6 步：创建 Flask Web 应用 ======
    from 研发.web_app import create_app
    logger.info("创建 Web 应用...")
    try:
        # 将数据库和调度器注入到 Web 应用中
        app = create_app(BASE_DIR, config, scheduler)
    except Exception as e:
        logger.error("Web 应用创建失败：%s", e)
        logger.debug("异常堆栈：%s", traceback.format_exc())
        scheduler.stop()   # 失败时停止调度器
        sys.exit(1)

    # ====== 第 7 步：启动欢迎信息 ======
    logger.info("-" * 40)
    logger.info("✅ 日程提醒智能体启动成功！")
    logger.info("📝 添加日程：下午5点开会")
    logger.info("🔍 查询日程：我今天的日程有哪些？")
    logger.info("🗑 删除日程：删除日程1")
    logger.info("🌐 Web 地址：http://%s:%s", config.get("host", "127.0.0.1"), args.port)
    logger.info("=" * 50)

    # ====== 第 8 步：启动 Flask 开发服务器 ======
    try:
        app.run(
            host=config.get("host", "127.0.0.1"),  # 监听地址
            port=args.port,                         # 监听端口
            debug=config.get("debug", False)        # 调试模式
        )
    except KeyboardInterrupt:
        # 用户按下 Ctrl+C 正常退出
        logger.info("收到中断信号，正在关闭...")
    except Exception as e:
        # 其他运行异常
        logger.error("Web 服务运行异常：%s", e)
        logger.debug("异常堆栈：%s", traceback.format_exc())
    finally:
        # 无论正常退出还是异常，都要确保调度器停止
        logger.info("正在关闭调度器...")
        scheduler.stop()
        logger.info("Agent工单2 已停止")


# ---------- 入口判断 ----------
# 当脚本直接运行时（而非被 import 时），执行 main()
if __name__ == "__main__":
    main()
