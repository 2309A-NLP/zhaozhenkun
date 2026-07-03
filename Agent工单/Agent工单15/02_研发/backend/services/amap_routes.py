"""
================================================================================
文件名:   amap_routes.py
功能:     高德地图 Web 服务 API 客户端 —— 路线规划 & 地理编码模块
          —— 以猴子补丁方式为 AmapClient 类注入路线/编码相关方法
所属项目:  医疗智能体-影像分析系统
工单编号:  人工智能 NLP-Agent 数字人项目-医疗智能体-MCP V1.0
调用方:    api/map.py（地图 API 路由层）
          mcp_server/mcp_serve.py（MCP Server 工具层）
依赖:      config.py（AMAP_API_KEY, AMAP_BASE_URL, AMAP_API_TIMEOUT）
          .amap_core（AmapClient 基类）

注入方法（猴子补丁）:
  AmapClient
    ├── direction_driving()         # 驾车路线规划
    ├── direction_walking()         # 步行路线规划
    ├── direction_transit()         # 公交换乘规划
    ├── geocode()                   # 地址 → 经纬度
    └── regeocode()                 # 经纬度 → 地址

使用方式:
  直接 import services.amap_routes 即可（导入时自动注入到 AmapClient）

高德 API 文档: https://lbs.amap.com/api/webservice/summary
================================================================================
"""
import time       # time.time() —— 用于在复合查询中计算耗时
import logging    # logging.getLogger —— 日志输出

# 从 amap_core 导入 AmapClient 类，用于猴子补丁注入方法
from services.amap_core import AmapClient, _fmt_poi  # AmapClient 基类 + POI 格式化工具

# 创建本模块的 logger
_log = logging.getLogger("medical_agent.amap")  # 沿用统一日志命名空间


# ================================================================
# 3. 驾车路线规划（注入到 AmapClient 类）
#    API: https://restapi.amap.com/v3/direction/driving
# ================================================================
def direction_driving(self, origin: str,          # 起点坐标 "lng,lat" —— 必须为"经度,纬度"格式
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

    # ② 调用底层请求（self._get 来自 AmapClient）
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
# 4. 步行路线规划（注入到 AmapClient 类）
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

    # ② 调用底层请求（self._get 来自 AmapClient）
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
# 5. 公交换乘规划（注入到 AmapClient 类）
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
    result = self._get("/direction/transit/integrated", params)  # 高德公交规划接口

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
# 6. 地理编码（注入到 AmapClient 类）
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

    # ② 调用底层请求（self._get 来自 AmapClient）
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
# 7. 逆地理编码（注入到 AmapClient 类）
#    API: https://restapi.amap.com/v3/geocode/regeo
# ================================================================
def regeocode(self, location: str,           # 坐标 "lng,lat" —— 必须为"经度,纬度"格式
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

    # ② 调用底层请求（self._get 来自 AmapClient）
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
# 猴子补丁注入 —— 将上述方法绑定到 AmapClient 类上
# ================================================================
AmapClient.direction_driving = direction_driving  # 注入驾车路线规划方法
AmapClient.direction_walking = direction_walking  # 注入步行路线规划方法
AmapClient.direction_transit = direction_transit  # 注入公交换乘规划方法
AmapClient.geocode = geocode                      # 注入地理编码方法
AmapClient.regeocode = regeocode                  # 注入逆地理编码方法
