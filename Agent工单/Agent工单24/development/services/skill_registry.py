"""该文件用于注册全部技能对象，并按名称提供统一查找能力。"""

# 导入记忆仓库，用于向记忆技能注入依赖。
from development.core.memory import JsonMemoryStore
# 导入外部服务实现，用于给技能注入真实联网能力。
from development.services.drug_service import DrugService
from development.services.route_service import RouteService
from development.services.search_service import SearchService
from development.services.weather_service import WeatherService
# 导入通用技能实现。
from development.skills.common_skills import CalculatorSkill
from development.skills.common_skills import MemorySkill
from development.skills.common_skills import SummarySkill
from development.skills.common_skills import WebSearchSkill
# 导入教育技能实现。
from development.skills.education_skills import ExerciseSolverSkill
from development.skills.education_skills import KnowledgeExplainSkill
from development.skills.education_skills import LearningProgressSkill
# 导入医疗技能实现。
from development.skills.medical_skills import DrugInfoSkill
from development.skills.medical_skills import HealthTipsSkill
from development.skills.medical_skills import SymptomAnalyzerSkill
# 导入文旅技能实现。
from development.skills.tourism_skills import AttractionInfoSkill
from development.skills.tourism_skills import RoutePlanningSkill
from development.skills.tourism_skills import WeatherCheckSkill


# 定义技能注册中心，用于集中创建并管理所有技能对象。
class SkillRegistry:
    # 初始化技能注册中心，并完成全部技能实例注册。
    def __init__(self, memory_store: JsonMemoryStore) -> None:
        # 初始化搜索服务对象，供多个技能复用。
        search_service = SearchService()
        # 初始化天气服务对象，供天气技能调用。
        weather_service = WeatherService()
        # 初始化药品查询服务对象，供医疗技能调用。
        drug_service = DrugService()
        # 初始化路线规划服务对象，供路线技能调用。
        route_service = RouteService()
        # 构建技能名称到技能对象的映射表。
        self.skills = {
            "skill_memory": MemorySkill(memory_store),
            "skill_web_search": WebSearchSkill(search_service),
            "skill_calculator": CalculatorSkill(),
            "skill_generate_summary": SummarySkill(),
            "skill_attraction_info": AttractionInfoSkill(search_service),
            "skill_weather_check": WeatherCheckSkill(weather_service),
            "skill_route_planning": RoutePlanningSkill(route_service),
            "skill_exercise_solver": ExerciseSolverSkill(),
            "skill_knowledge_point_explain": KnowledgeExplainSkill(),
            "skill_learning_progress_track": LearningProgressSkill(),
            "skill_symptom_analyzer": SymptomAnalyzerSkill(),
            "skill_drug_info_query": DrugInfoSkill(drug_service),
            "skill_health_tips_provider": HealthTipsSkill(),
        }

    # 根据技能名称返回技能对象，若不存在则抛出错误。
    def get(self, name: str):
        # 判断技能是否已经被注册。
        if name not in self.skills:
            # 对未知技能抛出明确错误，便于调试。
            raise KeyError(f"未注册技能: {name}")
        # 返回目标技能对象。
        return self.skills[name]
