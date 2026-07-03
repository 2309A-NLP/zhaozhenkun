"""
================================================================================
文件名:   api/map.py
功能:     地图服务 API 路由层（FastAPI Router）
          —— 医院位置相关的出行/住宿/餐饮查询 HTTP 端点
          —— 对接高德地图 REST API + DeepSeek 自然语言意图解析
所属项目:  医疗智能体-影像分析系统
工单编号:  人工智能 NLP-Agent 数字人项目-医疗智能体-MCP V1.0
调用方:    main.py（FastAPI 应用注册）
           frontend/js/map.js（前端 AJAX 调用）
依赖:      services/amap_client.py（高德地图 API 客户端）
          services/llm_client.py（DeepSeek 文本推理 - 意图解析 + 回复整理）

路由列表（8 个端点）:
  POST /api/map/search              关键词地点搜索（医院/酒店/餐厅）
  POST /api/map/nearby              周边 POI 搜索（住宿/餐饮/交通）
  POST /api/map/directions          路线规划（驾车/步行/公交）
  POST /api/map/geocode             地址 → 经纬度
  POST /api/map/regeocode           经纬度 → 地址
  POST /api/map/hospital-services   医院周边一站式查询
  POST /api/map/ip-location         IP 定位
  POST /api/map/chat                自然语言对话入口 ★核心★
                                    ┌─ DeepSeek 意图解析
                                    ├─ 高德 API 调用
                                    └─ DeepSeek 回复整理

核心流程（/api/map/chat）:
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

# 创建本模块的 logger
_log = logging.getLogger("medical_agent.map")

# 创建 FastAPI 路由实例
# prefix="/api/map" 表示所有端点都以此路径开头
# tags=["地图服务..."] 用于 Swagger UI 文档分组
router = APIRouter(prefix="/api/map", tags=["地图服务（高德地图 MCP 对接）"])


# ================================================================
# 请求模型 —— Pydantic BaseModel，FastAPI 自动校验和文档生成
# ================================================================
class SearchRequest(BaseModel):
    """地点搜索请求体"""
    keywords: str = Field(..., min_length=1, max_length=100,
                          description="搜索关键词，如'三甲医院'、'酒店'、'川菜'")
    city: str = Field(default="", max_length=50,
                      description="城市名称，如'北京'，空=全国搜索")
    poi_type: str = Field(default="",
                          description="POI类型编码：090000=医疗 100000=住宿 050000=餐饮")
    page: int = Field(default=1, ge=1, le=20, description="页码")
    offset: int = Field(default=10, ge=1, le=25, description="每页条数")


class AroundRequest(BaseModel):
    """周边搜索请求体"""
    location: str = Field(..., description="中心点坐标，格式 '经度,纬度'")
    keywords: str = Field(default="", max_length=100, description="搜索关键词")
    poi_type: str = Field(default="",
                          description="POI类型：050000=餐饮 100000=住宿 150300=公交站 150500=地铁站")
    radius: int = Field(default=3000, ge=100, le=50000,
                        description="搜索半径（米），100~50000")


class DirectionRequest(BaseModel):
    """路线规划请求体"""
    origin: str = Field(..., description="起点坐标 'lng,lat'")
    destination: str = Field(..., description="终点坐标 'lng,lat'")
    mode: str = Field(default="driving",
                      description="出行方式: driving(驾车) walking(步行) transit(公交)")


class GeocodeRequest(BaseModel):
    """地理编码请求体"""
    address: str = Field(..., min_length=1, max_length=200,
                         description="地址文本，如'北京协和医院'")
    city: str = Field(default="", max_length=50, description="城市名（缩小搜索范围）")


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
# 端点 1: POST /api/map/search —— 关键词搜索地点
# ================================================================
@router.post("/search")
async def search_poi(req: SearchRequest):
    """
    关键词地点搜索

    适用场景: "搜索北京市的三甲医院"、"附近有什么酒店？"

    前端调用示例:
      fetch('/api/map/search', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({keywords: '协和医院', city: '北京'})
      })
    """
    # ① 获取高德客户端单例
    amap = get_amap_client()

    # ② 调用底层搜索方法
    result = amap.search_poi(
        req.keywords,        # 搜索关键词（必填）
        city=req.city,       # 城市限定（可选）
        poi_type=req.poi_type,  # POI 类型过滤（可选）
        page=req.page,       # 页码
        offset=req.offset    # 每页条数
    )

    # ③ 返回 JSON（FastAPI + JSONResponse 自动序列化 dict）
    return JSONResponse(result)


# ================================================================
# 端点 2: POST /api/map/nearby —— 周边搜索
# ================================================================
@router.post("/nearby")
async def search_nearby(req: AroundRequest):
    """
    周边 POI 搜索（以指定坐标为中心）

    适用场景: "协和医院附近有什么餐厅？"
    """
    # ① 获取高德客户端
    amap = get_amap_client()

    # ② 调用周边搜索
    result = amap.search_around(
        req.location,          # 中心坐标（必填）
        keywords=req.keywords, # 关键词过滤（可选）
        poi_type=req.poi_type, # POI 类型（可选，推荐使用）
        radius=req.radius      # 搜索半径（米）
    )

    return JSONResponse(result)


# ================================================================
# 端点 3: POST /api/map/directions —— 路线规划
# ================================================================
@router.post("/directions")
async def get_directions(req: DirectionRequest):
    """
    路线规划（驾车/步行/公交）

    适用场景: "从这里去协和医院怎么走？"
    """
    # ① 获取高德客户端
    amap = get_amap_client()

    # ② 根据出行方式分发到不同的 API
    if req.mode == "walking":
        result = amap.direction_walking(req.origin, req.destination)
    elif req.mode == "transit":
        result = amap.direction_transit(req.origin, req.destination)
    else:
        # 默认驾车（driving）
        result = amap.direction_driving(req.origin, req.destination)

    return JSONResponse(result)


# ================================================================
# 端点 4: POST /api/map/geocode —— 地址 → 经纬度
# ================================================================
@router.post("/geocode")
async def geocode(req: GeocodeRequest):
    """
    地理编码 —— 将文字地址转换为经纬度坐标

    适用场景: "协和医院在哪个位置？" → 返回坐标
    """
    # ① 获取高德客户端
    amap = get_amap_client()

    # ② 调用地理编码（地址→坐标）
    result = amap.geocode(req.address, city=req.city)

    return JSONResponse(result)


# ================================================================
# 端点 5: POST /api/map/regeocode —— 坐标 → 地址
# ================================================================
@router.post("/regeocode")
async def regeocode(location: str,            # URL query 参数：坐标
                    radius: int = 1000):      # URL query 参数：周边 POI 半径
    """
    逆地理编码 —— 将经纬度转换为详细地址

    适用场景: 用户共享位置后"这是哪里？"
    """
    # ① 获取高德客户端
    amap = get_amap_client()

    # ② 调用逆地理编码（坐标→地址）
    result = amap.regeocode(location, radius=radius)

    return JSONResponse(result)


# ================================================================
# 端点 6: POST /api/map/hospital-services —— 医院周边一站式查询
# ================================================================
@router.post("/hospital-services")
async def hospital_services(hospital_name: str,   # 医院名称
                            city: str = "",       # 城市
                            radius: int = 2000):  # 周边搜索半径
    """
    医院周边一站式查询 —— 一次请求获取：医院信息 + 周边住宿 + 餐饮 + 交通

    适用场景: "我去协和医院看病，附近有酒店吗？哪里可以吃饭？"
    """
    # ① 获取高德客户端
    amap = get_amap_client()

    # ② 调用一站式复合查询（内部串联 5 次 API 调用）
    result = amap.search_hospital_with_services(hospital_name, city=city, radius=radius)

    return JSONResponse(result)


# ================================================================
# 端点 7: POST /api/map/ip-location —— IP 定位
# ================================================================
@router.post("/ip-location")
async def ip_location():
    """
    IP 定位 —— 根据请求方 IP 获取当前所在城市

    适用场景: 自动获取用户城市，用于默认搜索范围
    """
    # ① 获取高德客户端
    amap = get_amap_client()

    # ② IP 定位（不传 IP 则用请求方 IP）
    result = amap.ip_location()

    return JSONResponse(result)


# ================================================================
# 端点 8: POST /api/map/chat —— 地图自然语言对话 ★核心入口★
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
{_fmt_for_prompt(api_result)}"""
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


# ================================================================
# 工具函数 —— 将 API 返回的 dict 转为 LLM 易读的文本
# ================================================================
def _fmt_for_prompt(data: dict, depth: int = 0) -> str:
    """
    将高德 API 返回的结构化 dict 精简为 LLM 友好的文本格式

    为什么需要这个函数？
      - 高德 API 返回的原始 JSON 体积很大（含大量元数据）
      - LLM 的上下文窗口有限，需要精简
      - 格式化后的文本 LLM 理解更准确

    参数:
      data:  高德 API 返回的结果 dict
      depth: 递归深度（防止无限循环，最大 2 层）

    返回:
      纯文本摘要（不超过 500 字符）
    """
    # 防止递归过深
    if depth > 2:
        return ""
    lines = []  # 累积输出行

    # 处理医院 + 周边服务复合结果
    if depth == 0 and data.get("hospital"):
        h = data["hospital"]
        lines.append(f"🏥 医院: {h.get('name')} | {h.get('address')} | 坐标:{h.get('location')}")

    # 处理 POI 列表（搜索/周边结果）
    if data.get("pois"):
        lines.append(f"共找到 {data.get('total', len(data['pois']))} 个地点（展示前5个）:")
        for p in data["pois"][:5]:
            lines.append(f"  • {p.get('name')} | {p.get('address','')} | "
                        f"距离:{p.get('distance','?')}米 | 评分:{p.get('rating','?')} | "
                        f"电话:{p.get('tel','?')}")

    # 处理周边设施分类（医院周边一站式查询结果）
    if data.get("services"):
        for cat, pois in data["services"].items():        # 遍历每个分类
            if pois:
                lines.append(f"\n🍽️🍜🏨🚇 {cat}（{len(pois)}个）:")
                for p in pois[:3]:                        # 每类最多 3 个
                    lines.append(f"  • {p.get('name')} | {p.get('address','')} | "
                                f"距离:{p.get('distance','?')}米 | 评分:{p.get('rating','?')}")

    # 处理驾车/步行路线
    if data.get("paths"):
        for i, path in enumerate(data["paths"][:1]):      # 只取第一条路线
            dist = int(path.get("distance", 0))            # 总距离（米）
            dur = int(path.get("duration", 0))             # 总耗时（秒）
            lines.append(f"🚗 路线: 距离{_fmt_dist(dist)}, 预计{_fmt_time(dur)}")
            steps = path.get("steps", [])[:3]              # 最多 3 个导航步骤
            for s in steps:
                lines.append(f"  → {s.get('instruction','')[:80]}")  # 截断过长指令

    # 处理公交方案
    if data.get("transits"):
        for t in data["transits"][:1]:                    # 只取第一条方案
            cost = t.get("cost", "")                       # 总费用
            dur = int(t.get("duration", 0))                # 总耗时
            lines.append(f"🚌 公交: 费用{cost}元, 预计{_fmt_time(dur)}")

    # 如果以上都没有匹配到，回退到原始字符串（截断到 500 字符）
    return "\n".join(lines) if lines else str(data)[:500]


def _fmt_dist(meters: int) -> str:
    """
    距离格式化 —— 米 → 人类可读

    例: 3500 → "3.5公里"
         800 → "800米"
    """
    if meters >= 1000:
        return f"{meters/1000:.1f}公里"    # 超过 1km 用公里显示
    return f"{meters}米"                    # 不足 1km 用米显示


def _fmt_time(seconds: int) -> str:
    """
    时间格式化 —— 秒 → 人类可读

    例: 4500 → "1小时15分钟"
         180 → "3分钟"
          45 → "45秒"
    """
    if seconds >= 3600:                              # 超过 1 小时
        h = seconds // 3600                          # 小时数
        m = (seconds % 3600) // 60                   # 余下的分钟数
        return f"{h}小时{m}分钟" if m else f"{h}小时"
    if seconds >= 60:                                # 分钟级别
        return f"{seconds // 60}分钟"
    return f"{seconds}秒"                            # 秒级别
