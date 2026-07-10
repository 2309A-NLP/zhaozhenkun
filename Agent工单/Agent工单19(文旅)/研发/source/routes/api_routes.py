# -*- coding: utf-8 -*-  # 指定源码编码。
# 工单编号：人工智能CV-AIGC-19-文旅Agent任务工单-创意策划与内容生成V1.1-20260306  # 标记工单来源。
"""api_routes.py - 文旅策划、纪念内容、导出下载接口路由模块。"""  # 说明当前文件职责。

import json  # 导入 JSON 处理模块。
from urllib import error  # 导入请求异常模块。
from urllib import request as urlrequest  # 导入 HTTP 请求模块。
from urllib.parse import quote  # 导入文件名编码函数。

from flask import Blueprint  # 导入蓝图工具。
from flask import current_app  # 导入当前应用对象。
from flask import make_response  # 导入响应对象构造函数。
from flask import request  # 导入请求对象。

from services.content_service import generate_content_package  # 导入内容生成函数。
from services.content_service import generate_recommendation_package  # 导入推荐生成函数。
from services.export_service import build_download_filename  # 导入下载文件名生成函数。
from services.export_service import build_markdown_pack  # 导入方案包构造函数。
from services.export_service import generate_flowchart  # 导入流程图导出函数。
from services.export_service import generate_ppt_outline  # 导入 PPT 大纲导出函数。
from services.knowledge_service import list_regions_and_spots  # 导入地区景点列表函数。
from services.knowledge_service import load_knowledge_service  # 导入知识服务加载函数。
from services.memorial_service import generate_memorial_package  # 导入纪念内容生成函数。
from services.planner_service import build_brief  # 导入 brief 构造函数。
from services.planner_service import generate_plan_outline  # 导入策划结果生成函数。
from services.response_service import error_response  # 导入错误响应函数。
from services.response_service import ok_response  # 导入成功响应函数。
from services.session_service import append_message  # 导入消息追加函数。
from services.session_service import create_session  # 导入会话创建函数。
from services.session_service import get_session_snapshot  # 导入会话快照函数。


api_bp = Blueprint("api_bp", __name__, url_prefix="/api")  # 创建 API 蓝图。


def _payload() -> dict:  # 统一获取请求数据。
    return request.get_json(silent=True) or {}  # 返回 JSON 数据或空字典。


def _knowledge(config: dict, brief: dict) -> list:  # 基于 brief 获取知识增强结果。
    service = load_knowledge_service(config["KNOWLEDGE_PATH"])  # 读取知识服务实例。
    query = f"{brief['region']} {brief['city']} {brief['spot']} {brief['theme']} {brief['keywords']}"  # 组合查询语句。
    return service.search(query, top_k=3)  # 返回前三条知识结果。


def _build_full_pack(data: dict) -> tuple:  # 统一构造完整方案包所需的全部结果。
    brief = build_brief(data, current_app.config)  # 构造标准 brief。
    knowledge = _knowledge(current_app.config, brief)  # 执行知识增强。
    plan_result = generate_plan_outline(brief, knowledge)  # 生成策划结果。
    content_result = generate_content_package(brief, knowledge)  # 生成传播内容结果。
    recommend_result = generate_recommendation_package(brief, knowledge)  # 生成路线推荐结果。
    memorial_result = generate_memorial_package(brief, knowledge)  # 生成纪念内容结果。
    flowchart_result = generate_flowchart(plan_result)  # 生成流程图结果。
    return brief, plan_result, content_result, recommend_result, memorial_result, flowchart_result  # 返回完整结果组。


@api_bp.get("/health")  # 注册健康检查接口。
def health():  # 返回服务健康状态。
    return ok_response({"service": current_app.config["APP_TITLE"]}, "alive")  # 返回健康结果。


@api_bp.post("/session/create")  # 注册创建会话接口。
def create_session_api():  # 创建并返回新会话。
    return ok_response(create_session(), "session created")  # 返回会话结果。


@api_bp.get("/spots/options")  # 注册地区景点选项接口。
def list_spot_options_api():  # 返回前端所需的地区景点数据。
    options = list_regions_and_spots(current_app.config["KNOWLEDGE_PATH"])  # 读取地区景点映射。
    return ok_response(options, "spot options")  # 返回选项结果。


@api_bp.get("/location/ip")  # 注册服务端 IP 定位接口（绕开浏览器 Geolocation API）。
def ip_location_api():  # 通过高德 IP 定位 API 获取城市级坐标。
    try:  # 开始调用高德 IP 定位服务。
        amap_key = current_app.config.get("AMAP_WEB_KEY", "")  # 读取高德 Web Key。
        ip_url = f"https://restapi.amap.com/v3/ip?key={amap_key}&output=JSON"  # 组装 IP 定位请求地址。
        req = urlrequest.Request(ip_url)  # 创建 HTTP 请求对象。
        with urlrequest.urlopen(req, timeout=5) as resp:  # 发起请求并设置 5 秒超时。
            body = json.loads(resp.read().decode("utf-8"))  # 读取并解析响应 JSON。
        if body.get("status") == "1" and body.get("rectangle"):  # 当 API 返回成功且包含矩形坐标时。
            rect = body["rectangle"]  # 格式："左下经度,左下纬度;右上经度,右上纬度"。
            parts = rect.split(";")  # 按分号拆分左右下角。
            if len(parts) == 2:  # 确认包含两组坐标。
                left_bottom = [float(v) for v in parts[0].split(",")]  # 解析左下角坐标。
                right_top = [float(v) for v in parts[1].split(",")]  # 解析右上角坐标。
                center_lng = round((left_bottom[0] + right_top[0]) / 2, 6)  # 计算矩形中心经度。
                center_lat = round((left_bottom[1] + right_top[1]) / 2, 6)  # 计算矩形中心纬度。
                return ok_response({  # 返回 IP 定位成功结果。
                    "longitude": center_lng,  # 返回中心经度。
                    "latitude": center_lat,  # 返回中心纬度。
                    "province": body.get("province", ""),  # 返回省份（中文）。
                    "city": body.get("city", ""),  # 返回城市（中文）。
                    "adcode": body.get("adcode", ""),  # 返回行政区划代码。
                    "source": "amap-ip",  # 标记定位来源。
                }, "ip location success")  # 完成成功响应。
    except Exception:  # 捕获所有异常（网络、解析等）。
        pass  # IP 定位失败时静默处理，由前端回退到其他方式。
    return error_response("ip location failed", 502)  # 返回定位失败响应。

@api_bp.post("/plan/generate")  # 注册策划生成接口。
def generate_plan_api():  # 生成结构化策划方案。
    data = _payload()  # 获取请求体。
    brief = build_brief(data, current_app.config)  # 构造标准 brief。
    session_id = str(data.get("session_id", "")).strip()  # 读取会话编号。
    knowledge = _knowledge(current_app.config, brief)  # 执行知识增强。
    result = generate_plan_outline(brief, knowledge)  # 生成策划结果。
    append_message(session_id, "user", f"策划需求：{brief['theme']}")  # 记录用户策划请求。
    append_message(session_id, "assistant", result["positioning"])  # 记录系统策划结果摘要。
    return ok_response(result, "plan generated")  # 返回策划结果。


@api_bp.post("/content/generate")  # 注册内容生成接口。
def generate_content_api():  # 生成传播内容。
    data = _payload()  # 获取请求体。
    brief = build_brief(data, current_app.config)  # 构造标准 brief。
    knowledge = _knowledge(current_app.config, brief)  # 执行知识增强。
    result = generate_content_package(brief, knowledge)  # 生成内容传播包。
    return ok_response(result, "content generated")  # 返回内容结果。


@api_bp.post("/recommend/generate")  # 注册推荐生成接口。
def generate_recommend_api():  # 生成路线与体验推荐。
    data = _payload()  # 获取请求体。
    brief = build_brief(data, current_app.config)  # 构造标准 brief。
    knowledge = _knowledge(current_app.config, brief)  # 执行知识增强。
    result = generate_recommendation_package(brief, knowledge)  # 生成推荐结果。
    return ok_response(result, "recommendation generated")  # 返回推荐结果。


@api_bp.post("/memorial/generate")  # 注册纪念内容生成接口。
def generate_memorial_api():  # 生成人旅纪念内容。
    data = _payload()  # 获取请求体。
    brief = build_brief(data, current_app.config)  # 构造标准 brief。
    knowledge = _knowledge(current_app.config, brief)  # 执行知识增强。
    result = generate_memorial_package(brief, knowledge)  # 生成纪念内容结果。
    return ok_response(result, "memorial generated")  # 返回纪念内容结果。


@api_bp.post("/export/ppt-outline")  # 注册 PPT 大纲导出接口。
def export_ppt_api():  # 导出 PPT 大纲。
    data = _payload()  # 获取请求体。
    brief = build_brief(data, current_app.config)  # 构造标准 brief。
    knowledge = _knowledge(current_app.config, brief)  # 执行知识增强。
    plan_result = generate_plan_outline(brief, knowledge)  # 生成策划结果。
    content_result = generate_content_package(brief, knowledge)  # 生成内容结果。
    return ok_response(generate_ppt_outline(plan_result, content_result), "ppt outline generated")  # 返回 PPT 大纲。


@api_bp.post("/export/flowchart")  # 注册流程图导出接口。
def export_flowchart_api():  # 导出 Mermaid 流程图。
    data = _payload()  # 获取请求体。
    brief = build_brief(data, current_app.config)  # 构造标准 brief。
    knowledge = _knowledge(current_app.config, brief)  # 执行知识增强。
    plan_result = generate_plan_outline(brief, knowledge)  # 生成策划结果。
    return ok_response(generate_flowchart(plan_result), "flowchart generated")  # 返回流程图结果。


@api_bp.post("/export/markdown-pack")  # 注册方案包下载接口。
def export_markdown_pack_api():  # 导出 Markdown 完整方案包。
    data = _payload()  # 获取请求体。
    brief, plan_result, content_result, recommend_result, memorial_result, flowchart_result = _build_full_pack(data)  # 生成完整结果组。
    markdown_text = build_markdown_pack(brief, plan_result, content_result, recommend_result, memorial_result, flowchart_result)  # 生成完整方案包文本。
    response = make_response(markdown_text)  # 构造下载响应。
    response.headers["Content-Type"] = "text/markdown; charset=utf-8"  # 设置响应内容类型。
    encoded_name = quote(build_download_filename(brief))  # 对下载文件名执行 URL 编码。
    response.headers["Content-Disposition"] = f"attachment; filename=plan-pack.md; filename*=UTF-8''{encoded_name}"  # 设置兼容性的下载文件名。
    return response  # 返回下载响应。


@api_bp.get("/session/<session_id>")  # 注册会话快照接口。
def session_snapshot_api(session_id: str):  # 返回指定会话快照。
    if not session_id.strip():  # 当会话编号为空时返回错误。
        return error_response("session_id 不能为空", 400)  # 返回错误响应。
    return ok_response(get_session_snapshot(session_id), "session snapshot")  # 返回会话快照。


def register_api_routes(app):  # 把 API 蓝图注册到应用。
    app.register_blueprint(api_bp)  # 执行蓝图注册。
