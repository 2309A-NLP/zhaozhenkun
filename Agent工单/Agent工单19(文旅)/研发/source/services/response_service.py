# -*- coding: utf-8 -*-  # 指定源码编码。
# 工单编号：人工智能CV-AIGC-19-文旅Agent任务工单-创意策划与内容生成V1.1-20260306  # 标记工单来源。
"""response_service.py - 统一接口响应结构模块。"""  # 说明当前文件职责。

from flask import jsonify  # 导入 JSON 响应函数。


def ok_response(data=None, message: str = "success", status: int = 200):  # 构造成功响应。
    body = {  # 初始化响应体。
        "ok": True,  # 标记当前请求成功。
        "message": message,  # 写入成功消息。
        "data": data or {},  # 写入业务数据。
    }  # 响应体构造结束。
    return jsonify(body), status  # 返回 JSON 响应与状态码。


def error_response(message: str, status: int = 400, extra=None):  # 构造失败响应。
    body = {  # 初始化错误响应体。
        "ok": False,  # 标记当前请求失败。
        "message": message,  # 写入失败消息。
        "data": extra or {},  # 写入扩展错误信息。
    }  # 错误响应体构造结束。
    return jsonify(body), status  # 返回 JSON 响应与状态码。
