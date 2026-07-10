"""工单18：统一启动入口 — SocketIO 实时通信 + Flask Web 服务。"""
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PROJECT_ROOT / "研发" / "source"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from app import create_app, socketio

app = create_app()

if __name__ == "__main__":
    # 工单18：allow_unsafe_werkzeug=True 允许开发环境使用 Flask 自带服务器
    socketio.run(
        app,
        host=app.config["APP_HOST"],
        port=app.config["APP_PORT"],
        debug=False,
        allow_unsafe_werkzeug=True,
    )
