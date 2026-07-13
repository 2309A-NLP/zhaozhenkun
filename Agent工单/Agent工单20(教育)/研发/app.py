# 工单20：本文件用于创建 Flask 应用并加载面试AI复盘路由。
# 工单20：导入Flask框架。
from flask import Flask  # 工单20：代码语句。
# 工单20：导入配置加载函数。
from config import load_settings  # 工单20：代码语句。
# 工单20：导入路由注册函数。
from routes import create_web_blueprint  # 工单20：代码语句。

# 工单20：定义应用工厂函数。
def create_app(settings_override: dict | None = None) -> Flask:  # 工单20：代码语句。
    # 工单20：加载项目配置。
    settings = load_settings()  # 工单20：代码语句。
    # 工单20：按需覆盖测试或运行时配置。
    if settings_override:  # 工单20：代码语句。
        settings.update(settings_override)  # 工单20：代码语句。
    # 工单20：创建Flask应用实例。
    app = Flask(__name__, template_folder="templates", static_folder="static")  # 工单20：代码语句。
    # 工单20：写入Flask配置。
    app.config.update(settings)  # 工单20：代码语句。
    # 工单20：注册页面与接口蓝图。
    app.register_blueprint(create_web_blueprint(settings))  # 工单20：代码语句。
    # 工单20：返回应用实例。
    return app  # 工单20：代码语句。

# 工单20：创建默认应用对象。
app = create_app()  # 工单20：代码语句。

# 工单20：定义直接运行入口。
if __name__ == "__main__":  # 工单20：代码语句。
    # 工单20：读取运行参数。
    host = app.config.get("host", "127.0.0.1")  # 工单20：代码语句。
    # 工单20：读取端口参数。
    port = app.config.get("port", 5020)  # 工单20：代码语句。
    # 工单20：读取调试参数。
    debug = app.config.get("debug", True)  # 工单20：代码语句。
    # 工单20：启动开发服务器。
    app.run(host=host, port=port, debug=debug)  # 工单20：代码语句。
