# -*- coding: utf-8 -*-  # 指定源码编码。
# 工单编号：人工智能CV-AIGC-19-文旅Agent任务工单-创意策划与内容生成V1.1-20260306  # 标记工单来源。
"""app.py - Flask 应用工厂与启动入口。"""  # 说明当前文件职责。

from pathlib import Path  # 导入路径处理工具。
from flask import Flask  # 导入 Flask 核心类。


from config.settings import load_settings  # 导入配置加载函数。
from routes.api_routes import register_api_routes  # 导入接口路由注册函数。
from routes.page_routes import register_page_routes  # 导入页面路由注册函数。


def create_app() -> Flask:  # 创建并返回 Flask 应用。
    base_dir = Path(__file__).resolve().parent  # 获取当前源码根目录。
    app = Flask(  # 初始化 Flask 应用。
        __name__,  # 传入当前模块名称。
        template_folder=str(base_dir / "web" / "templates"),  # 指定模板目录。
        static_folder=str(base_dir / "web" / "static"),  # 指定静态资源目录。
    )  # 完成应用初始化。
    app.config.update(load_settings())  # 加载并写入项目配置。
    app.config["JSON_AS_ASCII"] = False  # 允许 JSON 正常输出中文。
    app.config["TEMPLATES_AUTO_RELOAD"] = True  # 开启模板自动重载。
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0  # 关闭静态资源缓存。
    register_page_routes(app)  # 注册页面路由。
    register_api_routes(app)  # 注册接口路由。

    @app.after_request  # 为每个响应追加无缓存头。
    def apply_no_cache(response):  # 定义响应后处理函数。
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"  # 禁止缓存。
        response.headers["Pragma"] = "no-cache"  # 兼容旧式缓存控制。
        response.headers["Expires"] = "0"  # 声明立即过期。
        return response  # 返回处理后的响应对象。

    return app  # 返回应用实例。


app = create_app()  # 创建可供 WSGI 直接使用的应用对象。



if __name__ == "__main__":  # 当脚本被直接执行时启动开发服务。
    app.run(  # 启动 Flask 内置开发服务器。
        host=app.config["HOST"],  # 使用配置中的监听地址。
        port=app.config["PORT"],  # 使用配置中的监听端口。
        debug=app.config["DEBUG"],  # 使用配置中的调试开关。
    )  # 完成服务启动。
