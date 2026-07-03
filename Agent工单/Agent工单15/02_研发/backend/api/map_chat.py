"""
================================================================================
文件名:   api/map_chat.py
功能:     地图自然语言对话端点（Agent 智能体核心入口）
          —— DeepSeek 意图解析 → 高德 API 调用 → DeepSeek 回复整理
所属项目:  医疗智能体-影像分析系统
工单编号:  人工智能 NLP-Agent 数字人项目-医疗智能体-MCP V1.0
调用方:    main.py（FastAPI 应用注册）
           frontend/js/map.js（前端 AJAX 调用）
依赖:      services/amap_client.py（高德地图 API 客户端）
          services/llm_client.py（DeepSeek 文本推理 - 意图解析 + 回复整理）
          api/map_format.py（API 结果格式化工具函数）

核心流程:
  用户输入 "北京协和医院附近有什么酒店？"
    → Step 1: DeepSeek 解析意图 → {"action":"nearby","location":"...","poi_type":"100000"}
    → Step 2: 调用高德地图 API 获取原始数据
    → Step 3: DeepSeek 将原始数据整理成友好的自然语言回复
================================================================================
"""
import re         # re.search —— 正则匹配，从 LLM 回复中提取 JSON
import json       # json.loads —— 解析 LLM 返回的 JSON 字符串
import logging    # logging.getLogger —— 模块级别日志
from fastapi import APIRouter                         # FastAPI 路由器（用于组织 API 端点）
from fastapi.responses import JSONResponse            # JSONResponse —— 统一返回 JSON 格式
from pydantic import BaseModel, Field                 # Pydantic 数据校验模型
from services.amap_client import get_amap_client      # 高德地图客户端单例
from services.llm_client import get_deepseek_client   # DeepSeek 文本推理客户端单例

# 从同包的格式化模块导入工具函数
from api.map_format import fmt_for_prompt

# 创建本模块的 logger
_log = logging.getLogger("medical_agent.map_chat")

# 创建 FastAPI 路由实例
router = APIRouter(tags=["地图服务（高德地图 MCP 对接）"])  # 前缀由 include_router 统一管理


# ================================================================
# 请求模型 —— Pydantic BaseModel，FastAPI 自动校验和文档生成
# ================================================================
class MapChatRequest(BaseModel):
    """地图自然语言对话请求体 — Agent 智能体核心入口"""
    message: str = Field(..., min_length=1, max_length=2000,
                         description="自然语言查询，如'北京协和医院附近的酒店'")


# ================================================================
# DeepSeek 地图意图解析 System Prompt
# 告诉 LLM 如何从自然语言中提取结构化参数
# ================================================================
MAP_SYSTEM = """你是一个地图服务意图解析器，从用户消息中提取 JSON 参数，调用对应的高德地图功能。

可用功能:
1. search - 搜索地点（医院、酒店、餐厅）
   参数: {"action":"search", "keywords":"三甲医院", "city":"北京"}

2. nearby - 搜索周边（某地点附近的设施）
   参数: {"action":"nearby", "location":"116.397,39.909", "keywords":"酒店", "poi_type":"100000", "radius":3000}

3. directions - 路线规划（从A到B怎么走）
   参数: {"action":"directions", "origin_name":"天安门", "dest_name":"协和医院", "mode":"driving"}
   mode: driving(驾车)/walking(步行)/transit(公交)

4. weather - 天气查询
   参数: {"action":"weather", "city":"北京"}

5. hospital_services - 医院周边一站式查询
   参数: {"action":"hospital_services", "hospital_name":"协和医院", "city":"北京"}

只返回 JSON 对象，不要任何其他内容。"""


# ================================================================
# 端点: POST /api/map/chat —— 地图自然语言对话 ★核心入口★
# 这是 Agent 智能体的核心能力：理解自然语言、调用工具、整理回复
# ================================================================
@router.post("/chat")
async def map_chat(req: MapChatRequest):
    """
    地图服务自然语言对话 —— Agent 智能体核心入口

    完整流程（三步走）:
      Step 1. DeepSeek 解析用户意图 → 提取结构化参数（action + 参数）
      Step 2. 根据意图调用对应的高德地图 API
      Step 3. DeepSeek 将原始 API 结果整理成友好的自然语言回复

    示例:
      用户: "北京协和医院附近的酒店"
      → Step1: {"action":"nearby", ...}
      → Step2: 调用 amap.search_around(...)
      → Step3: "为您找到协和医院附近5家酒店：..."
    """
    # 获取两个客户端单例
    ds = get_deepseek_client()   # DeepSeek 文本推理（意图解析 + 回复整理）
    amap = get_amap_client()     # 高德地图 API（数据查询）

    # ================================================================
    # Step 1: 意图解析 —— 让 LLM 理解用户想做什么
    # ================================================================
    parse_r = ds.chat(
        [{"role": "user", "content": req.message}],  # 用户原始消息
        system=MAP_SYSTEM,                            # 地图意图解析专用 Prompt
        max_tokens=300                                # 意图只需少量 token
    )
    intent_raw = parse_r.get("content", "{}")         # LLM 返回的原始文本（应该是 JSON）
    _log.info("地图意图解析: %s → %s", req.message[:50], intent_raw[:150])  # 日志记录

    # ① 从 LLM 回复中提取 JSON（可能被包裹在 markdown 代码块中）
    m = re.search(r'\{[^{}]*\}', intent_raw)          # 正则匹配第一个 JSON 对象
    intent = {}
    if m:
        try:
            intent = json.loads(m.group())            # 解析 JSON 字符串为 dict
        except json.JSONDecodeError:
            pass  # 解析失败则用空 dict，后续走 fallback 逻辑

    # ② 获取意图类型（action 字段），默认为 search
    action = intent.get("action", "search")
    api_result = {"success": False, "error": "无法识别意图"}  # 兜底错误

    # ================================================================
    # Step 2: 调用高德地图 API —— 根据意图分发到不同的方法
    # ================================================================
    try:
        if action == "search":
            # 关键词搜索地点
            api_result = amap.search_poi(
                intent.get("keywords", req.message),  # 关键词（兜底用原始消息）
                city=intent.get("city", ""),          # 城市
                poi_type=intent.get("poi_type", "")   # POI 类型
            )

        elif action == "nearby":
            # 周边 POI 搜索
            api_result = amap.search_around(
                intent.get("location", ""),           # 中心坐标（必填）
                keywords=intent.get("keywords", ""),  # 关键词
                poi_type=intent.get("poi_type", ""),  # POI 类型
                radius=intent.get("radius", 3000)     # 搜索半径
            )

        elif action == "directions":
            # 路线规划 —— 需要先解析起点/终点名称为坐标
            origin_name = intent.get("origin_name", "")  # 起点名称（用户口语描述）
            dest_name = intent.get("dest_name", "")      # 终点名称
            origin_loc = intent.get("origin", "")        # 起点坐标（如果已提供）
            dest_loc = intent.get("destination", "")     # 终点坐标（如果已提供）

            # 如果用户给的是名称而非坐标，调用地理编码转换
            if origin_name and not origin_loc:
                geo = amap.geocode(origin_name)           # 起点名称→坐标
                origin_loc = geo.get("location", "") if geo.get("success") else ""
            if dest_name and not dest_loc:
                geo = amap.geocode(dest_name)             # 终点名称→坐标
                dest_loc = geo.get("location", "") if geo.get("success") else ""

            # 坐标都有了，执行路线规划
            if origin_loc and dest_loc:
                mode = intent.get("mode", "driving")      # 出行方式
                if mode == "walking":
                    api_result = amap.direction_walking(origin_loc, dest_loc)
                elif mode == "transit":
                    api_result = amap.direction_transit(origin_loc, dest_loc)
                else:
                    api_result = amap.direction_driving(origin_loc, dest_loc)
            else:
                api_result = {"success": False,
                             "error": "无法定位起点或终点"}  # 坐标解析失败

        elif action == "weather":
            # 天气查询
            api_result = amap.weather(intent.get("city", "北京"))

        elif action == "hospital_services":
            # 医院周边一站式查询
            api_result = amap.search_hospital_with_services(
                intent.get("hospital_name", req.message),  # 医院名称
                city=intent.get("city", "")                  # 城市
            )

    except Exception as e:
        # API 调用异常兜底
        api_result = {"success": False, "error": str(e)}

    # ================================================================
    # Step 3: DeepSeek 整理回复 —— 将原始 API 数据转为友好的自然语言
    # ================================================================
    if api_result.get("success"):
        # 成功：让 LLM 整理 API 返回的原始数据
        summary_prompt = f"""你是智能出行助手。用户原始问题: {req.message}
高德地图返回了以下结果（已精简关键信息），请用友好的中文整理回复。
要求：
- 简洁清晰，突出重点（名称/地址/距离/评分）
- 如果有多条结果，分类展示（如出行路线、附近住宿、附近餐饮）
- 如果是路线，说明大致时间和距离
- 结尾加上温馨提示（仅供参考）

API结果:
{fmt_for_prompt(api_result)}"""
    else:
        # 失败：让 LLM 友好地告知用户
        summary_prompt = f"""用户查询"{req.message}"时出错: {api_result.get('error','未知')}
请友好地告知用户，并建议尝试其他方式。"""

    # 调用 DeepSeek 生成最终回复
    summary_r = ds.chat(
        [{"role": "user", "content": summary_prompt}],
        system="你是智能出行助手，专业、简洁、友好。",
        max_tokens=800
    )

    # 返回完整的对话结果
    return JSONResponse({
        "success": api_result.get("success", False),     # 是否成功
        "reply": summary_r.get("content", "服务暂时不可用"),  # LLM 整理的友好回复
        "intent": intent,                                 # 解析出的意图（调试用）
        "api_result": api_result if isinstance(api_result, dict) else {},  # 原始 API 结果
        "latency_ms": (parse_r.get("latency_ms", 0) +     # 总耗时 = 意图解析 + API 调用
                       api_result.get("latency_ms", 0)),
        "model": summary_r.get("model", ""),              # 使用的 LLM 模型名
    })
