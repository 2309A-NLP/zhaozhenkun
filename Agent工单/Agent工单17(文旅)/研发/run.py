# 这里定义项目统一启动入口。
from app import create_app
from config.settings import FLASK_PORT


if __name__ == "__main__":
    # 这里创建 Flask 应用实例。
    app = create_app()
    # 这里启动开发服务器。
    app.run(host="127.0.0.1", port=FLASK_PORT, debug=True)
