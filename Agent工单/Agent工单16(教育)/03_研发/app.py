# -*- coding: utf-8 -*-  # 指定源码使用 UTF-8 编码。
"""app.py - 教育 Agent Web 应用工厂与启动入口。"""  # 说明当前文件职责。

from pathlib import Path  # 导入路径处理工具。
from flask import Flask  # 导入 Flask 核心类。

from config import load_settings  # 导入配置加载函数。
from routes.api_routes import register_api_routes  # 导入接口路由注册函数。
from routes.page_routes import register_page_routes  # 导入页面路由注册函数。
from services.agent_orchestrator import AgentOrchestrator  # 导入核心编排服务。


def create_app() -> Flask:  # 创建并返回 Flask 应用实例。
    base_dir = Path(__file__).resolve().parent  # 获取研发目录绝对路径。
    settings = load_settings()  # 加载应用运行配置。
    Path(settings["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)  # 确保上传目录存在。
    app = Flask(  # 初始化 Flask 应用对象。
        __name__,  # 传入当前模块名称。
        template_folder=str(base_dir / "web" / "templates"),  # 指定模板目录。
        static_folder=str(base_dir / "web" / "static"),  # 指定静态资源目录。
    )  # 完成 Flask 应用初始化。
    app.config.update(settings)  # 写入基础配置字典。
    app.config["JSON_AS_ASCII"] = False  # 允许 JSON 正常返回中文。
    app.config["MAX_CONTENT_LENGTH"] = settings["MAX_UPLOAD_MB"] * 1024 * 1024  # 设置上传总大小限制。
    app.extensions["agent_orchestrator"] = AgentOrchestrator(settings)  # 挂载核心编排服务实例。
    register_page_routes(app)  # 注册页面访问路由。
    register_api_routes(app)  # 注册数据接口路由。

    @app.after_request  # 在每次响应后附加无缓存响应头。
    def apply_no_cache(response):  # 定义响应后处理函数。
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"  # 禁止缓存。
        response.headers["Pragma"] = "no-cache"  # 兼容旧式代理缓存控制。
        response.headers["Expires"] = "0"  # 设置资源立即过期。
        return response  # 返回修改后的响应对象。

    return app  # 返回创建好的应用实例。


app = create_app()  # 创建默认可运行应用实例。


if __name__ == "__main__":  # 当脚本被直接执行时启动开发服务。
    app.run(  # 启动 Flask 开发服务器。
        host=app.config["HOST"],  # 使用配置中的监听地址。
        port=app.config["PORT"],  # 使用配置中的监听端口。
        debug=app.config["DEBUG"],  # 使用配置中的调试开关。
    )  # 完成服务启动。
