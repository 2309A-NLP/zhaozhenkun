"""工单18：Flask + SocketIO 应用工厂，负责实时通信与Web服务。"""
from flask import Flask
from flask_socketio import SocketIO
from pathlib import Path

from config.settings import load_settings
from routes.api_routes import register_api_routes
from routes.socket_routes import register_socket_events

socketio = SocketIO(cors_allowed_origins="*", async_mode="threading", ping_timeout=30, ping_interval=15)

def create_app() -> Flask:
    base_dir = Path(__file__).resolve().parent
    app = Flask(
        __name__,
        template_folder=str(base_dir / "web" / "templates"),
        static_folder=str(base_dir / "web" / "static"),
    )
    app.config.update(load_settings())
    # 工单18：强制禁用所有缓存
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    app.jinja_env.auto_reload = True

    # 工单18：每个响应添加禁止缓存头
    @app.after_request
    def no_cache(response):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    socketio.init_app(app)
    register_api_routes(app)
    register_socket_events(socketio, app)
    return app
