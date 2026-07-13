"""该文件用于实现通用技能，包括记忆、搜索、计算与摘要能力。"""

# 导入数学表达式安全求值所需的抽象语法树模块。
import ast
# 导入运算符模块，用于建立允许执行的计算映射。
import operator

# 导入记忆仓库，以便技能读取历史上下文。
from development.core.memory import JsonMemoryStore
# 导入技能上下文与结果类型，统一技能协议。
from development.core.models import SkillContext
from development.core.models import SkillResult
# 导入搜索服务，用于执行真实联网搜索。
from development.services.search_service import SearchService
# 导入技能基类，便于复用统一接口。
from development.skills.base import BaseSkill

# 定义允许执行的安全运算符集合，避免任意代码执行。
SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


# 定义记忆技能，用于回显最近上下文辅助模型作答。
class MemorySkill(BaseSkill):
    # 初始化记忆技能，并注入底层记忆仓库。
    def __init__(self, memory_store: JsonMemoryStore) -> None:
        # 调用父类初始化技能基础信息。
        super().__init__(name="skill_memory")
        # 保存记忆仓库对象。
        self.memory_store = memory_store

    # 执行记忆读取逻辑，并返回最近对话摘要。
    def run(self, context: SkillContext) -> SkillResult:
        # 根据上下文已有历史记录拼装可读文本。
        lines = [f"{item['role']}: {item['content']}" for item in context.history]
        # 生成适合提示词拼接的记忆文本。
        content = "\n".join(lines) if lines else "暂无历史会话。"
        # 返回统一的技能结果对象。
        return SkillResult(name=self.name, domain=context.domain, content=content)


# 定义通用搜索技能，用于提供真实联网检索结果。
class WebSearchSkill(BaseSkill):
    # 初始化搜索技能对象，并注入搜索服务依赖。
    def __init__(self, search_service: SearchService) -> None:
        # 调用父类初始化技能名。
        super().__init__(name="skill_web_search")
        # 保存搜索服务对象。
        self.search_service = search_service

    # 执行搜索逻辑，并返回真实搜索结果摘要。
    def run(self, context: SkillContext) -> SkillResult:
        # 调用搜索服务获取联网结果。
        content = self.search_service.search(context.query)
        # 返回技能执行结果。
        return SkillResult(name=self.name, domain=context.domain, content=content)


# 定义计算技能，用于安全地处理基础四则运算表达式。
class CalculatorSkill(BaseSkill):
    # 初始化计算技能对象。
    def __init__(self) -> None:
        # 调用父类初始化技能名。
        super().__init__(name="skill_calculator")

    # 递归解析抽象语法树节点并计算结果。
    def _eval(self, node: ast.AST) -> float:
        # 若节点是数字常量，则直接返回其值。
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        # 若节点是二元运算，则递归计算左右子树。
        if isinstance(node, ast.BinOp) and type(node.op) in SAFE_OPERATORS:
            return SAFE_OPERATORS[type(node.op)](self._eval(node.left), self._eval(node.right))
        # 若节点是一元运算，则递归处理其操作数。
        if isinstance(node, ast.UnaryOp) and type(node.op) in SAFE_OPERATORS:
            return SAFE_OPERATORS[type(node.op)](self._eval(node.operand))
        # 对不被允许的表达式直接抛错，确保安全。
        raise ValueError("仅支持基础数字运算表达式。")

    # 执行计算逻辑，并返回最终结果文本。
    def run(self, context: SkillContext) -> SkillResult:
        # 仅保留表达式相关字符，避免解析无关文本。
        expression = "".join(char for char in context.query if char in "0123456789+-*/(). ")
        # 若提取不到表达式，则直接返回提示文本。
        if not expression.strip():
            return SkillResult(name=self.name, domain=context.domain, content="未识别到可计算表达式。")
        # 将表达式解析为抽象语法树节点。
        tree = ast.parse(expression, mode="eval")
        # 计算表达式数值结果。
        result = self._eval(tree.body)
        # 返回统一技能结果。
        return SkillResult(name=self.name, domain=context.domain, content=f"计算结果为 {result:g}。")


# 定义摘要技能，用于快速概括用户问题核心诉求。
class SummarySkill(BaseSkill):
    # 初始化摘要技能对象。
    def __init__(self) -> None:
        # 调用父类初始化技能名。
        super().__init__(name="skill_generate_summary")

    # 执行摘要逻辑，并输出简短概括文本。
    def run(self, context: SkillContext) -> SkillResult:
        # 对长文本进行简单截断处理，形成基础摘要。
        summary = context.query.strip()[:80]
        # 返回统一技能结果。
        return SkillResult(name=self.name, domain=context.domain, content=f"问题摘要：{summary}")
