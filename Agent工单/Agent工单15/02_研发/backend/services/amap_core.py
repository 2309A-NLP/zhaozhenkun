"""
================================================================================
文件名:   amap_core.py
功能:     高德地图 Web 服务 API 客户端 —— 核心模块
          —— 封装高德地图 REST API，提供基础类定义、底层请求、POI 搜索能力
所属项目:  医疗智能体-影像分析系统
工单编号:  人工智能 NLP-Agent 数字人项目-医疗智能体-MCP V1.0
调用方:    api/map.py（地图 API 路由层）
          mcp_server/mcp_serve.py（MCP Server 工具层）
依赖:      config.py（AMAP_API_KEY, AMAP_BASE_URL, AMAP_API_TIMEOUT）
          httpx（HTTP 客户端库）

类结构（本文件包含）:
  AmapClient（核心骨架）
    ├── __init__()                  # 初始化 API Key / BaseURL / httpx 客户端
    ├── _get(path, params)          # 【底层】封装 GET 请求，注入 key + 异常处理
    ├── search_poi()                # 关键词地点搜索（医院/酒店/餐厅）
    └── search_around()             # 周边 POI 搜索（以坐标为中心）

  其余方法由 amap_routes.py 和 amap_weather.py 以猴子补丁方式注入，
  确保所有 import 路径兼容原始代码。

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
from config import AMAP_API_KEY, AMAP_BASE_URL, AMAP_API_TIMEOUT  # 高德 API 密钥/地址/超时

# 创建本模块的 logger，后续所有日志通过 _log.info/warning/error 输出
_log = logging.getLogger("medical_agent.amap")  # 统一使用 "medical_agent.amap" 命名空间


class AmapClient:
    """
    高德地图 Web 服务 API 客户端

    所有方法均返回统一的 dict 格式:
      成功: {"success": True,  "data": ..., "latency_ms": 123.45}
      失败: {"success": False, "error": "错误描述", "latency_ms": 123.45}

    支持的功能:
      - POI 搜索（关键词 / 周边）         ← 本文件
      - 路线规划（驾车 / 步行 / 公交）     ← amap_routes.py 注入
      - 地理编码 / 逆地理编码             ← amap_routes.py 注入
      - 天气 / IP 定位                   ← amap_weather.py 注入
      - 医院周边一站式复合查询            ← amap_weather.py 注入
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
