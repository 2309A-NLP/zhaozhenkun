"""该文件用于接入真实地图路线规划接口并输出路径摘要。"""

# 导入系统环境变量模块，用于读取可配置的公网接口地址。
import os
# 导入正则模块，用于从问题中抽取起点终点与出行方式。
import re

# 导入公共 HTTP 客户端，便于访问地理编码与路线接口。
from development.services.http_client import HttpJsonClient

# 定义常见提问前缀，用于清理路线抽取前的噪声文本。
HELPER_PREFIXES = (
    "帮我规划一下",
    "帮我规划",
    "帮我查一下",
    "请帮我规划",
    "请帮我",
    "帮我",
    "请",
    "麻烦",
)

# 定义导航动作到中文描述的映射，便于格式化步骤文本。
MANEUVER_TEXT_MAP = {
    "depart": "出发",
    "arrive": "到达目的地",
    "turn": "转向",
    "new name": "继续前行",
    "merge": "并入道路",
    "ramp": "驶入匝道",
    "roundabout": "通过环岛",
    "fork": "在岔路保持方向",
    "end of road": "在道路尽头转向",
    "continue": "继续前行",
}


# 定义路线规划服务，用于访问公开地理编码与地图路线接口。
class RouteService:
    # 初始化路线规划服务，并注入底层 HTTP 客户端。
    def __init__(self, http_client: HttpJsonClient | None = None) -> None:
        # 保存 HTTP 客户端对象，便于复用连接。
        self.http_client = http_client or HttpJsonClient()
        # 读取可配置的地理编码接口基础地址。
        self.nominatim_base_url = os.getenv("NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org").rstrip("/")
        # 读取可配置的路线规划接口基础地址。
        self.osrm_base_url = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org").rstrip("/")

    # 根据用户问题规划真实路线并返回摘要文本。
    def plan_route(self, query: str) -> str:
        # 从问题中抽取起点与终点名称。
        origin_name, destination_name = self.extract_route_points(query)
        # 若起终点识别失败，则提示用户补充结构化表达。
        if not origin_name or not destination_name:
            return "未识别到明确起点和终点，请使用“从A到B怎么走”的表达方式。"
        # 从问题中识别出行方式。
        mode = self.extract_mode(query)
        # 查询起点的地理编码结果。
        origin_place = self._geocode(origin_name)
        # 查询终点的地理编码结果。
        destination_place = self._geocode(destination_name)
        # 若起点无法定位，则直接返回提示。
        if not origin_place:
            return f"未查询到起点“{origin_name}”的公开地理编码结果。"
        # 若终点无法定位，则直接返回提示。
        if not destination_place:
            return f"未查询到终点“{destination_name}”的公开地理编码结果。"
        # 根据两端坐标请求真实路线数据。
        route = self._route(mode, origin_place, destination_place)
        # 若路线接口没有可用结果，则给出明确说明。
        if not route:
            return "已识别起终点，但暂时未获取到可用路线结果。"
        # 将路线结果格式化成中文摘要文本。
        return self._format_route(mode, origin_place, destination_place, route)

    # 从问题中抽取起点与终点文本。
    def extract_route_points(self, query: str) -> tuple[str, str]:
        # 先清理提问前缀与句末标点。
        cleaned = self._strip_prefixes(query.strip()).rstrip("？?。！!")
        # 定义常见路线提问模式集合。
        patterns = [
            r"从(?P<origin>.+?)到(?P<destination>.+?)(?:怎么走|怎么去|路线|路程|导航|开车|打车|步行|骑行|最快路线|最短路线)?$",
            r"(?P<origin>.+?)到(?P<destination>.+?)(?:怎么走|怎么去|路线|路程|导航|开车|打车|步行|骑行|最快路线|最短路线)$",
        ]
        # 依次尝试匹配提问模式。
        for pattern in patterns:
            # 在文本中执行正则匹配。
            match = re.search(pattern, cleaned)
            # 若匹配成功，则返回标准化后的起终点。
            if match:
                origin = self._normalize_endpoint(match.group("origin"))
                destination = self._normalize_endpoint(match.group("destination"))
                return origin, destination
        # 若没有匹配成功，则返回空起终点。
        return "", ""

    # 从问题中识别最适合的路线出行方式。
    def extract_mode(self, query: str) -> str:
        # 保存便于匹配的低噪声文本。
        text = query.strip()
        # 若问题包含步行语义，则返回步行模式。
        if "步行" in text:
            return "walking"
        # 若问题包含骑行语义，则返回骑行模式。
        if "骑行" in text or "骑车" in text:
            return "cycling"
        # 默认使用驾车模式，适配公开 OSRM 服务。
        return "driving"

    # 调用 Nominatim 地理编码接口获取地点坐标。
    def _geocode(self, place_name: str) -> dict[str, object] | None:
        # 生成一组更稳妥的地点查询候选词。
        queries = [place_name, f"{place_name}, China"]
        # 若地点中带“站”，则补充更适合车站检索的候选表达。
        if "站" in place_name:
            queries.append(f"{place_name} railway station")
        # 依次尝试每个候选词，直到找到可用地理编码结果。
        for query in queries:
            # 尝试访问地理编码接口。
            try:
                # 请求 Nominatim 的公开地理编码结果。
                data = self.http_client.get_json(
                    f"{self.nominatim_base_url}/search",
                    {
                        "q": query,
                        "format": "jsonv2",
                        "limit": 1,
                        "accept-language": "zh-CN",
                    },
                )
            # 若网络异常，则继续尝试下一个候选词。
            except Exception:
                continue
            # 若响应是非空列表，则直接返回首个最相关地点对象。
            if isinstance(data, list) and data:
                return data[0]
        # 当所有候选词都失败时，返回空值。
        return None

    # 调用 OSRM 路线接口获取真实路线数据。
    def _route(self, mode: str, origin: dict[str, object], destination: dict[str, object]) -> dict[str, object] | None:
        # 提取起点经纬度并转换为字符串。
        origin_lon = str(origin.get("lon", "")).strip()
        # 提取起点纬度并转换为字符串。
        origin_lat = str(origin.get("lat", "")).strip()
        # 提取终点经纬度并转换为字符串。
        destination_lon = str(destination.get("lon", "")).strip()
        # 提取终点纬度并转换为字符串。
        destination_lat = str(destination.get("lat", "")).strip()
        # 若四个坐标字段任一为空，则无法继续请求路线。
        if not all((origin_lon, origin_lat, destination_lon, destination_lat)):
            return None
        # 组合 OSRM 的坐标串参数。
        coordinates = f"{origin_lon},{origin_lat};{destination_lon},{destination_lat}"
        # 尝试请求公开路线服务。
        try:
            # 请求 OSRM 路线 JSON 数据。
            data = self.http_client.get_json(
                f"{self.osrm_base_url}/route/v1/{mode}/{coordinates}",
                {
                    "overview": "false",
                    "steps": "true",
                    "alternatives": "false",
                    "annotations": "false",
                },
            )
        # 若请求异常，则返回空值。
        except Exception:
            return None
        # 读取路线数组。
        routes = data.get("routes", []) if isinstance(data, dict) else []
        # 若没有路线结果，则返回空值。
        if not routes:
            return None
        # 返回首条最优路线。
        return routes[0]

    # 将路线结果格式化为简洁清晰的中文摘要。
    def _format_route(self, mode: str, origin: dict[str, object], destination: dict[str, object], route: dict[str, object]) -> str:
        # 读取路线总距离，单位为米。
        distance_meters = float(route.get("distance", 0))
        # 读取路线总时长，单位为秒。
        duration_seconds = float(route.get("duration", 0))
        # 将总距离转换为公里并保留一位小数。
        distance_km = distance_meters / 1000
        # 将总时长转换为分钟并四舍五入。
        duration_minutes = round(duration_seconds / 60)
        # 读取第一段路段信息。
        legs = route.get("legs", [])
        # 读取步骤数组，若为空则回退为空列表。
        steps = legs[0].get("steps", []) if legs else []
        # 构造路线摘要开头行。
        lines = [
            f"路线规划：{self._display_name(origin)} → {self._display_name(destination)}",
            f"出行方式：{self._mode_label(mode)}，全程约 {distance_km:.1f} 公里，预计 {duration_minutes} 分钟。",
        ]
        # 若请求中包含公交或地铁语义，则提示当前接口能力边界。
        if any(keyword in f"{self._display_name(origin)} {self._display_name(destination)}" for keyword in ("公交", "地铁")):
            lines.append("当前接入的是公开道路路线服务，返回结果以道路导航为主，不含公交换乘方案。")
        # 提取前几步关键导航信息。
        key_steps = self._format_steps(steps[:4])
        # 若存在关键步骤，则追加到输出中。
        if key_steps:
            lines.append("关键步骤：")
            lines.extend(key_steps)
        # 返回拼接后的路线摘要文本。
        return "\n".join(lines)

    # 将步骤列表格式化为简洁导航文本。
    def _format_steps(self, steps: list[dict[str, object]]) -> list[str]:
        # 准备格式化后的步骤文本列表。
        lines: list[str] = []
        # 遍历步骤数组并逐条格式化。
        for index, step in enumerate(steps):
            # 提取动作类型信息。
            maneuver = step.get("maneuver", {}) if isinstance(step, dict) else {}
            # 提取动作主类型。
            step_type = str(maneuver.get("type", "continue")).strip()
            # 提取道路名称。
            road_name = str(step.get("name", "")).strip() or "未命名道路"
            # 提取当前步骤距离。
            step_distance = round(float(step.get("distance", 0)))
            # 将动作类型映射为中文标签。
            action = MANEUVER_TEXT_MAP.get(step_type, step_type)
            # 写入格式化后的步骤描述。
            lines.append(f"{index + 1}. {action}，沿 {road_name} 前行约 {step_distance} 米。")
        # 返回步骤文本列表。
        return lines

    # 移除问题开头的提问前缀，保留更纯净的路线语义。
    def _strip_prefixes(self, text: str) -> str:
        # 在前缀命中时循环剥离，直到没有前缀为止。
        while True:
            # 记录本轮是否执行了剥离动作。
            stripped = False
            # 遍历所有常见前缀。
            for prefix in HELPER_PREFIXES:
                # 若文本以当前前缀开头，则移除该前缀。
                if text.startswith(prefix):
                    text = text[len(prefix):].strip()
                    stripped = True
                    break
            # 若本轮没有继续剥离，则结束循环。
            if not stripped:
                return text

    # 标准化起点或终点文本，去掉噪声后缀。
    def _normalize_endpoint(self, text: str) -> str:
        # 去除首尾空白与句末常见标点。
        normalized = text.strip().rstrip("，,。？?")
        # 去掉路线问句里残留的说明词。
        normalized = re.sub(r"(怎么走|怎么去|路线|路程|导航|开车|打车|步行|骑行)$", "", normalized).strip()
        # 返回标准化后的端点文本。
        return normalized

    # 获取适合展示的人类可读地点名称。
    def _display_name(self, place: dict[str, object]) -> str:
        # 优先使用 display_name，若太长则退回 name 字段。
        display_name = str(place.get("display_name", "")).strip()
        # 读取地点名称字段。
        name = str(place.get("name", "")).strip()
        # 若存在较短名称，则优先用于展示。
        if name:
            return name
        # 否则返回展示名称或默认占位文本。
        return display_name or "未知地点"

    # 将出行方式英文值转换为中文标签。
    def _mode_label(self, mode: str) -> str:
        # 为步行模式返回中文名称。
        if mode == "walking":
            return "步行"
        # 为骑行模式返回中文名称。
        if mode == "cycling":
            return "骑行"
        # 默认返回驾车名称。
        return "驾车"
