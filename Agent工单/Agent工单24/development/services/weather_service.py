"""该文件用于接入真实天气接口并输出三日天气摘要。"""

# 导入正则模块，用于从问题中抽取地点名称。
import re

# 导入公共 HTTP 客户端，便于访问天气与地理编码接口。
from development.services.http_client import HttpJsonClient

# 定义天气代码映射表，用于把 Open-Meteo 代码转成中文描述。
WEATHER_CODE_MAP = {
    0: "晴朗",
    1: "大部晴朗",
    2: "局部多云",
    3: "阴天",
    45: "有雾",
    48: "有雾并伴随霜冻",
    51: "小毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    71: "小雪",
    80: "阵雨",
    95: "雷暴",
}

# 定义常见提问前缀，用于清理地点抽取前的噪声文本。
HELPER_PREFIXES = (
    "帮我查询一下",
    "帮我查一下",
    "请查询一下",
    "请查一下",
    "查询一下",
    "查一下",
    "看一下",
    "看下",
    "搜一下",
    "帮我",
    "请",
    "麻烦",
)


# 定义天气服务，用于把地名查询转为可读天气结果。
class WeatherService:
    # 初始化天气服务，并注入底层 HTTP 客户端。
    def __init__(self, http_client: HttpJsonClient | None = None) -> None:
        # 保存 HTTP 客户端对象，便于复用连接。
        self.http_client = http_client or HttpJsonClient()

    # 根据用户问题获取真实三日天气摘要。
    def get_forecast(self, query: str) -> str:
        # 从用户问题中尽量抽取地点名称。
        location_name = self.extract_location(query)
        # 若未抽取到地点，则引导用户补充城市信息。
        if not location_name:
            return "未识别到明确地点，请在问题中包含城市或景点名称。"
        # 根据地点名称查询经纬度信息。
        place = self._geocode(location_name)
        # 若未找到对应地点，则返回明确提示。
        if not place:
            return f"未查询到“{location_name}”对应的公开地理编码结果。"
        # 根据经纬度查询未来三天天气数据。
        daily = self._forecast(place["latitude"], place["longitude"])
        # 若天气接口未返回有效数据，则给出失败提示。
        if not daily:
            return f"已定位到“{place['name']}”，但暂时未获取到天气数据。"
        # 将天气 JSON 结果格式化为可读摘要文本。
        return self._format_forecast(place, daily)

    # 从问题文本中抽取城市或景点名称。
    def extract_location(self, query: str) -> str:
        # 先清理常见提问前缀，减少地点抽取误判。
        cleaned = self._strip_prefixes(query.strip())
        # 定义多组常见中文地点提问模式。
        patterns = [
            r"([一-龥A-Za-z]{2,20}?)(?:的)?(?:天气|气温|温度)",
            r"去([一-龥A-Za-z]{2,20}?)",
            r"到([一-龥A-Za-z]{2,20}?)",
            r"在([一-龥A-Za-z]{2,20}?)(?:玩|旅游|出行|旅行)",
        ]
        # 按顺序尝试匹配地点模式。
        for pattern in patterns:
            # 在问题中搜索首个匹配地点。
            match = re.search(pattern, cleaned)
            # 若成功匹配，则返回清理后的地点文本。
            if match:
                return self._normalize_candidate(match.group(1))
        # 若未命中模式，则返回空字符串。
        return ""

    # 调用地理编码接口，把地点名称转换为经纬度信息。
    def _geocode(self, location_name: str) -> dict[str, object] | None:
        # 尝试访问真实地理编码接口。
        try:
            # 请求 Open-Meteo 地理编码数据。
            data = self.http_client.get_json(
                "https://geocoding-api.open-meteo.com/v1/search",
                {
                    "name": location_name,
                    "count": 1,
                    "language": "zh",
                    "format": "json",
                },
            )
        # 若网络异常，则返回空结果。
        except Exception:
            return None
        # 提取结果数组。
        results = data.get("results", [])
        # 若结果为空，则返回空值。
        if not results:
            return None
        # 返回首个最相关的地点结果。
        return results[0]

    # 调用天气接口，获取未来三日天气信息。
    def _forecast(self, latitude: object, longitude: object) -> dict[str, list[object]] | None:
        # 尝试访问真实天气接口。
        try:
            # 请求 Open-Meteo 未来三日天气数据。
            data = self.http_client.get_json(
                "https://api.open-meteo.com/v1/forecast",
                {
                    "latitude": latitude,
                    "longitude": longitude,
                    "timezone": "auto",
                    "forecast_days": 3,
                    "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                },
            )
        # 若网络异常，则返回空值。
        except Exception:
            return None
        # 返回日级天气数据字典。
        return data.get("daily")

    # 把天气结果格式化为多行中文摘要。
    def _format_forecast(self, place: dict[str, object], daily: dict[str, list[object]]) -> str:
        # 读取日期数组。
        dates = daily.get("time", [])
        # 读取最高温数组。
        max_values = daily.get("temperature_2m_max", [])
        # 读取最低温数组。
        min_values = daily.get("temperature_2m_min", [])
        # 读取降水概率数组。
        rain_values = daily.get("precipitation_probability_max", [])
        # 读取天气代码数组。
        code_values = daily.get("weather_code", [])
        # 先构造地点标题行。
        lines = [f"地点：{place.get('name')}，{place.get('country', '')}"]
        # 遍历三日天气数据并生成摘要行。
        for index, date_text in enumerate(dates):
            # 按下标提取当天天气代码。
            code = int(code_values[index]) if index < len(code_values) else -1
            # 根据天气代码映射中文描述。
            description = WEATHER_CODE_MAP.get(code, f"天气代码 {code}")
            # 提取当天最高温。
            high = max_values[index] if index < len(max_values) else "-"
            # 提取当天最低温。
            low = min_values[index] if index < len(min_values) else "-"
            # 提取当天最大降水概率。
            rain = rain_values[index] if index < len(rain_values) else "-"
            # 追加当天的可读天气摘要。
            lines.append(f"{date_text}：{description}，{low}°C~{high}°C，降水概率 {rain}%")
        # 返回拼接后的天气摘要文本。
        return "\n".join(lines)

    # 移除问题开头的提问前缀，保留更纯净的地点语义。
    def _strip_prefixes(self, text: str) -> str:
        # 在前缀命中时循环剥离，直到没有前缀为止。
        while True:
            # 记录本轮是否执行了剥离操作。
            stripped = False
            # 遍历全部常见前缀。
            for prefix in HELPER_PREFIXES:
                # 若文本以当前前缀开头，则移除该前缀。
                if text.startswith(prefix):
                    text = text[len(prefix):].strip()
                    stripped = True
                    break
            # 若本轮没有继续剥离，则结束循环。
            if not stripped:
                return text

    # 清理地点候选词前缀，避免把提问词一并当作地名。
    def _normalize_candidate(self, candidate: str) -> str:
        # 复用前缀清理逻辑去除多余引导词。
        normalized = self._strip_prefixes(candidate.strip())
        # 返回最终标准化后的地点名称。
        return normalized
