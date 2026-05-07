# -*- coding: utf-8 -*-
"""
RAG 对话系统主入口。

只负责：
1. 创建 Flask app
2. 注册路由
3. 异步初始化系统
4. 启动服务
"""

import logging
import os
import threading
from datetime import timedelta

from flask import Flask

try:
    from flask_cors import CORS
except Exception:
    def CORS(*args, **kwargs):
        return None

from app_monitor import QPSMonitor, choose_port
from app_routes import register_routes
from app_services import init_system
from config import SECRET_KEY, SESSION_TIMEOUT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__, template_folder="templates")
    app.secret_key = SECRET_KEY
    app.config.update(
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(seconds=SESSION_TIMEOUT),
        JSON_AS_ASCII=False, 
    )
    CORS(app, supports_credentials=True)

    qps_monitor = QPSMonitor()
    register_routes(app, qps_monitor)
    return app


app = create_app()


def main():
    desired_port = int(os.environ.get("APP_PORT", "5010"))
    port = choose_port(desired_port)

    logger.info("=" * 60)
    logger.info("RAG 对话系统启动中")
    logger.info("=" * 60)

    init_thread = threading.Thread(target=init_system, daemon=True)
    init_thread.start()

    if port != desired_port:
        logger.warning("端口 %s 已被占用，自动切换到 %s", desired_port, port)

    logger.info("服务地址: http://localhost:%s", port)
    logger.info("聊天页面: http://localhost:%s/chat", port)
    logger.info("QPS 面板: http://localhost:%s/qps", port)
    logger.info("性能测试: http://localhost:%s/performance", port)
    logger.info("压力测试: http://localhost:%s/stress", port)
    logger.info("混合检索: http://localhost:%s/retrieval", port)
    logger.info("负载均衡: http://localhost:%s/load-balancer", port)
    logger.info("=" * 60)

    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
