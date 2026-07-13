"""该文件用于编排领域识别、技能执行与模型生成的完整智能体流程。"""

# 导入类型工具，用于声明流式事件的迭代器类型。
from typing import Iterator

# 导入配置加载函数，用于读取当前模型配置。
from development.core.config import load_config
# 导入记忆仓库，用于保存和读取会话历史。
from development.core.memory import JsonMemoryStore
# 导入响应与上下文模型，统一输出结构。
from development.core.models import AgentResponse
from development.core.models import SkillContext
# 导入领域路由函数，用于识别业务域并选择技能。
from development.core.router import detect_domain
from development.core.router import select_skills
# 导入聊天客户端，用于调用大模型。
from development.llm.client import ChatClient
# 导入技能注册中心，用于调度技能对象。
from development.services.skill_registry import SkillRegistry


# 定义主智能体服务，用于聚合技能与模型输出。
class AgentService:
    # 初始化智能体服务，并注入默认依赖。
    def __init__(self, provider_name: str | None = None) -> None:
        # 加载应用配置对象。
        self.config = load_config(provider_name)
        # 初始化记忆仓库对象。
        self.memory_store = JsonMemoryStore()
        # 初始化技能注册中心。
        self.registry = SkillRegistry(self.memory_store)
        # 初始化大模型客户端。
        self.client = ChatClient(self.config.provider)

    # 处理单轮问答，并返回结构化响应结果。
    def handle(self, query: str, session_id: str = "default") -> AgentResponse:
        # 先准备技能执行结果与提示词上下文。
        prepared = self._prepare(query, session_id)
        # 调用模型生成最终答案。
        answer = self.client.chat(prepared["system_prompt"], prepared["user_prompt"])
        # 持久化当前用户问题与模型答案。
        self._persist(session_id, query, answer)
        # 返回统一结构化响应。
        return AgentResponse(
            domain=prepared["domain"],
            answer=answer,
            skills_used=prepared["skill_names"],
            skill_results=prepared["skill_results"],
            session_id=session_id,
        )

    # 以流式方式处理单轮问答，并逐步返回事件数据。
    def stream_handle(self, query: str, session_id: str = "default") -> Iterator[dict[str, object]]:
        # 先准备技能执行结果与提示词上下文。
        prepared = self._prepare(query, session_id)
        # 先向前端返回领域与技能元数据，便于即时渲染。
        yield {
            "type": "meta",
            "domain": prepared["domain"],
            "skills_used": prepared["skill_names"],
            "skill_results": [item.to_dict() for item in prepared["skill_results"]],
            "session_id": session_id,
        }
        # 准备承载流式文本块的列表。
        chunks: list[str] = []
        # 调用模型的流式接口逐块返回文本内容。
        for chunk in self.client.stream_chat(prepared["system_prompt"], prepared["user_prompt"]):
            # 将当前文本块写入本地缓冲区。
            chunks.append(chunk)
            # 把当前文本块作为事件向上游返回。
            yield {"type": "chunk", "content": chunk}
        # 拼接全部文本块得到最终答案。
        answer = "".join(chunks)
        # 持久化当前用户问题与完整模型答案。
        self._persist(session_id, query, answer)
        # 组装最终结构化响应对象。
        response = AgentResponse(
            domain=prepared["domain"],
            answer=answer,
            skills_used=prepared["skill_names"],
            skill_results=prepared["skill_results"],
            session_id=session_id,
        )
        # 返回流式结束事件，便于前端收尾。
        yield {"type": "done", "response": response.to_dict()}

    # 构造系统提示词，用于限定模型行为与风格。
    def _build_system_prompt(self, domain: str) -> str:
        # 返回面向领域化智能体的系统提示信息。
        return (
            f"你是一个基于 SKILLS 架构的 {domain} 智能体。"
            "请优先结合技能结果作答，语言准确、结构清晰。"
            "若问题涉及医疗，请明确提醒用户线下就医边界，避免给出确定性诊断。"
        )

    # 构造用户提示词，用于把技能结果汇总给大模型。
    def _build_user_prompt(self, query: str, skill_results: list) -> str:
        # 整理全部技能输出文本，便于提示词拼接。
        skills_text = "\n".join(f"- {item.name}: {item.content}" for item in skill_results)
        # 返回最终用户提示词内容。
        return f"用户问题：{query}\n\n技能结果：\n{skills_text}\n\n请综合以上信息给出最终回答。"

    # 准备领域识别、技能执行和提示词上下文。
    def _prepare(self, query: str, session_id: str) -> dict[str, object]:
        # 先从记忆中读取最近会话内容。
        history = self.memory_store.recall(session_id)
        # 识别当前问题所属业务领域。
        domain = detect_domain(query)
        # 根据领域与问题内容选取技能列表。
        skill_names = select_skills(domain, query)
        # 构造传递给技能层的上下文对象。
        context = SkillContext(query=query, domain=domain, history=history)
        # 准备技能执行结果容器。
        skill_results = []
        # 逐个运行被选中的技能。
        for skill_name in skill_names:
            # 根据名称获取技能实例。
            skill = self.registry.get(skill_name)
            # 执行技能并收集输出结果。
            skill_results.append(skill.run(context))
        # 生成系统提示词，要求模型按安全与专业口吻回答。
        system_prompt = self._build_system_prompt(domain)
        # 基于技能结果构造用户提示词。
        user_prompt = self._build_user_prompt(query, skill_results)
        # 返回完整的编排中间结果。
        return {
            "domain": domain,
            "skill_names": skill_names,
            "skill_results": skill_results,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        }

    # 持久化用户问题与模型答案，便于后续轮次回忆上下文。
    def _persist(self, session_id: str, query: str, answer: str) -> None:
        # 将当前用户问题写入记忆仓库。
        self.memory_store.append(session_id, "user", query)
        # 将模型回答写入记忆仓库。
        self.memory_store.append(session_id, "assistant", answer)
