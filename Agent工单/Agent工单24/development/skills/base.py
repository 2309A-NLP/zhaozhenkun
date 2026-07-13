"""该文件用于定义技能抽象基类，统一技能接口与结果格式。"""

# 导入抽象基类工具，用于定义统一技能协议。
from abc import ABC
# 导入抽象方法装饰器，用于强制子类实现运行逻辑。
from abc import abstractmethod

# 导入上下文与结果模型，统一输入输出结构。
from development.core.models import SkillContext
from development.core.models import SkillResult


# 定义技能基类，用于约束所有技能的公共行为。
class BaseSkill(ABC):
    # 初始化技能对象，并保存技能名称与所属领域。
    def __init__(self, name: str, domain: str = "general") -> None:
        # 保存当前技能名称。
        self.name = name
        # 保存当前技能领域。
        self.domain = domain

    # 定义统一运行接口，由各个技能子类完成具体实现。
    @abstractmethod
    def run(self, context: SkillContext) -> SkillResult:
        # 抽象方法不直接实现，交由子类覆盖。
        raise NotImplementedError
