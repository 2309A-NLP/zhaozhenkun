"""该文件用于测试领域识别与技能路由逻辑。"""

# 导入单元测试框架，用于编写基础断言。
import unittest

# 导入待测试的领域识别与技能选择函数。
from development.core.router import detect_domain
from development.core.router import select_skills


# 定义路由测试类，用于覆盖主要领域分流场景。
class RouterTestCase(unittest.TestCase):
    # 测试文旅问题是否能正确识别到 tourism 领域。
    def test_detect_tourism_domain(self) -> None:
        # 执行领域识别并获取结果。
        domain = detect_domain("请帮我规划北京三日旅游路线和景点")
        # 校验领域识别结果是否符合预期。
        self.assertEqual(domain, "tourism")

    # 测试教育问题是否能正确识别到 education 领域。
    def test_detect_education_domain(self) -> None:
        # 执行领域识别并获取结果。
        domain = detect_domain("请讲解二次函数知识点并给我题目")
        # 校验领域识别结果是否符合预期。
        self.assertEqual(domain, "education")

    # 测试医疗问题是否能正确识别到 medical 领域。
    def test_detect_medical_domain(self) -> None:
        # 执行领域识别并获取结果。
        domain = detect_domain("我发烧咳嗽应该注意什么")
        # 校验领域识别结果是否符合预期。
        self.assertEqual(domain, "medical")

    # 测试文旅问题是否会被分配到景点与路线技能。
    def test_select_tourism_skills(self) -> None:
        # 执行技能选择逻辑并获取技能列表。
        skills = select_skills("tourism", "帮我查询杭州西湖天气并规划路线")
        # 校验文旅核心技能是否已被正确注入。
        self.assertIn("skill_attraction_info", skills)
        # 校验路线规划技能是否已被正确注入。
        self.assertIn("skill_route_planning", skills)
        # 校验天气技能是否已被正确注入。
        self.assertIn("skill_weather_check", skills)

    # 测试路线导航问题是否会被识别为文旅领域。
    def test_detect_route_query_as_tourism(self) -> None:
        # 执行领域识别并获取结果。
        domain = detect_domain("请帮我从北京站到故宫怎么走")
        # 校验路线类问题应分流到文旅领域。
        self.assertEqual(domain, "tourism")


# 在脚本被直接执行时启动单元测试。
if __name__ == "__main__":
    # 运行当前文件内的所有测试用例。
    unittest.main()
