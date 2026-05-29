"""
main — ADSD 项目在线模块主入口文件。

功能说明：
- 创建 Flask Web 应用实例
- 注册所有路由（通过 register_routes）
- 在后台线程中异步初始化 RAG 系统（通过 init_system）
- 自动选择可用的端口号并启动 HTTP 服务
"""
# -*- coding: utf-8 -*-
# 指定文件编码为UTF-8，确保中文字符能正确处理

"""
RAG 对话系统主入口。

只负责：
1. 创建 Flask app
2. 注册路由
3. 异步初始化系统
4. 启动服务
"""

import logging
# 导入日志模块，用于输出运行日志
import os
# 导入os模块，用于读取环境变量（如端口号）
import threading
# 导入threading模块，用于在后台线程中异步初始化系统
from datetime import timedelta
# 从datetime导入timedelta，用于设置会话过期时间
from pathlib import Path
# 从pathlib导入Path，用于跨平台路径操作

from flask import Flask
# 从Flask框架导入Flask核心类，用于创建Web应用

try:
    from flask_cors import CORS
except Exception:
    def CORS(*args, **kwargs):
        return None
# 尝试导入flask_cors扩展（处理跨域请求），如果导入失败则用空函数替代

from 测试.app_monitor import QPSMonitor, choose_port
# 从监控模块导入QPS监控器和端口选择函数
from 研发.app_routes import register_routes
# 从路由模块导入路由注册函数
from 研发.app_services import init_system
# 从服务模块导入系统初始化函数
from 设计.config import SECRET_KEY, SESSION_TIMEOUT
# 从配置模块导入密钥和会话超时时间

logging.basicConfig(level=logging.INFO)
# 配置日志系统，设置日志级别为INFO（只输出INFO及以上级别的日志）
logger = logging.getLogger(__name__)
# 获取当前模块的日志记录器实例


def create_app():
    # 定义函数：创建并配置Flask应用实例
    
    template_dir = Path(__file__).resolve().parent / "templates"
    # 获取模板文件所在的目录路径（与当前文件同级的templates文件夹）
    app = Flask(__name__, template_folder=str(template_dir))
    # 创建Flask应用实例，指定模板文件夹路径
    app.secret_key = SECRET_KEY
    # 设置Flask应用的会话密钥，用于会话加密
    app.config.update(
        # 批量更新Flask应用配置
        SESSION_COOKIE_SAMESITE="Lax",
        # 设置会话Cookie的SameSite属性为Lax，防止CSRF攻击同时允许一定程度的跨站请求
        PERMANENT_SESSION_LIFETIME=timedelta(seconds=SESSION_TIMEOUT),
        # 设置永久会话的存活时间（从配置中读取）
        JSON_AS_ASCII=False,
        # 设置JSON响应不转义ASCII字符，使中文能正常显示
    )
    CORS(app, supports_credentials=True)
    # 启用跨域资源共享（CORS），并允许携带凭证（cookies）

    qps_monitor = QPSMonitor()
    # 创建QPS（每秒请求数）监控器实例
    register_routes(app, qps_monitor)
    # 将所有路由注册到Flask应用中，并传入QPS监控器
    return app
    # 返回配置完成的Flask应用


app = create_app()
# 在模块加载时直接创建Flask应用实例（全局变量）


def main():
    # 定义主启动函数
    
    desired_port = int(os.environ.get("APP_PORT", "5010"))
    # 从环境变量获取用户指定的端口号，默认为5010
    port = choose_port(desired_port)
    # 调用choose_port自动选择一个可用端口（如果首选端口被占用，会尝试递增的端口号）

    logger.info("=" * 60)
    # 输出分隔线日志
    logger.info("RAG 对话系统启动中")
    # 输出启动提示日志
    logger.info("=" * 60)
    # 输出分隔线日志

    init_thread = threading.Thread(target=init_system, daemon=True)
    # 创建后台守护线程，用于异步初始化RAG系统（不会阻塞主线程）
    init_thread.start()
    # 启动初始化线程

    if port != desired_port:
        # 如果实际使用的端口与用户指定的不同
        logger.warning("端口 %s 已被占用，自动切换到 %s", desired_port, port)
        # 输出警告日志，提示端口切换

    logger.info("服务地址: http://localhost:%s", port)
    # 输出服务访问地址
    logger.info("聊天页面: http://localhost:%s/chat", port)
    # 输出聊天页面地址
    logger.info("QPS 面板: http://localhost:%s/qps", port)
    # 输出QPS监控面板地址
    logger.info("性能测试: http://localhost:%s/performance", port)
    # 输出性能测试页面地址
    logger.info("压力测试: http://localhost:%s/stress", port)
    # 输出压力测试页面地址
    logger.info("混合检索: http://localhost:%s/retrieval", port)
    # 输出混合检索调试页面地址
    logger.info("负载均衡: http://localhost:%s/load-balancer", port)
    # 输出负载均衡状态页面地址
    logger.info("综合测试: http://localhost:%s/combined-test", port)
    # 输出综合测试页面地址
    logger.info("=" * 60)
    # 输出分隔线日志

    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True)
    # 启动Flask开发服务器：
    # host="0.0.0.0" 监听所有网络接口
    # debug=False 关闭调试模式
    # use_reloader=False 关闭自动重启
    # threaded=True 启用多线程处理请求


if __name__ == "__main__":
    # 判断是否直接运行此脚本（而不是被import）
    main()
    # 如果是直接运行，调用主启动函数
