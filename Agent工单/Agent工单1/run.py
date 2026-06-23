# -*- coding: utf-8 -*-
"""
文件功能：项目统一入口 —— 启动家庭记账本 Web 服务。

工单编号：人工智能NLP-Agent数字人项目-记账本任务

职责说明：
  1. 读取项目配置文件（部署/config.json）
  2. 初始化日志系统
  3. 解析命令行参数（是否启动 Web、端口号等）
  4. 创建 Flask 应用并启动 Web 服务器

运行方式：
  python run.py              # 默认在 5050 端口启动
  python run.py --port 8080   # 指定端口启动
"""

# ---------- 标准库导入 ----------
import argparse   # 命令行参数解析
import json       # 读取 JSON 配置文件
import logging    # 日志记录
from pathlib import Path  # 跨平台路径处理

# ---------- 项目根目录常量 ----------
# Path(__file__).resolve() 获取当前文件的绝对路径
# .parent 取其父目录，即项目的根目录
BASE_DIR = Path(__file__).resolve().parent

# 配置文件路径：部署/config.json
CONFIG_PATH = BASE_DIR / "部署" / "config.json"


def load_config() -> dict:
    """
    读取项目配置文件，返回配置字典。

    如果配置文件存在，则从 JSON 文件读取；
    如果文件不存在，则使用内置默认配置。
    """
    # 检查配置文件是否存在
    if CONFIG_PATH.exists():
        # 存在则读取 JSON 文件，encoding="utf-8" 确保中文正常解析
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    # 配置文件不存在时，使用硬编码的默认配置
    return {
        "project_name": "Agent工单1",       # 项目名称
        "db_name": "money_notes.db",         # SQLite 数据库文件名
        "host": "127.0.0.1",                 # Web 服务监听地址（仅本机访问）
        "port": 5050,                        # Web 服务默认端口
        "debug": False,                      # 是否开启 Flask 调试模式
        "llm_base_url": "https://api.deepseek.com",  # LLM API 地址
        "llm_api_key": "",                   # LLM API 密钥（为空则禁用 LLM）
        "llm_model": "deepseek-chat",        # LLM 模型名称
        "llm_temperature": 0.1,              # LLM 温度参数
        "llm_max_tokens": 1024,              # LLM 最大 token 数
    }


def main() -> None:
    """
    程序主入口：解析命令行参数、初始化日志、创建并启动 Flask Web 服务。
    """
    # ---------- 初始化日志系统 ----------
    # 从研发目录导入日志配置模块
    from 研发.logger_config import setup_logging

    # setup_logging 创建日志目录和文件，返回日志文件路径
    log_path = setup_logging(BASE_DIR)

    # 获取当前模块对应的 logger 实例（日志输出时会带模块名标识）
    logger = logging.getLogger("agent_work_order_1.run")

    # ---------- 加载项目配置 ----------
    config = load_config()

    # ---------- 解析命令行参数 ----------
    # 创建命令行参数解析器，description 为帮助信息
    parser = argparse.ArgumentParser(description="家庭记账本 Agent")

    # --web 参数：标记是否启动 Web 界面（默认 False）
    parser.add_argument("--web", action="store_true", help="启动 Web 界面")

    # --port 参数：指定服务监听端口，默认值从配置文件读取，若配置不存在则用 5050
    parser.add_argument("--port", type=int, default=config.get("port", 5050), help="服务端口")

    # 执行参数解析
    args = parser.parse_args()

    # ---------- 创建 Flask 应用 ----------
    # 延迟导入，避免在非 Web 模式下加载 Web 依赖
    from 研发.web_app import create_app

    # 创建 Flask app 实例，传入项目根目录和配置字典
    app = create_app(BASE_DIR, config)

    # ---------- 启动前日志输出 ----------
    logger.info("项目启动，日志文件：%s", log_path)                           # 日志文件路径
    logger.info("欢迎使用咱们小家专属记账本")                                  # 欢迎语
    logger.info("输入格式：x年x月x日，谁做什么事收入/支出多少钱")              # 输入格式说明
    logger.info("Web 地址：http://%s:%s", config.get("host", "127.0.0.1"), args.port)  # 服务地址

    # ---------- 启动 Flask 开发服务器 ----------
    # host: 监听地址，默认 127.0.0.1（仅本机）
    # port: 监听端口，来自命令行参数
    # debug: 调试模式开关，默认关闭
    app.run(host=config.get("host", "127.0.0.1"), port=args.port, debug=config.get("debug", False))


# ---------- 入口判断 ----------
# 当脚本直接运行时（而非被 import 时），执行 main()
if __name__ == "__main__":
    main()
