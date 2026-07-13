"""该文件用于定义智能体运行过程中复用的数据模型。"""

# 导入数据类工具，用于定义轻量对象。
from dataclasses import asdict
# 导入数据类装饰器，用于声明结构化模型。
from dataclasses import dataclass
# 导入字段工厂，用于设置列表默认值。
from dataclasses import field


# 定义技能运行上下文，用于向技能传递输入信息。
@dataclass(slots=True)
class SkillContext:
    # 保存用户当前问题文本。
    query: str
    # 保存当前识别到的业务领域。
    domain: str
    # 保存最近几轮对话记忆。
    history: list[dict[str, str]] = field(default_factory=list)


# 定义技能执行结果，用于统一技能输出格式。
@dataclass(slots=True)
class SkillResult:
    # 保存技能名称。
    name: str
    # 保存技能所属领域。
    domain: str
    # 保存技能输出内容。
    content: str

    # 提供字典转换方法，便于序列化响应。
    def to_dict(self) -> dict[str, str]:
        # 返回当前对象的字典形式。
        return asdict(self)


# 定义智能体响应结构，用于统一 CLI 与服务端输出。
@dataclass(slots=True)
class AgentResponse:
    # 保存识别出的领域名称。
    domain: str
    # 保存最终生成的回答内容。
    answer: str
    # 保存本次使用到的技能列表。
    skills_used: list[str]
    # 保存本次技能执行详情。
    skill_results: list[SkillResult]
    # 保存会话编号，便于区分不同用户上下文。
    session_id: str

    # 提供字典转换方法，便于转成 JSON。
    def to_dict(self) -> dict[str, object]:
        # 构造基础字典结果。
        payload = asdict(self)
        # 覆盖技能结果字段，确保每项都可直接序列化。
        payload["skill_results"] = [item.to_dict() for item in self.skill_results]
        # 返回整理后的响应字典。
        return payload
