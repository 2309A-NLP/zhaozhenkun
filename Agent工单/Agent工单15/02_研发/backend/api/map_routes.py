"""
================================================================================
文件名:   api/map_routes.py
功能:     地图服务 API 路由层（FastAPI Router）
          —— 医院位置相关的出行/住宿/餐饮查询 HTTP 端点
          —— 对接高德地图 REST API（不含 chat 端点，chat 拆分至 map_chat.py）
所属项目:  医疗智能体-影像分析系统
工单编号:  人工智能 NLP-Agent 数字人项目-医疗智能体-MCP V1.0
调用方:    main.py（FastAPI 应用注册）
           frontend/js/map.js（前端 AJAX 调用）
依赖:      services/amap_client.py（高德地图 API 客户端）

路由列表（7 个端点）:
  POST /api/map/search              关键词地点搜索（医院/酒店/餐厅）
  POST /api/map/nearby              周边 POI 搜索（住宿/餐饮/交通）
  POST /api/map/directions          路线规划（驾车/步行/公交）
  POST /api/map/geocode             地址 → 经纬度
  POST /api/map/regeocode           经纬度 → 地址
  POST /api/map/hospital-services   医院周边一站式查询
  POST /api/map/ip-location         IP 定位
================================================================================
"""
import logging    # logging.getLogger —— 模块级别日志
from fastapi import APIRouter                         # FastAPI 路由器（用于组织 API 端点）
from fastapi.responses import JSONResponse            # JSONResponse —— 统一返回 JSON 格式
from pydantic import BaseModel, Field                 # Pydantic 数据校验模型
from services.amap_client import get_amap_client      # 高德地图客户端单例

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
