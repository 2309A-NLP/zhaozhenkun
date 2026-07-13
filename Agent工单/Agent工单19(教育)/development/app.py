"""工单19：教育智能体个性化学习推荐项目的 Flask 应用工厂。"""

# 工单19：导入 Flask 框架。
from flask import Flask

# 工单19：导入项目调试配置。
from development.config import DEBUG

# 工单19：导入数据库初始化逻辑。
from development.database import initialize_database

# 工单19：导入 Web 路由蓝图。
from development.routes.web import web_blueprint


# 工单19：创建并配置 Flask 应用。
def create_app():
    initialize_database()
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["JSON_AS_ASCII"] = False
    app.config["TEMPLATES_AUTO_RELOAD"] = DEBUG
    app.register_blueprint(web_blueprint)
    return app
