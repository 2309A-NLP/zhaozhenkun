"""
================================================================================
文件名:   mcp_serve.py
功能:     MCP（Model Context Protocol）Server
          —— 将医疗 Agent 的 11 个工具封装为标准 MCP 协议，供 MCP Client 调用
          —— 支持 stdio 传输模式（本地 MCP 客户端）和 HTTP/SSE 模式（远程客户端）
所属项目:  医疗智能体-影像分析系统
工单编号:  人工智能 NLP-Agent 数字人项目-医疗智能体-MCP V1.0

什么是 MCP？
  MCP 是 Anthropic 发布的模型上下文协议（Model Context Protocol），
  定义了 AI 模型与外部工具之间的标准化交互方式。
  本文件实现了 MCP Server 端，暴露工具供 Claude Desktop / Cursor / VS Code 等客户端调用。

工具列表（11 个）:
  ┌─ 高德地图工具（7 个）────────────────────────────┐
  │ amap_search_poi              关键词地点搜索      │
  │ amap_search_nearby           周边 POI 搜索       │
  │ amap_get_directions          出行路线规划        │
  │ amap_geocode                 地址 → 经纬度       │
  │ amap_regeocode               经纬度 → 地址       │
  │ amap_weather                 天气查询            │
  │ amap_hospital_services       医院周边一站式查询  │
  └─────────────────────────────────────────────────┘
  ┌─ 医疗智能体工具（4 个）──────────────────────────┐
  │ medical_health_consult       健康咨询（知识图谱） │
  │ medical_rag_search           医学知识检索（RAG） │
  │ medical_registration_intent  挂号意图解析        │
  │ （注: VQA/MRG 涉及图片，MCP stdio 模式下不适用） │
  └─────────────────────────────────────────────────┘

启动方式:
  开发模式:  cd 02_研发/mcp_server && python mcp_serve.py
  MCP客户端配置 (stdio):
    {
      "mcpServers": {
        "medical-agent": {
          "command": "python",
          "args": ["02_研发/mcp_server/mcp_serve.py"],
          "env": {"AMAP_API_KEY": "your-key"}
        }
      }
    }

依赖:
  pip install mcp httpx openai python-dotenv
================================================================================
"""
import sys              # sys.path —— 添加 backend 目录到 Python 模块搜索路径
import os               # os.getenv / os.environ —— 环境变量读取与设置
import json             # json.dumps —— 工具返回值序列化为 JSON 字符串
import logging          # logging —— 控制台日志输出
import time             # time.time —— 保留（可用于性能统计）
import re               # re.match —— 正则匹配（判断输入是坐标还是地址名）
from pathlib import Path  # Path —— 跨平台的文件路径处理

# 将 backend 目录加入 sys.path，以便 import 同项目的 config / kg / rag 模块
# Path(__file__).resolve().parent  = 02_研发/mcp_server/
#                          .parent = 02_研发/
#                          / "backend" = 02_研发/backend/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

# FastMCP —— Anthropic 官方 MCP Python SDK 的高层封装
# 使用 @mcp.tool() 装饰器即可将一个 async 函数注册为 MCP 工具
from mcp.server import FastMCP

# 配置日志（INFO 级别 = 启动信息 + 错误信息）
_log = logging.getLogger("medical_mcp_server")
logging.basicConfig(level=logging.INFO)

# ================================================================
# 配置加载 —— 从 .env 文件读取 API Key
# 为什么手动解析而不依赖 python-dotenv？
#   - 减少外部依赖（MCP Server 环境通常最小化安装）
#   - .env 格式简单（KEY=VALUE），正则/字符串处理即可
# ================================================================
_ENV_FILE = Path(__file__).resolve().parent.parent / "backend" / ".env"
if _ENV_FILE.exists():                                          # .env 文件存在
    with open(_ENV_FILE, encoding="utf-8") as f:               # UTF-8 读取
        for line in f:                                          # 逐行处理
            line = line.strip()                                 # 去除首尾空白
            if line and not line.startswith("#") and "=" in line:  # 跳过空行和注释
                k, v = line.split("=", 1)                       # 按 = 分割（只分一次）
                os.environ.setdefault(k.strip(), v.strip())     # 设置环境变量（不覆盖已有值）

# 从环境变量读取各 API Key
AMAP_KEY = os.getenv("AMAP_API_KEY", "")                        # 高德地图 Key
AMAP_BASE = "https://restapi.amap.com/v3"                      # 高德 API 基础地址
QWEN_KEY = os.getenv("QWEN_API_KEY", "")                        # 千问 Key（备用）
QWEN_BASE = os.getenv("QWEN_BASE_URL",
                      "https://dashscope.aliyuncs.com/compatible-mode/v1")  # 千问 API 地址
DEEPSEEK_KEY = os.getenv("DEEPSEEK_API_KEY", "")                # DeepSeek Key
DEEPSEEK_BASE = os.getenv("DEEPSEEK_BASE_URL",
                          "https://api.deepseek.com/v1")        # DeepSeek API 地址

# ================================================================
# 初始化 MCP Server
# ================================================================
mcp = FastMCP(
    name="医疗智能体-MCP-Server",                # MCP Server 名称（显示在客户端中）
    description="医疗Agent MCP Server — 提供高德地图就医导航 + 医学影像分析 + 知识检索服务",
    version="1.0.0"                              # 语义化版本号
)


# ================================================================
# HTTP 客户端 —— 供高德地图工具使用（同步 httpx.Client）
# ================================================================
import httpx  # 放在这里是为了强调它是 MCP Server 的独立依赖

_http = httpx.Client(                            # 创建同步 HTTP 客户端
    timeout=httpx.Timeout(10.0)                  # 所有请求统一 10 秒超时
)


def _amap_get(path: str, params: dict) -> dict:
    """
    高德 REST API 底层调用封装（MCP Server 内部使用）

    为什么单独封装而不是复用 amap_client.py？
      - MCP Server 是独立进程，不应该依赖 FastAPI 后端
      - 保持 MCP Server 的轻量性和独立性
      - 如果后端未启动，MCP Server 仍然可以工作

    参数:
      path:   API 路径，如 "/place/text"
      params: 请求参数字典（不含 key，本函数自动注入）

    返回:
      原始 API 响应 dict，或 {"error": "错误描述"}
    """
    params["key"] = AMAP_KEY                    # ① 注入 API Key
    try:
        r = _http.get(                           # ② 发送 GET 请求
            f"{AMAP_BASE}{path}",               #    拼接完整 URL
            params=params                       #    查询参数
        )
        r.raise_for_status()                     # ③ 检查 HTTP 状态（非 2xx 抛异常）
        data = r.json()                          # ④ 解析 JSON 响应
        if data.get("status") != "1":            # ⑤ 检查高德业务状态码
            return {"error": data.get("info", "API错误")}
        return data                              # ⑥ 返回原始数据
    except Exception as e:
        return {"error": str(e)}                 # ⑦ 异常兜底


# ================================================================
# 高德地图工具（7 个）—— 使用 @mcp.tool() 装饰器注册
# 每个工具函数 = 函数名 + docstring + 参数类型标注 + 返回值
# MCP SDK 自动从函数签名和 docstring 生成 Tool Schema
# ================================================================

@mcp.tool()  # ← 这个装饰器把 async 函数注册为 MCP Tool
async def amap_search_poi(keywords: str,        # ← 参数类型标注自动生成 JSON Schema
                          city: str = "",
                          poi_type: str = "",
                          offset: int = 10) -> str:
    """
    关键词地点搜索 —— 搜索医院、酒店、餐厅、交通站点等

    :param keywords: 搜索关键词，如"三甲医院"、"酒店"、"川菜"
    :param city: 城市名（可选），如"北京"、"上海"
    :param poi_type: POI类型编码：090000=医疗, 100000=住宿, 050000=餐饮, 150000=交通
    :param offset: 返回条数(1-25)，默认10
    :return: JSON格式的搜索结果摘要
    """
    # 调用高德文本搜索 API
    data = _amap_get("/place/text", {
        "keywords": keywords,                    # 搜索关键词
        "city": city,                            # 城市限定
        "types": poi_type,                       # POI 类型
        "offset": offset,                        # 返回条数
        "extensions": "all"                      # 返回详细信息（含评分/图片）
    })
    if "error" in data:                          # API 调用失败
        return json.dumps(data, ensure_ascii=False)

    # 精简 POI 数据（只保留关键字段，减少 token 消耗）
    pois = data.get("pois", [])
    result = {"total": data.get("count", 0), "pois": []}
    for p in pois:
        result["pois"].append({
            "name": p.get("name"),               # 名称
            "address": p.get("address"),         # 地址
            "location": p.get("location"),       # 坐标
            "tel": p.get("tel"),                 # 电话
            "type": p.get("type"),               # 分类
            "rating": p.get("biz_ext", {}).get("rating", ""),   # 评分
            "cost": p.get("biz_ext", {}).get("cost", ""),       # 人均
            "distance": p.get("distance", "")     # 距离
        })
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def amap_search_nearby(location: str,      # 中心坐标 "lng,lat"
                             poi_type: str = "", # POI 类型编码
                             keywords: str = "", # 关键词过滤
                             radius: int = 3000) -> str:
    """
    周边搜索 —— 搜索指定坐标附近的设施（住宿/餐饮/交通）

    :param location: 中心点坐标，格式 "经度,纬度"，如 "116.397,39.909"
    :param poi_type: POI类型：050000=餐饮, 100000=住宿, 150300=公交站, 150500=地铁站
    :param keywords: 关键词过滤（可选）
    :param radius: 搜索半径（米），默认3000
    :return: JSON格式的周边POI列表
    """
    # 拼装请求参数
    params = {
        "location": location,                    # 中心坐标（必填）
        "radius": radius,                        # 搜索半径
        "offset": 10,                            # 返回数量
        "extensions": "all"                      # 详细信息
    }
    if poi_type:
        params["types"] = poi_type               # 类型过滤
    if keywords:
        params["keywords"] = keywords            # 关键词过滤

    data = _amap_get("/place/around", params)
    if "error" in data:
        return json.dumps(data, ensure_ascii=False)

    # 精简 POI 数据
    pois = data.get("pois", [])
    result = {"total": data.get("count", 0), "pois": []}
    for p in pois:
        result["pois"].append({
            "name": p.get("name"),
            "address": p.get("address"),
            "location": p.get("location"),
            "tel": p.get("tel"),
            "distance": (p.get("distance", "") + "米") if p.get("distance") else "",
            "rating": p.get("biz_ext", {}).get("rating", ""),
            "cost": p.get("biz_ext", {}).get("cost", "")
        })
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def amap_get_directions(origin: str,         # 起点（坐标或名称）
                              destination: str,    # 终点（坐标或名称）
                              mode: str = "driving",  # 出行方式
                              city: str = "") -> str:
    """
    出行路线规划 —— 查询从起点到终点的路线（驾车/步行/公交）

    :param origin: 起点坐标 "lng,lat" 或地址名
    :param destination: 终点坐标 "lng,lat" 或地址名
    :param mode: 出行方式：driving(驾车), walking(步行), transit(公交)
    :param city: 城市名（公交时需要）
    :return: 路线规划结果（距离、时间、步骤）
    """
    # 工具函数：判断输入是坐标还是名称，如果是名称则先做地理编码
    def _resolve(name: str) -> str:
        """判断输入是坐标（116.xxx,39.xxx）还是地址名，地址名则转为坐标"""
        if re.match(r'^\d{2,3}\.\d+,\d{2,3}\.\d+$', name):  # 匹配 "数字.数字,数字.数字" 格式
            return name                                       # 已经是坐标，直接返回
        geo = _amap_get("/geocode/geo", {"address": name})   # 地理编码
        if "error" not in geo and geo.get("geocodes"):
            return geo["geocodes"][0].get("location", name)  # 返回坐标
        return name                                           # 编码失败则返回原名

    # 解析起点和终点为坐标
    origin_loc = _resolve(origin)
    dest_loc = _resolve(destination)

    # 根据出行方式调用对应 API
    params = {"origin": origin_loc, "destination": dest_loc}
    if mode == "walking":
        data = _amap_get("/direction/walking", params)
    elif mode == "transit":
        if city:
            params["city"] = city                # 公交需要城市编码
        data = _amap_get("/direction/transit/integrated", params)
    else:
        params["extensions"] = "all"             # 驾车请求详细信息
        data = _amap_get("/direction/driving", params)

    if "error" in data:
        return json.dumps(data, ensure_ascii=False)

    route = data.get("route", {})                # 路线根对象

    # 公交模式：返回换乘方案
    if mode == "transit":
        transits = route.get("transits", [])
        result = []
        for t in transits[:3]:                   # 最多 3 个方案
            result.append({
                "cost": t.get("cost", "?"),       # 费用
                "duration": _fmt_time(int(t.get("duration", 0))),  # 耗时
                "walking_distance": str(int(t.get("walking_distance", 0))) + "米",
                "segments": [                     # 换乘段
                    (s.get("bus", {}).get("name", "") or           # 公交线路名
                     s.get("railway", {}).get("name", "") or       # 地铁线路名
                     s.get("walking", {}).get("destination", ""))  # 步行终点
                    for s in t.get("segments", [])[:5]             # 最多 5 段
                ]
            })
        return json.dumps(result, ensure_ascii=False, indent=2)
    else:
        # 驾车/步行模式：返回路径方案
        paths = route.get("paths", [])
        result = []
        for p in paths[:3]:
            result.append({
                "distance": _fmt_dist(int(p.get("distance", 0))),
                "duration": _fmt_time(int(p.get("duration", 0))),
                "strategy": p.get("strategy", ""),  # 策略描述
                "toll": p.get("tolls", 0),           # 过路费
            })
        return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
async def amap_geocode(address: str,             # 地址文本
                       city: str = "") -> str:   # 城市名
    """
    地理编码 —— 将地址转换为经纬度坐标

    :param address: 地址名称，如"北京协和医院"
    :param city: 城市名（可选）
    :return: 地址对应的经纬度坐标
    """
    data = _amap_get("/geocode/geo", {"address": address, "city": city})
    if "error" in data:
        return json.dumps(data, ensure_ascii=False)

    geos = data.get("geocodes", [])              # 匹配结果数组
    if geos:
        g = geos[0]                              # 取最佳匹配
        return json.dumps({
            "address": g.get("formatted_address"),  # 标准化地址
            "location": g.get("location")           # 经纬度坐标
        }, ensure_ascii=False, indent=2)
    return '{"error":"未找到该地址"}'


@mcp.tool()
async def amap_regeocode(location: str) -> str:
    """
    逆地理编码 —— 将经纬度坐标转换为详细地址

    :param location: 坐标 "lng,lat"
    :return: 格式化地址 + 省市区信息
    """
    data = _amap_get("/geocode/regeo", {
        "location": location,
        "extensions": "base"                     # 基本信息（不含周边 POI）
    })
    if "error" in data:
        return json.dumps(data, ensure_ascii=False)

    regeo = data.get("regeocode", {})
    return json.dumps({
        "address": regeo.get("formatted_address"),       # 完整地址
        "city": regeo.get("addressComponent", {}).get("city", ""),       # 城市
        "district": regeo.get("addressComponent", {}).get("district", ""),  # 区县
    }, ensure_ascii=False, indent=2)


@mcp.tool()
async def amap_weather(city: str = "北京") -> str:
    """
    天气查询 —— 查询指定城市的实时天气

    :param city: 城市名或城市编码（如 110000=北京）
    :return: 实时天气信息（天气/温度/风向/湿度）
    """
    data = _amap_get("/weather/weatherInfo", {
        "city": city,
        "extensions": "base"                     # base=实时天气
    })
    if "error" in data:
        return json.dumps(data, ensure_ascii=False)

    lives = data.get("lives", [])                # 实时天气数组
    if lives:
        l = lives[0]                             # 取当前天气
        return json.dumps({
            "city": l.get("city"),                # 城市名
            "weather": l.get("weather"),          # 天气状况（晴/雨/阴）
            "temperature": l.get("temperature") + "°C",  # 温度
            "wind": l.get("winddirection") + "风 " + l.get("windpower") + "级",  # 风向风力
            "humidity": l.get("humidity") + "%",  # 湿度
            "report_time": l.get("reporttime")     # 发布时间
        }, ensure_ascii=False, indent=2)
    return '{"error":"天气数据不可用"}'


@mcp.tool()
async def amap_hospital_services(hospital_name: str,  # 医院名称
                                 city: str = "",      # 所在城市
                                 radius: int = 2000) -> str:
    """
    医院周边一站式查询 —— 一次查询医院位置 + 周边住宿 + 餐饮 + 交通

    :param hospital_name: 医院名称，如"协和医院"
    :param city: 所在城市（可选）
    :param radius: 周边搜索半径（米），默认2000
    :return: 医院信息 + 周边住宿/餐饮/交通站点列表
    """
    # Step 1: 搜索医院（获取坐标）
    h_data = _amap_get("/place/text", {
        "keywords": hospital_name,               # 医院名称
        "city": city,                            # 城市
        "types": "090000",                       # 090000=医疗保健服务
        "offset": 1,                             # 只要最佳匹配
        "extensions": "all"
    })
    if "error" in h_data or not h_data.get("pois"):
        return json.dumps({"error": f"未找到医院: {hospital_name}"}, ensure_ascii=False)

    h = h_data["pois"][0]                        # 医院 POI 对象
    loc = h.get("location", "")                   # 医院坐标
    result = {
        "hospital": {
            "name": h.get("name"),                # 医院名称
            "address": h.get("address"),          # 地址
            "location": loc,                      # 坐标
            "tel": h.get("tel"),                  # 电话
            "rating": h.get("biz_ext", {}).get("rating", "")  # 评分
        },
        "services": {}                           # 周边服务（待填充）
    }

    if not loc:
        return json.dumps(result, ensure_ascii=False, indent=2)

    # Step 2: 周边 4 类设施搜索
    for cat, tp in [("住宿", "100000"),           # 100000=住宿服务
                    ("餐饮", "050000"),           # 050000=餐饮服务
                    ("公交站", "150300"),         # 150300=公交站
                    ("地铁站", "150500")]:        # 150500=地铁站
        data = _amap_get("/place/around", {
            "location": loc,                     # 医院坐标
            "types": tp,                         # POI 类型
            "radius": radius,                    # 搜索半径
            "offset": 5,                         # 每类最多 5 条
            "extensions": "all"
        })
        if "error" not in data:
            result["services"][cat] = [          # 精简每类 POI
                {"name": p.get("name"),
                 "address": p.get("address"),
                 "distance": (p.get("distance", "") + "米") if p.get("distance") else "",
                 "rating": p.get("biz_ext", {}).get("rating", ""),
                 "cost": p.get("biz_ext", {}).get("cost", "")}
                for p in data.get("pois", [])[:5]
            ]

    return json.dumps(result, ensure_ascii=False, indent=2)


# ================================================================
# 医疗智能体工具（3 个）—— 封装已有的医学 LLM 能力
# 注: VQA/MRG 需要图片输入，MCP stdio 模式下图片传输不便，暂不暴露
# ================================================================

@mcp.tool()
async def medical_health_consult(question: str) -> str:
    """
    健康咨询 —— 基于医学知识图谱（6143种疾病）回答医学问题

    适用场景:
      - "百日咳的传播途径是什么？"
      - "高血压的并发症有哪些？"
      - "头痛应该挂什么科？"

    :param question: 医学问题
    :return: 基于知识图谱 + DeepSeek 推理的医学回答
    """
    try:
        # 导入知识图谱模块（在 backend/kg/ 下）
        from kg.knowledge import answer_question  # 知识图谱问答引擎
        from openai import OpenAI                 # DeepSeek API 调用

        # Step 1: 从知识图谱检索相关疾病
        kg = answer_question(question)

        if kg.get("found"):                       # 找到匹配疾病
            # Step 2: 创建 DeepSeek 客户端（每次新建以确保线程安全）
            client = OpenAI(
                api_key=DEEPSEEK_KEY,
                base_url=DEEPSEEK_BASE,
                timeout=httpx.Timeout(120)         # 120 秒超时（LLM 推理可能较慢）
            )
            # Step 3: 构造提示词（知识库上下文 + 用户问题）
            prompt = (f"知识库: {kg['disease']} - {kg['reply'][:500]}\n"
                     f"\n用户问题: {question}\n"
                     f"请给出标准医学教科书级别的精确答案。")
            # Step 4: 调用 DeepSeek 生成答案
            r = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system",
                     "content": "你是临床医学专家，给出精确医学答案，包含具体数值。结尾加：⚠仅供参考，请及时就医。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=600,                    # 限制回复长度
                temperature=0.2                    # 低温度 = 更确定性的回答
            )
            return f"【{kg['disease']}】\n{r.choices[0].message.content}"

        return "未找到相关疾病信息，请尝试更具体的问题。"
    except Exception as e:
        return f"健康咨询服务异常: {e}"


@mcp.tool()
async def medical_rag_search(question: str,       # 医学问题
                             top_k: int = 5) -> str:
    """
    医学知识检索 —— 从向量知识库（ChromaDB）中检索相关医学文档并生成回答

    :param question: 医学问题
    :param top_k: 检索文档数量(1-10)，默认5
    :return: 基于知识库文档的增强回答（含引用来源）
    """
    try:
        from rag.vector_store import get_vector_store  # 向量库单例
        from openai import OpenAI                      # DeepSeek API

        # Step 1: 向量检索 —— 从 ChromaDB 中找最相关的文档片段
        vs = get_vector_store()
        docs = vs.search(question, top_k=min(top_k, 10))  # 限制最多 10 条
        if not docs:
            return "知识库中未找到相关内容。"

        # Step 2: 拼接上下文
        ctx = "\n\n".join(
            f"【参考 {i+1}】{d['content'][:300]}"        # 每条截断到 300 字
            for i, d in enumerate(docs)
        )

        # Step 3: 调用 DeepSeek 生成 RAG 回答
        client = OpenAI(api_key=DEEPSEEK_KEY, base_url=DEEPSEEK_BASE,
                      timeout=httpx.Timeout(120))
        r = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system",
                 "content": "基于参考资料回答医学问题，引用参考编号。"},
                {"role": "user",
                 "content": f"{ctx}\n\n问题: {question}"}
            ],
            max_tokens=800,
            temperature=0.1                          # 极低温度 = 严格基于参考资料
        )

        # Step 4: 追加引用来源
        sources = "\n---\n📚 参考来源:\n" + "\n".join(
            f"[{i+1}] 相似度={d.get('score', 0):.3f} | "
            f"{d.get('metadata', {}).get('source_file', '')}"
            for i, d in enumerate(docs)
        )
        return r.choices[0].message.content + sources
    except Exception as e:
        return f"RAG检索服务异常: {e}"


@mcp.tool()
async def medical_registration_intent(message: str) -> str:
    """
    挂号意图解析 —— 从自然语言中提取挂号参数（科室/医生/时间）

    适用场景:
      - "帮大宝挂一个儿科专家的号"  → 提取: child_name=大宝, department=儿科, title=专家
      - "查一下今天下午内科还有号吗"  → 提取: intent=query, department=内科

    :param message: 用户的自然语言挂号请求
    :return: 解析后的 JSON 格式挂号参数
    """
    try:
        from openai import OpenAI
        from datetime import datetime                # 获取当前日期

        # 创建 DeepSeek 客户端
        client = OpenAI(api_key=DEEPSEEK_KEY, base_url=DEEPSEEK_BASE,
                      timeout=httpx.Timeout(30))     # 意图解析 30 秒足够
        now = datetime.now().strftime("%Y-%m-%d %A")  # 当前日期（用于解析"今天""明天"）

        # 调用 DeepSeek 进行意图解析
        r = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": message}],
            max_tokens=300,
            temperature=0.1,                         # 低温度 = 结构化输出更稳定
            extra_body={                             # extra_body 传递非标准参数
                "system": f"""你是挂号意图解析器。从消息提取JSON参数。
意图: book(挂号) | query(查号) | cancel(取消) | doctor_query(查医生)
参数: intent, child_name, department, doctor_title(专家/主任/普通),
      date(YYYY-MM-DD), time_slot(上午/下午), doctor_name, reason
当前日期: {now}
只返回JSON对象。"""
            }
        )
        return r.choices[0].message.content
    except Exception as e:
        return f"挂号意图解析异常: {e}"


# ================================================================
# 工具函数 —— 格式化距离和时间（与 api/map.py 独立，避免跨模块依赖）
# ================================================================
def _fmt_dist(meters: int) -> str:
    """距离格式化：米 → 人类可读"""
    if meters >= 1000:
        return f"{meters/1000:.1f}公里"
    return f"{meters}米"


def _fmt_time(seconds: int) -> str:
    """时间格式化：秒 → 人类可读"""
    if seconds >= 3600:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}小时{m}分钟" if m else f"{h}小时"
    if seconds >= 60:
        return f"{seconds // 60}分钟"
    return f"{seconds}秒"


# ================================================================
# 启动入口
# ================================================================
if __name__ == "__main__":
    # 打印启动横幅
    _log.info("=" * 60)
    _log.info("医疗智能体 MCP Server V1.0 启动中...")
    _log.info("工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-MCP V1.0")
    _log.info("工具数量：高德地图 7 个 + 医疗智能体 3 个 = 共 10 个")
    _log.info("传输方式：stdio（标准输入输出）")
    _log.info("=" * 60)

    # 启动 MCP Server（阻塞式，等待 MCP Client 连接）
    # transport="stdio" 表示通过标准输入输出与 MCP Client 通信
    # MCP Client（如 Claude Desktop）会启动这个进程并通过 stdin/stdout 发送 JSON-RPC 消息
    mcp.run(transport="stdio")
