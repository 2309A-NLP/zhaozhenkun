"""
================================================================================
文件名:   amap_client.py
功能:     高德地图 Web 服务 API 客户端
          —— 封装高德地图 REST API，提供医院位置相关的出行/住宿/餐饮查询能力
所属项目:  医疗智能体-影像分析系统
工单编号:  人工智能 NLP-Agent 数字人项目-医疗智能体-MCP V1.0
调用方:    api/map.py（地图 API 路由层）
          mcp_server/mcp_serve.py（MCP Server 工具层）
依赖:      config.py（AMAP_API_KEY, AMAP_BASE_URL, AMAP_API_TIMEOUT）
          httpx（HTTP 客户端库）

类结构:
  AmapClient
    ├── __init__()                  # 初始化 API Key / BaseURL / httpx 客户端
    ├── _get(path, params)          # 【底层】封装 GET 请求，注入 key + 异常处理
    ├── search_poi()                # 关键词地点搜索（医院/酒店/餐厅）
    ├── search_around()             # 周边 POI 搜索（以坐标为中心）
    ├── direction_driving()         # 驾车路线规划
    ├── direction_walking()         # 步行路线规划
    ├── direction_transit()         # 公交换乘规划
    ├── geocode()                   # 地址 → 经纬度
    ├── regeocode()                 # 经纬度 → 地址
    ├── weather()                   # 天气查询
    ├── ip_location()              # IP 定位
    └── search_hospital_with_services()  # 【复合】医院 + 周边一站式查询

全局:
  get_amap_client()                 # 单例获取函数
  _fmt_poi(p)                       # POI 结果精简工具函数

高德 API 文档: https://lbs.amap.com/api/webservice/summary
================================================================================
"""
import time       # time.time() —— 计算 API 调用耗时（毫秒级）
import logging    # logging.getLogger —— 模块级别日志输出
import httpx      # httpx.Client —— 高性能 HTTP 客户端（比 requests 更快）
from typing import Optional, List, Dict, Any  # 类型标注，提高代码可读性

# 从项目配置中心导入高德地图相关常量
from config import AMAP_API_KEY, AMAP_BASE_URL, AMAP_API_TIMEOUT

# 创建本模块的 logger，后续所有日志通过 _log.info/warning/error 输出
_log = logging.getLogger("medical_agent.amap")


class AmapClient:
    """
    高德地图 Web 服务 API 客户端

    所有方法均返回统一的 dict 格式:
      成功: {"success": True,  "data": ..., "latency_ms": 123.45}
      失败: {"success": False, "error": "错误描述", "latency_ms": 123.45}

    支持的功能:
      - POI 搜索（关键词 / 周边）
      - 路线规划（驾车 / 步行 / 公交）
      - 地理编码 / 逆地理编码
      - 天气 / IP 定位
      - 医院周边一站式复合查询
    """

    def __init__(self):
        """
        初始化高德地图客户端

        做的事:
          1. 保存 API Key（从 config.AMAP_API_KEY 读取）
          2. 保存 API 基础 URL（默认 https://restapi.amap.com/v3）
          3. 创建 httpx.Client 实例（连接池复用、超时控制）
        """
        self.key = AMAP_API_KEY           # 高德 Web 服务 API Key（必填，注册即得）
        self.base = AMAP_BASE_URL         # API 基础地址（v3 版本）
        self.client = httpx.Client(       # 创建 HTTP 客户端（同步，非异步）
            timeout=httpx.Timeout(        # 设置超时策略
                AMAP_API_TIMEOUT,         #   总超时：从 config 读取，默认 10 秒
                connect=10.0              #   连接超时：10 秒（建立 TCP 连接的最大等待）
            )
        )

    # ================================================================
    # 底层请求 —— 所有 API 调用的统一入口
    # ================================================================
    def _get(self, path: str, params: dict) -> dict:
        """
        【底层】封装 HTTPS GET 请求，统一处理 key 注入 + 异常捕获 + 耗时统计

        参数:
          path:   API 路径，如 "/place/text"（不含 base URL）
          params: 请求参数字典，如 {"keywords":"协和医院"}（不需要传 key）

        返回:
          成功: {"success": True,  "data": {...}, "latency_ms": 123.45}
          失败: {"success": False, "error": "错误原因", "latency_ms": 123.45}

        流程:
          1. 注入 API Key 到请求参数
          2. 记录开始时间
          3. 发送 GET 请求
          4. 检查 HTTP 状态码（非 200 抛异常）
          5. 解析 JSON 响应体
          6. 检查高德业务状态码（status != "1" 视为失败）
          7. 计算耗时、返回结果
        """
        # ① 注入 API Key —— 高德所有接口都要求传 key 参数
        params["key"] = self.key  # 直接修改原 dict（调用方无需关心 key）

        # ② 记录请求开始时间（用于计算延迟）
        t0 = time.time()  # 返回 Unix 时间戳（秒），精度微秒级

        try:
            # ③ 发起 GET 请求（httpx 自动拼接 base + path）
            r = self.client.get(                     # HTTP GET 方法
                f"{self.base}{path}",                #   完整 URL = base + path
                params=params                        #   查询参数（已包含 key）
            )
            r.raise_for_status()                    # ④ 检查 HTTP 状态码，非 2xx 抛异常

            data = r.json()                         # ⑤ 解析响应体为 Python dict

            # ⑥ 计算请求耗时（毫秒），保留两位小数
            latency = round((time.time() - t0) * 1000, 2)

            # ⑦ 检查高德业务状态码
            #    高德 API 返回 {"status":"1"...} 表示成功
            #    status 不为 "1" 时，info 字段包含错误描述
            if data.get("status") != "1":
                return {"success": False,           # 业务失败标记
                        "error": data.get("info", "未知错误"),  # 高德返回的错误信息
                        "latency_ms": latency}      # 即使失败也记录耗时

            # ⑧ 全部通过：返回成功结果
            return {"success": True,                # 业务成功标记
                    "data": data,                   # 完整的 API 响应数据
                    "latency_ms": latency}          # 请求耗时

        except Exception as e:
            # ⑨ 网络异常 / 超时 / 解析失败等兜底处理
            latency = round((time.time() - t0) * 1000, 2)  # 仍计算耗时
            return {"success": False,               # 失败标记
                    "error": str(e),                # 异常消息原文
                    "latency_ms": latency}          # 耗时

    # ================================================================
    # 1. 地点搜索 —— 关键词搜索医院/酒店/餐饮
    #    API: https://restapi.amap.com/v3/place/text
    # ================================================================
    def search_poi(self, keywords: str,        # 搜索关键词，如"三甲医院""酒店""川菜"
                   city: str = "",             # 城市名/编码（空=全国搜索）
                   poi_type: str = "",         # POI 类型编码（090000=医疗 100000=住宿 050000=餐饮）
                   page: int = 1,              # 页码（从 1 开始）
                   offset: int = 10,           # 每页条数（1~25）
                   extensions: str = "all") -> dict:  # "base"=基本信息 "all"=详细信息（含图片/评分）
        """
        关键词地点搜索

        适用场景:
          - "北京有哪些三甲医院？"
          - "搜索附近的快捷酒店"
          - "协和医院周边有什么餐厅"

        返回值示例:
          {"success": True, "pois": [{"name":"协和医院","address":"...","location":"..."}],
           "total": 100, "latency_ms": 85.2}
        """
        # ① 拼装请求参数
        params = {
            "keywords": keywords,               # 搜索关键词（必填）
            "extensions": extensions,           # "all" 返回详细评分/图片（v3 API 特性）
            "page": page,                       # 页码
            "offset": min(offset, 25)           # 每页最大 25 条，超过则截断
        }
        if city:
            params["city"] = city               # 城市限定（可选，提高精度）
        if poi_type:
            params["types"] = poi_type          # 类型过滤（可选，如"090000"只搜医疗）

        # ② 调用底层请求
        result = self._get("/place/text", params)  # 高德 POI 文本搜索接口

        # ③ 解析结果：提取 POI 列表并精简字段
        if result["success"]:
            pois = result["data"].get("pois", [])  # 原始 POI 数组（可能为空）
            count = int(result["data"].get("count", 0))  # 总结果数（字符串→整数）
            return {
                "success": True,
                "pois": [_fmt_poi(p) for p in pois],  # 精简每个 POI，只保留关键字段
                "total": count,                        # 总命中数
                "latency_ms": result["latency_ms"]     # 透传底层耗时
            }
        return result  # 失败时直接返回错误信息

    # ================================================================
    # 2. 周边搜索 —— 查找医院附近的酒店/餐饮/公交
    #    API: https://restapi.amap.com/v3/place/around
    # ================================================================
    def search_around(self, location: str,      # 中心坐标 "经度,纬度" 如 "116.397,39.909"
                      keywords: str = "",       # 搜索关键词（可选，与 poi_type 二选一或搭配使用）
                      poi_type: str = "",       # POI 类型（050000=餐饮 100000=住宿 150000=交通）
                      radius: int = 3000,       # 搜索半径（米），默认 3 公里
                      page: int = 1,            # 页码
                      offset: int = 10) -> dict:  # 每页条数
        """
        周边 POI 搜索（以指定坐标为中心）

        适用场景:
          - "协和医院 2 公里内有什么酒店？"
          - "附近的公交站/地铁站在哪？"
          - "医院旁边有什么好吃的？"

        定位方式:
          1. 先用 geocode() 获取医院坐标
          2. 再用本方法搜索周边设施
        """
        # ① 拼装请求参数
        params = {
            "location": location,               # 中心坐标（必填）
            "radius": radius,                   # 搜索半径（米）
            "extensions": "all",               # 返回详细信息（评分/图片）
            "page": page,                       # 页码
            "offset": min(offset, 25)          # 每页上限 25
        }
        if keywords:
            params["keywords"] = keywords      # 关键词过滤（可选）
        if poi_type:
            params["types"] = poi_type         # 类型过滤（可选，推荐使用）

        # ② 调用底层请求
        result = self._get("/place/around", params)  # 高德周边搜索接口

        # ③ 解析结果
        if result["success"]:
            pois = result["data"].get("pois", [])    # 周边 POI 列表
            count = int(result["data"].get("count", 0))  # 结果总数
            return {
                "success": True,
                "pois": [_fmt_poi(p) for p in pois],  # 精简格式
                "total": count,
                "latency_ms": result["latency_ms"]
            }
        return result

    # ================================================================
    # 3. 驾车路线规划
    #    API: https://restapi.amap.com/v3/direction/driving
    # ================================================================
    def direction_driving(self, origin: str,          # 起点坐标 "lng,lat"
                          destination: str,           # 终点坐标 "lng,lat"
                          origin_type: str = "1",     # 起点类型：1=坐标 0=POI ID
                          dest_type: str = "1",       # 终点类型：1=坐标 0=POI ID
                          strategy: int = 0) -> dict:  # 策略：0=速度优先 1=费用优先 2=距离优先 3=不走快速
        """
        驾车路线规划

        返回多条可选路径，每条含:
          - distance:  总距离（米）
          - duration:  预计耗时（秒）
          - toll:      过路费（元）
          - steps:     导航步骤列表（每步含 instruction 指令文本）

        适用场景:
          - "从家开车去协和医院怎么走？"
          - "去XX医院哪条路最快？"
        """
        # ① 拼装请求参数
        params = {
            "origin": origin,                   # 起点坐标
            "destination": destination,         # 终点坐标
            "origin_type": origin_type,         # 起点输入类型（默认坐标）
            "destination_type": dest_type,      # 终点输入类型（默认坐标）
            "strategy": strategy,               # 路线策略（速度优先）
            "extensions": "all"                # 返回详细信息
        }

        # ② 调用底层请求
        result = self._get("/direction/driving", params)  # 高德驾车路径规划接口

        # ③ 解析结果
        if result["success"]:
            route = result["data"].get("route", {})   # 路线对象
            paths = route.get("paths", [])            # 可选路径列表（多条方案）
            return {
                "success": True,
                "paths": paths,                       # 所有路径方案
                "latency_ms": result["latency_ms"]
            }
        return result

    # ================================================================
    # 4. 步行路线规划
    #    API: https://restapi.amap.com/v3/direction/walking
    # ================================================================
    def direction_walking(self, origin: str,       # 起点坐标 "lng,lat"
                          destination: str) -> dict:  # 终点坐标 "lng,lat"
        """
        步行路线规划

        返回步行路径，包含：
          - distance: 步行距离（米）
          - duration: 预计时长（秒）
          - steps:    每一步的导航指令（"沿XX路直行200米"）

        适用场景:
          - "出了地铁站走到医院要多久？"
          - "从酒店步行去协和医院怎么走？"
        """
        # ① 拼装参数（步行只需起点终点）
        params = {
            "origin": origin,                    # 起点坐标
            "destination": destination           # 终点坐标
        }

        # ② 调用底层请求
        result = self._get("/direction/walking", params)  # 高德步行规划接口

        # ③ 解析结果
        if result["success"]:
            route = result["data"].get("route", {})   # 路线对象
            paths = route.get("paths", [])            # 可选路径
            return {
                "success": True,
                "paths": paths,
                "latency_ms": result["latency_ms"]
            }
        return result

    # ================================================================
    # 5. 公交换乘规划
    #    API: https://restapi.amap.com/v3/direction/transit/integrated
    # ================================================================
    def direction_transit(self, origin: str,        # 起点坐标 "lng,lat"
                          destination: str,          # 终点坐标 "lng,lat"
                          city: str = "",            # 起点城市编码（如 110000=北京）
                          cityd: str = "") -> dict:  # 终点城市编码（跨城时需要）
        """
        公交换乘规划（含地铁/公交/步行混合）

        返回公交方案列表，每条含:
          - cost:             总费用（元）
          - duration:         总耗时（秒）
          - walking_distance: 步行距离（米）
          - segments:         换乘段列表（公交线路/地铁线路/步行段）

        适用场景:
          - "从北京西站坐公交去协和医院？"
          - "坐地铁怎么到XX医院？"
        """
        # ① 拼装参数
        params = {
            "origin": origin,                    # 起点坐标
            "destination": destination            # 终点坐标
        }
        if city:
            params["city"] = city                # 起点城市（可选，提高准确度）
        if cityd:
            params["cityd"] = cityd              # 终点城市（跨城必填）

        # ② 调用底层请求（使用 integrated 版本，返回公交换乘组合方案）
        result = self._get("/direction/transit/integrated", params)

        # ③ 解析结果
        if result["success"]:
            route = result["data"].get("route", {})     # 路线对象
            transits = route.get("transits", [])         # 公交方案列表
            return {
                "success": True,
                "transits": transits,                    # 所有公交方案
                "latency_ms": result["latency_ms"]
            }
        return result

    # ================================================================
    # 6. 地理编码 —— 地址 → 经纬度
    #    API: https://restapi.amap.com/v3/geocode/geo
    # ================================================================
    def geocode(self, address: str,        # 地址文本，如"北京协和医院""天安门"
                city: str = "") -> dict:   # 城市名（可选，缩小搜索范围）
        """
        地理编码 —— 将文字地址转换为经纬度坐标

        适用场景:
          - "协和医院在哪里？" → 返回经纬度
          - 用户说"去西单"，需要先转坐标才能做路线规划

        返回值:
          成功: {"success": True, "location": "116.397,39.909",
                 "formatted_address": "北京市东城区协和医院"}
          失败: {"success": False, "error": "未找到该地址"}
        """
        # ① 拼装请求参数
        params = {"address": address}           # 地址文本（必填）
        if city:
            params["city"] = city               # 城市名（可选，缩小范围）

        # ② 调用底层请求
        result = self._get("/geocode/geo", params)  # 高德地理编码接口

        # ③ 解析结果：取第一个匹配项（通常最准确）
        if result["success"]:
            geos = result["data"].get("geocodes", [])  # 匹配结果数组
            if geos:
                g = geos[0]                            # 取最佳匹配
                return {
                    "success": True,
                    "location": g.get("location", ""), # "116.xxx,39.xxx" 格式
                    "formatted_address": g.get("formatted_address", ""),  # 标准化地址
                    "latency_ms": result["latency_ms"]
                }
            return {"success": False,
                    "error": "未找到该地址",            # 无匹配结果
                    "latency_ms": result["latency_ms"]}
        return result

    # ================================================================
    # 7. 逆地理编码 —— 经纬度 → 地址
    #    API: https://restapi.amap.com/v3/geocode/regeo
    # ================================================================
    def regeocode(self, location: str,           # 坐标 "lng,lat"
                  radius: int = 1000,            # 周边 POI 返回半径（米）
                  extensions: str = "base") -> dict:  # "base" 基本信息 / "all" 含周边 POI
        """
        逆地理编码 —— 将经纬度坐标转换为结构化地址

        适用场景:
          - 用户共享位置后，"这个位置是哪里？"
          - 获取坐标所属的省/市/区/街道

        返回值:
          成功: {"success": True, "formatted_address": "北京市东城区...",
                 "address_component": {"province":"北京市","city":"北京市","district":"东城区"}}
        """
        # ① 拼装参数
        params = {
            "location": location,               # 坐标（必填）
            "radius": radius,                   # 周边 POI 返回范围
            "extensions": extensions            # 返回粒度
        }

        # ② 调用底层请求
        result = self._get("/geocode/regeo", params)  # 高德逆地理编码接口

        # ③ 解析结果
        if result["success"]:
            regeo = result["data"].get("regeocode", {})  # 逆编码结果对象
            return {
                "success": True,
                "formatted_address": regeo.get("formatted_address", ""),  # 格式化地址
                "address_component": regeo.get("addressComponent", {}),   # 地址组件（省/市/区/街道）
                "pois": regeo.get("pois", []),         # 周边 POI（如"天安门广场"）
                "latency_ms": result["latency_ms"]
            }
        return result

    # ================================================================
    # 8. 天气查询
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

        # ② 调用底层请求
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
    # 9. IP 定位 —— 获取当前城市
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

        # ② 调用底层请求
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
    # 10. 复合查询 —— 医院位置 + 周边服务一站式搜索
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
                    "error": f"未找到医院: {hospital_name}"}

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
# 工具函数 —— 不依赖类实例的纯函数
# ================================================================
def _fmt_poi(p: dict) -> dict:
    """
    高德 POI 数据精简 —— 从原始 30+ 字段中提取最常用的 10 个字段

    为什么需要精简？
      - 高德返回的原始 POI 含大量冗余字段（如 business_area、indoor_map 等）
      - 精简后传给 LLM 可减少 token 消耗
      - 前端展示也更清晰
    """
    return {
        "id": p.get("id", ""),                # POI 唯一 ID（可用于详情查询）
        "name": p.get("name", ""),            # 地点名称（如"北京协和医院"）
        "type": p.get("type", ""),            # 分类描述（如"综合医院;三甲医院"）
        "address": p.get("address", ""),      # 详细地址
        "location": p.get("location", ""),    # 经纬度坐标 "lng,lat"
        "tel": p.get("tel", ""),              # 联系电话（可能为空或多号）
        "distance": p.get("distance", ""),    # 距离中心点（米），仅周边搜索有效
        "biz_ext": p.get("biz_ext", {}),      # 扩展信息（评分/均价 — 保留原对象）
        "rating": p.get("biz_ext", {}).get("rating", ""),  # 评分（如"4.5"）
        "cost": p.get("biz_ext", {}).get("cost", ""),      # 人均消费（元）
        "photos": [ph.get("url", "")           # 环境照片 URL 列表（最多 3 张）
                   for ph in (p.get("photos", []) or [])][:3],
    }


# ================================================================
# 全局单例 —— 整个应用共享同一个 httpx 客户端（连接池复用）
# ================================================================
_amap: Optional[AmapClient] = None  # 模块级私有变量，存储唯一实例


def get_amap_client() -> AmapClient:
    """
    获取高德地图客户端单例

    为什么使用单例？
      - httpx.Client 内部维护连接池，复用可减少 TCP 握手开销
      - 避免每次请求都创建/销毁客户端对象
      - 线程安全：httpx.Client 本身是线程安全的
    """
    global _amap                         # 声明要修改模块级变量
    if _amap is None:                    # 首次调用时创建
        _amap = AmapClient()             # 初始化客户端（读取配置、创建连接池）
    return _amap                         # 返回已有实例
