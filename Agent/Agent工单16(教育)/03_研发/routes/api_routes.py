# -*- coding: utf-8 -*-  # 指定源码使用 UTF-8 编码。
"""api_routes.py - 教育 Agent 的接口路由注册模块。"""  # 说明当前文件职责。

from flask import jsonify  # 导入 JSON 响应函数。
from flask import request  # 导入请求对象。


def _read_payload():  # 从请求中统一读取表单或 JSON 数据。
    if request.is_json:  # 当当前请求是 JSON 格式时直接读取 JSON。
        return request.get_json(silent=True) or {}  # 返回请求体中的 JSON 数据。
    return {key: value for key, value in request.form.items()}  # 返回表单字段字典。


def register_api_routes(app):  # 注册全部 API 路由。
    @app.get("/api/health")  # 注册健康检查接口。
    def health():  # 返回应用健康状态摘要。
        orchestrator = app.extensions["agent_orchestrator"]  # 读取核心编排服务实例。
        return jsonify({"success": True, "data": orchestrator.get_context()["model_status"]})  # 返回服务健康结果。

    @app.post("/api/scene/<scene>")  # 注册统一场景执行接口。
    def execute_scene(scene: str):  # 执行指定场景的业务逻辑。
        orchestrator = app.extensions["agent_orchestrator"]  # 读取核心编排服务实例。
        payload = _read_payload()  # 解析请求中的业务参数。
        upload = request.files.get("image")  # 读取可选的上传图片对象。
        try:  # 开始执行业务并捕获可预期错误。
            result = orchestrator.execute_scene(scene, payload, upload)  # 调用主编排器执行场景。
            return jsonify({"success": True, "data": result})  # 返回成功业务结果。
        except Exception as exc:  # 当业务执行失败时返回错误结果。
            return jsonify({"success": False, "message": str(exc)}), 400  # 返回统一错误响应。
