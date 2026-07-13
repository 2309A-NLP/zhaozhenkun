"""该文件用于实现医疗领域技能，包括症状分析、药品查询与健康提示能力。"""

# 导入技能上下文与结果类型，统一输入输出。
from development.core.models import SkillContext
from development.core.models import SkillResult
# 导入药品查询服务，用于访问真实公开药品数据。
from development.services.drug_service import DrugService
# 导入技能基类，便于复用统一接口。
from development.skills.base import BaseSkill


# 定义症状分析技能，用于输出保守的分诊建议。
class SymptomAnalyzerSkill(BaseSkill):
    # 初始化症状分析技能对象。
    def __init__(self) -> None:
        # 调用父类并声明医疗领域。
        super().__init__(name="skill_symptom_analyzer", domain="medical")

    # 执行症状分析说明逻辑。
    def run(self, context: SkillContext) -> SkillResult:
        # 返回偏安全的健康建议，避免直接替代医生诊断。
        content = "建议先记录症状持续时间、伴随表现与体温变化；若症状加重或持续不缓解，应尽快线下就医。"
        # 返回技能执行结果。
        return SkillResult(name=self.name, domain=self.domain, content=content)


# 定义药品信息技能，用于提示用户关注药品使用边界。
class DrugInfoSkill(BaseSkill):
    # 初始化药品信息技能对象，并注入药品服务依赖。
    def __init__(self, drug_service: DrugService) -> None:
        # 调用父类并声明医疗领域。
        super().__init__(name="skill_drug_info_query", domain="medical")
        # 保存药品查询服务对象。
        self.drug_service = drug_service

    # 执行药品信息说明逻辑。
    def run(self, context: SkillContext) -> SkillResult:
        # 调用真实药品接口并获取公开标签摘要。
        content = self.drug_service.lookup(context.query)
        # 返回技能执行结果。
        return SkillResult(name=self.name, domain=self.domain, content=content)


# 定义健康提示技能，用于提供生活方式建议。
class HealthTipsSkill(BaseSkill):
    # 初始化健康提示技能对象。
    def __init__(self) -> None:
        # 调用父类并声明医疗领域。
        super().__init__(name="skill_health_tips_provider", domain="medical")

    # 执行健康提示说明逻辑。
    def run(self, context: SkillContext) -> SkillResult:
        # 返回通用健康建议，强调休息与观察。
        content = "建议保持补水、规律作息、清淡饮食，并持续观察是否出现高热、呼吸困难等预警信号。"
        # 返回技能执行结果。
        return SkillResult(name=self.name, domain=self.domain, content=content)
