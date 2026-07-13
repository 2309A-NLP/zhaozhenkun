"""该文件用于实现教育领域技能，包括解题、知识讲解与进度跟踪能力。"""

# 导入技能上下文与结果类型，统一输入输出。
from development.core.models import SkillContext
from development.core.models import SkillResult
# 导入技能基类，便于复用统一接口。
from development.skills.base import BaseSkill


# 定义习题求解技能，用于输出解题思路框架。
class ExerciseSolverSkill(BaseSkill):
    # 初始化习题求解技能对象。
    def __init__(self) -> None:
        # 调用父类并声明教育领域。
        super().__init__(name="skill_exercise_solver", domain="education")

    # 执行习题求解说明逻辑。
    def run(self, context: SkillContext) -> SkillResult:
        # 返回结构化解题建议。
        content = "建议按‘已知条件-目标结论-解题步骤-结果校验’四段式组织答案。"
        # 返回技能执行结果。
        return SkillResult(name=self.name, domain=self.domain, content=content)


# 定义知识点讲解技能，用于生成知识点解释框架。
class KnowledgeExplainSkill(BaseSkill):
    # 初始化知识点讲解技能对象。
    def __init__(self) -> None:
        # 调用父类并声明教育领域。
        super().__init__(name="skill_knowledge_point_explain", domain="education")

    # 执行知识点讲解说明逻辑。
    def run(self, context: SkillContext) -> SkillResult:
        # 返回知识讲解建议。
        content = f"建议从定义、原理、例题与常见误区四个层次讲解“{context.query}”。"
        # 返回技能执行结果。
        return SkillResult(name=self.name, domain=self.domain, content=content)


# 定义学习进度跟踪技能，用于输出学习计划建议。
class LearningProgressSkill(BaseSkill):
    # 初始化学习进度跟踪技能对象。
    def __init__(self) -> None:
        # 调用父类并声明教育领域。
        super().__init__(name="skill_learning_progress_track", domain="education")

    # 执行学习计划说明逻辑。
    def run(self, context: SkillContext) -> SkillResult:
        # 返回学习节奏建议，便于后续扩展个性化规划。
        content = "建议拆分为每日目标、每周回顾、错题整理与阶段测评四部分。"
        # 返回技能执行结果。
        return SkillResult(name=self.name, domain=self.domain, content=content)
