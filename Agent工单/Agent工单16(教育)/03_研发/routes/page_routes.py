# -*- coding: utf-8 -*-  # 指定源码使用 UTF-8 编码。
"""page_routes.py - 教育 Agent 的页面路由注册模块。"""  # 说明当前文件职责。

from flask import render_template  # 导入模板渲染函数。

from models.schemas import DEFAULT_METRICS  # 导入默认指标卡配置。
from models.schemas import SCENE_CONFIGS  # 导入场景卡片配置。


def register_page_routes(app):  # 注册全部页面访问路由。
    @app.get("/")  # 注册首页访问路由。
    def index():  # 渲染教育 Agent 主工作台页面。
        orchestrator = app.extensions["agent_orchestrator"]  # 读取核心编排服务实例。
        context = orchestrator.get_context()  # 读取页面初始化上下文数据。
        return render_template(  # 渲染并返回首页模板。
            "index.html",  # 指定首页模板文件。
            app_name=app.config["APP_NAME"],  # 注入应用名称。
            scenes=SCENE_CONFIGS,  # 注入场景卡片数据。
            metrics=DEFAULT_METRICS,  # 注入指标卡数据。
            courses=context["courses"],  # 注入课程列表数据。
            students=context["students"],  # 注入学生列表数据。
            model_status=context["model_status"],  # 注入模型状态数据。
            default_model_provider=app.config["DEFAULT_MODEL_PROVIDER"],  # 注入默认模型服务商。
        )  # 完成模板渲染与返回。
