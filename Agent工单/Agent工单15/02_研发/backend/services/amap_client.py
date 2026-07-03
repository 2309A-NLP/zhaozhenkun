"""
================================================================================
文件名:   amap_client.py
功能:     高德地图 Web 服务 API 客户端 —— 兼容性汇总入口
          —— 聚合 amap_core / amap_routes / amap_weather 三个子模块，
            对外提供与原版完全一致的 import 接口，确保旧代码零改动兼容。
所属项目:  医疗智能体-影像分析系统
工单编号:  人工智能 NLP-Agent 数字人项目-医疗智能体-MCP V1.0
调用方:    api/map.py（地图 API 路由层）
          mcp_server/mcp_serve.py（MCP Server 工具层）
依赖:      services.amap_core（AmapClient 基类 + _fmt_poi + get_amap_client）
          services.amap_routes（路线规划 + 地理编码 猴子补丁注入）
          services.amap_weather（天气/IP 定位/医院复合查询 猴子补丁注入）

子模块说明:
  amap_core.py    —— AmapClient.__init__, _get(), search_poi(), search_around(),
                     _fmt_poi(), get_amap_client(), 全局单例 _amap
  amap_routes.py  —— direction_driving(), direction_walking(), direction_transit(),
                     geocode(), regeocode()（猴子补丁注入到 AmapClient）
  amap_weather.py —— weather(), ip_location(), search_hospital_with_services()
                     （猴子补丁注入到 AmapClient）

兼容性保证:
  旧代码:  from services.amap_client import AmapClient, get_amap_client
  新代码:  同上，无需任何修改

高德 API 文档: https://lbs.amap.com/api/webservice/summary
================================================================================
"""
# ① 导入核心模块 —— 提供 AmapClient 类、_fmt_poi 工具、get_amap_client 单例
from services.amap_core import (       # 从 amap_core 子模块导入：
    AmapClient,                        #   AmapClient 类（含 __init__ / _get / search_poi / search_around）
    get_amap_client,                   #   单例工厂函数
    _fmt_poi,                          #   POI 精简工具
    _amap,                             #   模块级单例变量
)

# ② 导入路线模块 —— 触发猴子补丁注入（direction_driving / direction_walking / direction_transit / geocode / regeocode）
import services.amap_routes  # noqa: F401 —— 导入时自动将路线方法绑定到 AmapClient

# ③ 导入天气模块 —— 触发猴子补丁注入（weather / ip_location / search_hospital_with_services）
import services.amap_weather  # noqa: F401 —— 导入时自动将天气/定位/复合查询方法绑定到 AmapClient

# ④ 对外暴露的公共 API（与原版完全一致）
__all__ = [                           # 声明本模块的公共接口：
    "AmapClient",                     #   高德地图客户端类（完整带所有方法）
    "get_amap_client",                #   单例工厂函数
    "_fmt_poi",                       #   POI 格式化工具
]
