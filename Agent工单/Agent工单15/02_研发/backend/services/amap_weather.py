"""
================================================================================
文件名:   amap_weather.py
功能:     高德地图 Web 服务 API 客户端 —— 天气 / IP 定位 / 医院复合查询模块
          —— 以猴子补丁方式为 AmapClient 类注入天气、定位、复合查询方法
所属项目:  医疗智能体-影像分析系统
工单编号:  人工智能 NLP-Agent 数字人项目-医疗智能体-MCP V1.0
调用方:    api/map.py（地图 API 路由层）
          mcp_server/mcp_serve.py（MCP Server 工具层）
依赖:      config.py（AMAP_API_KEY, AMAP_BASE_URL, AMAP_API_TIMEOUT）
          .amap_core（AmapClient 基类）

注入方法（猴子补丁）:
  AmapClient
    ├── weather()                     # 天气查询（实时/预报）
    ├── ip_location()                 # IP 定位（获取当前城市）
    └── search_hospital_with_services()  # 【复合】医院 + 周边一站式查询

使用方式:
  直接 import services.amap_weather 即可（导入时自动注入到 AmapClient）

高德 API 文档: https://lbs.amap.com/api/webservice/summary
================================================================================
"""
import time       # time.time() —— 用于计算 API 调用耗时
import logging    # logging.getLogger —— 日志输出

# 从 amap_core 导入 AmapClient 类，用于猴子补丁注入方法
from services.amap_core import AmapClient  # AmapClient 基类（含 _get / search_poi / search_around）

# 创建本模块的 logger
_log = logging.getLogger("medical_agent.amap")  # 沿用统一日志命名空间


# ================================================================
# 8. 天气查询（注入到 AmapClient 类）
#    API: https://restapi.amap.com/v3/weather/weatherInfo
# ================================================================
def weather(self, city: str,                 # 城市编码（如 110000=北京 310000=上海）
            extensions: str = "base") -> dict:  # "base"=实时天气 "all"=未来4天预报
    """
    天气查询

    适用场景:
      - "北京今天天气怎么样？"
      - "去XX医院看病，今天会下雨吗？"

    返回值:
      base:  {"lives": [{天气/温度/风向/湿度/发布时间}]}
      all:   {"forecasts": [{城市 + 未来4天预报}]}
    """
    # ① 拼装参数
    params = {
        "city": city,                       # 城市编码（必填，如"110000"=北京）
        "extensions": extensions            # "base"=实时 "all"=预报
    }

    # ② 调用底层请求（self._get 来自 AmapClient）
    result = self._get("/weather/weatherInfo", params)  # 高德天气接口

    # ③ 解析结果
    if result["success"]:
        lives = result["data"].get("lives", [])          # 实时天气数组
        forecasts = result["data"].get("forecasts", [])  # 天气预报数组
        return {
            "success": True,
            "lives": lives,               # 实时天气
            "forecasts": forecasts,       # 预报天气
            "latency_ms": result["latency_ms"]
        }
    return result


# ================================================================
# 9. IP 定位（注入到 AmapClient 类）
#    API: https://restapi.amap.com/v3/ip
# ================================================================
def ip_location(self, ip: str = "") -> dict:  # IP 地址（空=使用请求方 IP）
    """
    IP 定位 —— 根据 IP 获取当前所在城市

    适用场景:
      - 用户在哪个城市？（不传 ip 则用请求方 IP）
      - 辅助搜索时默认城市
    """
    # ① 拼装参数
    params = {}
    if ip:
        params["ip"] = ip                # 指定 IP（可选，不传则用请求方 IP）

    # ② 调用底层请求（self._get 来自 AmapClient）
    result = self._get("/ip", params)  # 高德 IP 定位接口

    # ③ 解析结果
    if result["success"]:
        return {
            "success": True,
            "province": result["data"].get("province", ""),  # 省份
            "city": result["data"].get("city", ""),          # 城市
            "adcode": result["data"].get("adcode", ""),      # 城市编码（可用于天气等接口）
            "rectangle": result["data"].get("rectangle", ""), # 城市矩形范围
            "latency_ms": result["latency_ms"]
        }
    return result


# ================================================================
# 10. 复合查询（注入到 AmapClient 类）
#    医院位置 + 周边服务一站式搜索
#    内部串联 3 次 API 调用：搜索医院 → 获取坐标 → 周边搜索
# ================================================================
def search_hospital_with_services(self, hospital_name: str,  # 医院名称
                                  city: str = "",            # 所在城市（可选）
                                  radius: int = 2000) -> dict:  # 周边搜索半径（米）
    """
    医院周边一站式查询 —— Agent 回答"去XX医院怎么走？附近有酒店吗？有什么吃的？"

    内部流程（串行）:
      1. search_poi(hospital_name, poi_type="090000") → 找到医院坐标
      2. search_around(医院坐标, poi_type="050000") → 周边餐饮
      3. search_around(医院坐标, poi_type="100000") → 周边住宿
      4. search_around(医院坐标, poi_type="150300") → 周边公交站
      5. search_around(医院坐标, poi_type="150500") → 周边地铁站

    备注: 4 次周边搜索是串行的（非并行），总耗时约 200-400ms
          如需优化可改为 asyncio 并行，但对 Agent 体验无明显提升
    """
    # ① 第一步：搜索医院（poi_type="090000" = 医疗保健）
    hospital = self.search_poi(
        hospital_name,                    # 用户输入的医院名称
        city=city,                        # 城市限定（提高命中率）
        poi_type="090000",               # 090000 = 高德 POI 分类码：医疗保健服务
        offset=1                          # 只要第一个结果（最佳匹配）
    )
    # ② 检查医院搜索结果
    if not hospital.get("success") or not hospital.get("pois"):
        return {"success": False,
                "error": f"未找到医院: {hospital_name}"}  # 医院名称不存在或无结果

    # ③ 提取医院信息
    h = hospital["pois"][0]              # 最佳匹配的医院 POI
    loc = h.get("location", "")           # 医院坐标 "lng,lat"
    if not loc:
        return {"success": False,
                "error": "医院坐标缺失"}  # 极少见，部分数据可能缺少坐标

    # ④ 第二步：周边设施搜索（4 个类别串行调用）
    services = {}
    for kw, tp in [("餐饮", "050000"),    # 050000 = 餐饮服务（餐厅/小吃/咖啡）
                   ("住宿", "100000"),    # 100000 = 住宿服务（酒店/宾馆/青旅）
                   ("公交站", "150300"),  # 150300 = 公交车站
                   ("地铁站", "150500")]: # 150500 = 地铁站
        r = self.search_around(           # 以医院坐标为中心搜索
            loc,                          #   中心坐标
            keywords="",                  #   不限关键词（用类型过滤）
            poi_type=tp,                  #   POI 类型分类码
            radius=radius,                #   搜索半径（默认 2000 米）
            offset=5                      #   每类最多 5 条
        )
        if r.get("success"):
            services[kw] = r["pois"]      # 成功则保存结果

    # ⑤ 返回复合结果
    return {"success": True,
            "hospital": h,                # 医院信息（名称/地址/坐标/电话/评分）
            "services": services,         # 周边设施字典（餐饮/住宿/公交/地铁）
            "latency_ms": hospital["latency_ms"]}  # 仅记录首次搜索耗时


# ================================================================
# 猴子补丁注入 —— 将上述方法绑定到 AmapClient 类上
# ================================================================
AmapClient.weather = weather                                      # 注入天气查询方法
AmapClient.ip_location = ip_location                              # 注入 IP 定位方法
AmapClient.search_hospital_with_services = search_hospital_with_services  # 注入医院周边复合查询方法
