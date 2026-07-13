"""该文件用于实现文旅领域技能，包括景点、天气与路线规划能力。"""

# 导入技能上下文与结果类型，统一输入输出。
from development.core.models import SkillContext
from development.core.models import SkillResult
# 导入路线服务，用于查询真实导航结果。
from development.services.route_service import RouteService
# 导入搜索服务，用于查询景点公开信息。
from development.services.search_service import SearchService
# 导入天气服务，用于查询真实天气数据。
from development.services.weather_service import WeatherService
# 导入技能基类，便于复用统一接口。
from development.skills.base import BaseSkill


# 定义景点信息技能，用于给出景点联网查询结果。
class AttractionInfoSkill(BaseSkill):
    # 初始化景点信息技能对象，并注入搜索服务依赖。
    def __init__(self, search_service: SearchService) -> None:
        # 调用父类并声明文旅领域。
        super().__init__(name="skill_attraction_info", domain="tourism")
        # 保存搜索服务对象。
        self.search_service = search_service

    # 执行景点信息生成逻辑。
    def run(self, context: SkillContext) -> SkillResult:
        # 组合更适合景点搜索的查询语句。
        search_query = f"{context.query} 景点 门票 开放时间 交通"
        # 调用真实搜索服务获取公开结果。
        content = self.search_service.search(search_query)
        # 返回技能执行结果。
        return SkillResult(name=self.name, domain=self.domain, content=content)


# 定义天气检查技能，用于给出真实出行天气结果。
class WeatherCheckSkill(BaseSkill):
    # 初始化天气检查技能对象，并注入天气服务依赖。
    def __init__(self, weather_service: WeatherService) -> None:
        # 调用父类并声明文旅领域。
        super().__init__(name="skill_weather_check", domain="tourism")
        # 保存天气服务对象。
        self.weather_service = weather_service

    # 执行天气检查说明逻辑。
    def run(self, context: SkillContext) -> SkillResult:
        # 调用真实天气服务获取未来三日天气。
        content = self.weather_service.get_forecast(context.query)
        # 返回技能执行结果。
        return SkillResult(name=self.name, domain=self.domain, content=content)


# 定义路线规划技能，用于生成真实出行路径建议。
class RoutePlanningSkill(BaseSkill):
    # 初始化路线规划技能对象，并注入路线服务依赖。
    def __init__(self, route_service: RouteService) -> None:
        # 调用父类并声明文旅领域。
        super().__init__(name="skill_route_planning", domain="tourism")
        # 保存路线服务对象。
        self.route_service = route_service

    # 执行路线规划说明逻辑。
    def run(self, context: SkillContext) -> SkillResult:
        # 调用真实路线服务获取导航摘要。
        content = self.route_service.plan_route(context.query)
        # 返回技能执行结果。
        return SkillResult(name=self.name, domain=self.domain, content=content)
