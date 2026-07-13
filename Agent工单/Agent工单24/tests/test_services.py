"""该文件用于测试真实联网服务的核心解析与降级逻辑。"""

# 导入单元测试框架，用于编写解析层断言。
import unittest

# 导入药品查询服务，便于测试药名抽取与文本格式化。
from development.services.drug_service import DrugService
# 导入路线规划服务，便于测试路线抽取与格式化逻辑。
from development.services.route_service import RouteService
# 导入搜索服务，便于测试 HTML 清理与主题展平。
from development.services.search_service import SearchService
# 导入天气服务，便于测试地点抽取与天气格式化。
from development.services.weather_service import WeatherService


# 定义搜索服务测试类，用于验证结果清洗逻辑。
class SearchServiceTestCase(unittest.TestCase):
    # 测试 HTML 片段是否能被正确清理为纯文本。
    def test_strip_html(self) -> None:
        # 初始化搜索服务对象。
        service = SearchService()
        # 执行 HTML 清理逻辑。
        cleaned = service._strip_html("<b>北京</b> 是中国的首都")
        # 校验清理结果是否符合预期。
        self.assertEqual(cleaned, "北京 是中国的首都")

    # 测试关联主题嵌套结构是否能被正确展平。
    def test_flatten_related_topics(self) -> None:
        # 初始化搜索服务对象。
        service = SearchService()
        # 构造模拟的嵌套主题数据。
        items = [{"Topics": [{"Text": "A", "FirstURL": "u1"}]}, {"Text": "B", "FirstURL": "u2"}]
        # 执行主题展平逻辑。
        flattened = service._flatten_related_topics(items)
        # 校验展平后的条目数量。
        self.assertEqual(len(flattened), 2)


# 定义天气服务测试类，用于验证地点抽取与结果格式化。
class WeatherServiceTestCase(unittest.TestCase):
    # 测试是否能从天气提问中正确抽取地点。
    def test_extract_location(self) -> None:
        # 初始化天气服务对象。
        service = WeatherService()
        # 从问题中抽取地点名称。
        location = service.extract_location("帮我查一下北京天气")
        # 校验地点抽取结果。
        self.assertEqual(location, "北京")

    # 测试天气数据是否能被格式化为可读摘要。
    def test_format_forecast(self) -> None:
        # 初始化天气服务对象。
        service = WeatherService()
        # 构造模拟地点信息。
        place = {"name": "北京", "country": "中国"}
        # 构造模拟天气结果。
        daily = {
            "time": ["2026-07-13"],
            "weather_code": [0],
            "temperature_2m_max": [30],
            "temperature_2m_min": [22],
            "precipitation_probability_max": [10],
        }
        # 执行天气格式化逻辑。
        content = service._format_forecast(place, daily)
        # 校验结果中是否包含地点名称。
        self.assertIn("北京", content)
        # 校验结果中是否包含天气描述。
        self.assertIn("晴朗", content)


# 定义药品服务测试类，用于验证药名抽取与记录格式化。
class DrugServiceTestCase(unittest.TestCase):
    # 测试是否能从副作用查询中识别药品名称。
    def test_extract_drug_name(self) -> None:
        # 初始化药品服务对象。
        service = DrugService()
        # 从问题中抽取药名。
        drug_name = service.extract_drug_name("布洛芬有哪些副作用")
        # 校验药名抽取结果是否正确。
        self.assertEqual(drug_name, "布洛芬")

    # 测试中文常见药名是否能被归一化为英文通用名。
    def test_normalize_drug_name(self) -> None:
        # 初始化药品服务对象。
        service = DrugService()
        # 执行药名归一化逻辑。
        normalized = service.normalize_drug_name("布洛芬")
        # 校验归一化结果是否符合预期。
        self.assertEqual(normalized, "ibuprofen")

    # 测试药品记录是否能被格式化为结构化摘要。
    def test_format_record(self) -> None:
        # 初始化药品服务对象。
        service = DrugService()
        # 构造模拟药品标签记录。
        record = {
            "openfda": {"brand_name": ["Advil"], "generic_name": ["Ibuprofen"]},
            "indications_and_usage": ["Relieves pain."],
            "warnings": ["Use with care."],
        }
        # 执行药品记录格式化逻辑。
        content = service._format_record("布洛芬", record)
        # 校验结果中是否包含品牌名字段。
        self.assertIn("Advil", content)
        # 校验结果中是否包含适应症字段。
        self.assertIn("Relieves pain.", content)


# 定义路线服务测试类，用于验证起终点抽取与步骤格式化。
class RouteServiceTestCase(unittest.TestCase):
    # 测试是否能从路线提问中正确抽取起点与终点。
    def test_extract_route_points(self) -> None:
        # 初始化路线服务对象。
        service = RouteService()
        # 从问题中抽取起点与终点。
        origin, destination = service.extract_route_points("请帮我从北京站到故宫怎么走")
        # 校验起点抽取结果。
        self.assertEqual(origin, "北京站")
        # 校验终点抽取结果。
        self.assertEqual(destination, "故宫")

    # 测试路线步骤是否能被格式化为可读导航文本。
    def test_format_steps(self) -> None:
        # 初始化路线服务对象。
        service = RouteService()
        # 构造模拟步骤数组。
        steps = [{"maneuver": {"type": "depart"}, "name": "长安街", "distance": 500}]
        # 执行步骤格式化逻辑。
        lines = service._format_steps(steps)
        # 校验首条结果中是否包含道路名称。
        self.assertIn("长安街", lines[0])
        # 校验首条结果中是否包含动作描述。
        self.assertIn("出发", lines[0])


# 在脚本被直接执行时启动单元测试。
if __name__ == "__main__":
    # 运行当前文件内的所有测试用例。
    unittest.main()
