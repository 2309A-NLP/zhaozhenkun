# -*- coding: utf-8 -*-  # 指定源码编码。
# 工单编号：人工智能CV-AIGC-19-文旅Agent任务工单-创意策划与内容生成V1.1-20260306  # 标记工单来源。
"""page_routes.py - 项目页面路由注册模块。"""  # 说明当前文件职责。

from flask import Blueprint  # 导入蓝图工具。
from flask import current_app  # 导入当前应用对象。
from flask import render_template  # 导入模板渲染函数。


page_bp = Blueprint("page_bp", __name__)  # 创建页面蓝图。


@page_bp.get("/")  # 注册首页路由。
def index():  # 返回系统主页面。
    return render_template(  # 渲染首页模板。
        "index.html",  # 指定模板名称。
        amap_web_key=current_app.config.get("AMAP_WEB_KEY", ""),  # 注入高德地图 Web Key。
        amap_security_code=current_app.config.get("AMAP_SECURITY_CODE", ""),  # 注入高德地图安全密钥。
    )  # 返回模板响应。


def register_page_routes(app):  # 把页面蓝图注册到应用。
    app.register_blueprint(page_bp)  # 执行蓝图注册。
