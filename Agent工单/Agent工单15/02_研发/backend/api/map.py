"""
================================================================================
文件名:   api/map.py
功能:     地图服务 API —— 兼容性重导出模块
          —— 所有实现已拆分至 map_routes.py / map_chat.py / map_format.py
          —— 保留此文件以确保原有 import 路径不受影响
所属项目:  医疗智能体-影像分析系统
================================================================================
"""
# 路由层 —— 端点 1~7（search / nearby / directions / geocode / regeocode / hospital-services / ip-location）
from api.map_routes import (                  # noqa: F401
    router as _base_router,
    router,
    SearchRequest,
    AroundRequest,
    DirectionRequest,
    GeocodeRequest,
    search_poi,
    search_nearby,
    get_directions,
    geocode,
    regeocode,
    hospital_services,
    ip_location,
)

# 对话端点 —— 端点 8（/chat，三步流水线：意图解析 → API 调用 → 回复整理）
# 注意: map_chat 定义了自己的 router，需要将其路由合并到主 router 中
from api.map_chat import (                    # noqa: F401
    MapChatRequest,
    MAP_SYSTEM,
    map_chat,
    router as _chat_router,
)
router.include_router(_chat_router)           # 合并 chat 路由到主 router

# 格式化工具函数
from api.map_format import (                  # noqa: F401
    fmt_for_prompt as _fmt_for_prompt,
    fmt_dist as _fmt_dist,
    fmt_time as _fmt_time,
)
