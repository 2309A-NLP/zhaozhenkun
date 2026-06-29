"""
src/agent.py - 医疗健康咨询 ReAct Agent
功能: 基于 ReAct (Reasoning + Acting) 模式的自主 Agent。
      Agent 自主思考 → 选择工具 → 执行 → 观察结果 → 再思考 → 最终回答。
      不再走固定 pipeline，而是由 LLM 自主决策每一步做什么。
      支持工具: KG查询、疾病搜索、症状反向查找、本地数据降级。
      验收标准: 准确率 ≥ 80%
工单编号: 人工智能NLP-Agent数字人项目-医疗智能体-健康咨询
"""
import json
import logging
import time
import os

from openai import OpenAI

from src.config import AppConfig
from src.models import AgentResponse
from src.graph_query import GraphQueryExecutor, mock_query

logger = logging.getLogger(__name__)

# ============================================================
# ReAct Agent 系统提示词 — 定义 Agent 人格、能力和工具
# ============================================================

_REACT_SYSTEM_PROMPT = """你是一个医疗健康咨询 Agent。你可以自主使用工具来回答用户的健康问题。

## 你的能力

你不是一个简单的问答机器人。你需要：
1. **理解用户意图** — 分析用户真正想知道什么
2. **制定查询计划** — 决定用什么工具、查什么数据
3. **执行工具调用** — 自主选择工具并构造参数
4. **分析返回结果** — 判断结果是否足够回答问题
5. **决定下一步** — 如果信息不足，换种方式再查
6. **生成最终答案** — 综合所有信息，用通俗语言回答

## 可用工具

你有以下工具可以调用：

### 1. search_disease
搜索知识图谱中的疾病信息。
参数: disease_name (字符串) — 疾病名称
返回: 疾病的所有字段（简介、病因、症状、治疗、药物、预防、护理、饮食等）

### 2. query_graph
在 Neo4j 医疗知识图谱上执行 Cypher 查询。
知识图谱结构:
  (Disease {name, intro, cause, symptom, get_way, treat_detail, treat_prob, treat_period, treat_cost, prevent, nursing})
  关系: Disease-[:TREATED_BY]->Department, Disease-[:USES_DRUG]->Drug,
        Disease-[:HAS_COMPLICATION]->Complication, Disease-[:TREATED_WITH]->Treatment,
        Disease-[:HAS_SYMPTOM]->Symptom, Disease-[:HAS_PREVENTION]->Prevention,
        Disease-[:HAS_NURSING]->Nursing, Disease-[:CAN_EAT]->Food, Disease-[:AVOID_EAT]->Food
参数: cypher (字符串) — 完整的 Cypher 查询语句，使用 $name 作为疾病名参数
示例: MATCH (d:Disease {name: $disease})-[:USES_DRUG]->(drug:Drug) RETURN drug.name AS drugs

### 3. search_by_symptom
通过症状反向查找可能的疾病。
参数: symptom (字符串) — 症状关键词
返回: 匹配的疾病列表

## 回答格式

每次回复必须严格按照以下 JSON 格式，不要输出其他内容：

如果还需要查询信息：
{"thought": "你的思考过程...", "action": "工具名", "action_input": "参数"}

如果已有足够信息回答用户：
{"thought": "你的思考过程...", "final_answer": "你的完整回答"}

## 规则
- 每次只调用一个工具
- 如果第一次查询结果不够，尝试换角度再查
- 所有答案必须基于实际查询结果，不要编造
- 回答控制在 300 字以内
- 末尾加上: "⚠ 本回答仅供参考，具体诊疗请咨询专业医生。"
- 如果确实查不到，诚实告知并给出建议
"""

# ============================================================
# ReAct Agent 核心实现
# ============================================================

class MedicalAgent:
    """
    医疗健康咨询 ReAct Agent。

    不再使用固定 pipeline，而是 LLM 自主决策:
    Thought → Action → Observation → Thought → ... → Final Answer

    每轮:
    1. 将 [系统提示 + 工具定义 + 历史 + 用户问题] 发给 LLM
    2. LLM 返回 JSON: {"thought":..., "action":..., "action_input":...}
       或: {"thought":..., "final_answer":...}
    3. 如果是 action → 执行工具 → 将结果作为 observation 追加 → 回到步骤1
    4. 如果是 final_answer → 返回给用户

    最多 5 轮迭代，防止无限循环。
    """

    def __init__(self, config: AppConfig):
        self.config = config

        # LLM 客户端
        self._client = None
        if config.llm.api_key:
            self._client = OpenAI(
                api_key=config.llm.api_key,
                base_url=config.llm.api_base,
            )

        # Neo4j 查询执行器
        self.graph_query = GraphQueryExecutor(config.neo4j)
        self._neo4j_available = self.graph_query.check_connectivity()
        if self._neo4j_available:
            logger.info("Neo4j 连接就绪，Agent 可使用图谱查询")
        else:
            logger.info("Neo4j 未就绪，Agent 将使用本地数据检索")

        # 预加载 JSONL 数据用于本地降级
        self._local_data = {}
        self._load_local_data()

        logger.info("ReAct Medical Agent 初始化完成")

    def _load_local_data(self):
        """预加载 medical.json 到内存，供本地检索工具使用。"""
        data_file = self.config.kg.data_file
        if not os.path.exists(data_file):
            # 尝试 dev/ 目录
            alt = os.path.join("dev", data_file) if not data_file.startswith("dev") else data_file
            if os.path.exists(alt):
                data_file = alt
            else:
                logger.warning(f"数据文件未找到: {data_file}")
                return
        try:
            with open(data_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        obj = json.loads(line)
                        name = obj.get("name", "")
                        if name:
                            self._local_data[name] = obj
                    except json.JSONDecodeError:
                        continue
            logger.info(f"本地数据加载: {len(self._local_data)} 种疾病")
        except Exception as e:
            logger.error(f"本地数据加载失败: {e}")

    # ---- 工具辅助 ----

    @staticmethod
    def _safe_get(obj, key: str, default: str = "") -> str:
        """安全获取 Neo4j Node 属性值（兼容 dict 和 Neo4j Node 对象）。"""
        if obj is None:
            return default
        if isinstance(obj, dict):
            return str(obj.get(key, default))
        try:
            val = obj.get(key, default)
            return str(val) if val else default
        except Exception:
            return default

    # ---- 工具实现 ----

    def _tool_search_disease(self, disease_name: str) -> str:
        """工具: 搜索疾病信息。先查 Neo4j，不可用则查本地 JSONL。
        返回整洁的 JSON 格式，LLM 可直接理解。"""
        if self._neo4j_available:
            result = self.graph_query.query(
                "MATCH (d:Disease {name: $disease}) "
                "OPTIONAL MATCH (d)-[:USES_DRUG]->(drug:Drug) "
                "OPTIONAL MATCH (d)-[:HAS_COMPLICATION]->(c:Complication) "
                "OPTIONAL MATCH (d)-[:TREATED_BY]->(dept:Department) "
                "OPTIONAL MATCH (d)-[:TREATED_WITH]->(t:Treatment) "
                "OPTIONAL MATCH (d)-[:HAS_SYMPTOM]->(s:Symptom) "
                "RETURN d, "
                "collect(DISTINCT drug.name) AS drugs, "
                "collect(DISTINCT c.name) AS complications, "
                "collect(DISTINCT dept.name) AS departments, "
                "collect(DISTINCT t.name) AS treatments, "
                "collect(DISTINCT s.name) AS symptoms",
                disease_name
            )
            if result:
                r = result[0]
                d = r.get("d", {})
                # 构建干净的 JSON，而非 Neo4j Node 原始格式
                return json.dumps({
                    "name": disease_name,
                    "intro": self._safe_get(d, "intro", "")[:300],
                    "cause": self._safe_get(d, "cause", "")[:800],
                    "symptom": r.get("symptoms", []),
                    "get_way": self._safe_get(d, "get_way", ""),
                    "drugs": r.get("drugs", []),
                    "treatments": r.get("treatments", []),
                    "treat_detail": self._safe_get(d, "treat_detail", "")[:2500],
                    "treat_prob": self._safe_get(d, "treat_prob", ""),
                    "treat_period": self._safe_get(d, "treat_period", ""),
                    "treat_cost": self._safe_get(d, "treat_cost", ""),
                    "complications": r.get("complications", []),
                    "prevent": self._safe_get(d, "prevent", "")[:500],
                    "nursing": self._safe_get(d, "nursing", "")[:500],
                    "can_eat": self._safe_get(d, "can_eat", ""),
                    "not_eat": self._safe_get(d, "not_eat", ""),
                    "departments": r.get("departments", []),
                    "insurance": self._safe_get(d, "insurance", ""),
                    "easy_get": self._safe_get(d, "easy_get", ""),
                }, ensure_ascii=False, indent=2)
        # 降级: 本地 JSONL
        if disease_name in self._local_data:
            obj = self._local_data[disease_name]
            return json.dumps({
                "name": obj.get("name"), "intro": obj.get("intro", "")[:200],
                "cause": obj.get("cause", "")[:300],
                "symptom": obj.get("symptom", ""),
                "get_way": obj.get("get_way"), "drug": obj.get("drug"),
                "treat": obj.get("treat"), "treat_detail": obj.get("treat_detail", "")[:500],
                "neopathy": obj.get("neopathy"), "prevent": obj.get("prevent", "")[:200],
                "nursing": obj.get("nursing"), "not_eat": obj.get("not_eat"),
                "can_eat": obj.get("can_eat"), "cure_dept": obj.get("cure_dept"),
                "treat_prob": obj.get("treat_prob"), "treat_period": obj.get("treat_period"),
                "treat_cost": obj.get("treat_cost"),
            }, ensure_ascii=False, indent=2)
        return f"未找到名为 '{disease_name}' 的疾病。请尝试其他名称或使用 search_by_symptom。"

    def _tool_query_graph(self, cypher: str) -> str:
        """工具: 执行 Cypher 查询。返回整洁 JSON。"""
        import re
        # 标准化参数名: 将所有 $name / $diseaseName 等统一替换为 $disease
        cypher = re.sub(r'\$name\b', '$disease', cypher)
        cypher = re.sub(r'\$diseaseName\b', '$disease', cypher)
        cypher = re.sub(r'\$disease_name\b', '$disease', cypher)
        # 从 Cypher 中提取疾病名（优先从硬编码名称提取）
        name_match = re.search(r'\{name:\s*["\']([^"\']+)["\']\}', cypher)
        disease_name = name_match.group(1) if name_match else ""

        if self._neo4j_available:
            result = self.graph_query.query(cypher, disease_name)
            if result:
                # 将 Neo4j 结果中的 Node 对象转为纯 dict
                clean = []
                for row in result:
                    clean_row = {}
                    for k, v in row.items():
                        clean_row[k] = self._clean_value(v)
                    clean.append(clean_row)
                return json.dumps(clean, ensure_ascii=False, indent=2)[:3000]

        # 降级: 本地 JSONL
        if disease_name and disease_name in self._local_data:
            return self._tool_search_disease(disease_name)

        return f"查询无结果。疾病 '{disease_name}' 未找到。"

    @staticmethod
    def _clean_value(v) -> str:
        """清理 Neo4j 返回值：Node→dict, list→str join。"""
        if v is None:
            return ""
        if isinstance(v, (str, int, float, bool)):
            return str(v)
        if isinstance(v, list):
            return [str(x) for x in v[:20]]
        if isinstance(v, dict):
            return {k: str(vv)[:200] for k, vv in v.items()}
        return str(v)[:500]

    def _tool_search_by_symptom(self, symptom: str) -> str:
        """工具: 症状反向搜索。在本地数据中搜索匹配的疾病。"""
        matches = []
        for name, obj in self._local_data.items():
            symptom_text = str(obj.get("symptom", ""))
            if symptom in symptom_text:
                matches.append({
                    "name": name,
                    "symptom": symptom_text[:120],
                    "intro": obj.get("intro", "")[:80]
                })
            if len(matches) >= 10:
                break
        if matches:
            return json.dumps(matches, ensure_ascii=False, indent=2)
        return f"未找到包含 '{symptom}' 症状的疾病。"

    # ---- ReAct 主循环 ----

    def consult(self, query: str) -> AgentResponse:
        """
        ReAct Agent 主循环。

        参数:
            query: 用户自然语言问题

        返回:
            AgentResponse 包含思考过程、工具调用记录和最终答案
        """
        total_start = time.time()
        response = AgentResponse(query=query)
        reasoning_steps = []

        # 构建消息历史
        messages = [
            {"role": "system", "content": _REACT_SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ]

        max_iterations = 5
        for iteration in range(max_iterations):
            step = {"iteration": iteration + 1}
            logger.info(f"Agent 思考 第 {iteration+1} 轮...")

            if self._client is None:
                # 无 LLM → 使用简单降级逻辑
                return self._fallback_consult(query, response, total_start)

            try:
                llm_response = self._client.chat.completions.create(
                    model=self.config.llm.model,
                    messages=messages,
                    max_tokens=self.config.llm.max_tokens,
                    temperature=self.config.llm.temperature,
                    stream=False,
                )
                raw = llm_response.choices[0].message.content.strip()
            except Exception as e:
                logger.error(f"LLM 调用失败: {e}")
                return self._fallback_consult(query, response, total_start)

            # 解析 LLM 返回的 JSON
            try:
                # 清理可能的 markdown 标记
                if raw.startswith("```"):
                    lines = raw.split("\n")
                    raw = "\n".join(lines[1:]) if len(lines) > 1 else raw
                    if raw.endswith("```"):
                        raw = raw[:-3]
                data = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning(f"LLM 返回非 JSON: {raw[:200]}")
                step["thought"] = "(解析失败)"
                step["action"] = "fallback"
                step["observation"] = raw[:500]
                reasoning_steps.append(step)
                # 把 raw 当作最终答案
                response.answer = raw[:1000]
                response.success = True
                break

            thought = data.get("thought", "")
            step["thought"] = thought

            # 判断是工具调用还是最终答案
            if "final_answer" in data:
                step["action"] = "final_answer"
                step["observation"] = "(生成答案)"
                reasoning_steps.append(step)
                response.answer = data["final_answer"]
                response.success = True
                logger.info(f"Agent 在第 {iteration+1} 轮给出最终答案")
                break

            elif "action" in data:
                action = data["action"]
                action_input = data.get("action_input", "")
                step["action"] = action
                step["action_input"] = action_input

                # 执行工具
                observation = self._execute_tool(action, action_input)
                step["observation"] = observation[:500]
                reasoning_steps.append(step)

                # 将结果反馈给 LLM
                messages.append({"role": "assistant", "content": raw})
                messages.append({"role": "user", "content": f"工具执行结果:\n{observation}"})
                logger.info(f"Agent 执行工具 {action}: {str(action_input)[:80]} → {len(observation)} 字符")

            else:
                # 格式异常 → 当作答案
                step["action"] = "unknown_format"
                step["observation"] = raw[:300]
                reasoning_steps.append(step)
                response.answer = raw[:1000]
                response.success = True
                break

        # 超过最大迭代
        if not response.answer:
            response.answer = "抱歉，我尝试了多次查询但未能找到足够的信息来回答您的问题。建议您换个方式提问或咨询专业医生。"
            response.success = False

        response.reasoning_steps = reasoning_steps
        response.latency_ms = (time.time() - total_start) * 1000
        return response

    def _execute_tool(self, action: str, action_input: str) -> str:
        """执行工具调用。"""
        action_input = action_input.strip().strip('"').strip("'")
        try:
            if action == "search_disease":
                return self._tool_search_disease(action_input)
            elif action == "query_graph":
                return self._tool_query_graph(action_input)
            elif action == "search_by_symptom":
                return self._tool_search_by_symptom(action_input)
            else:
                return f"未知工具: {action}。可用工具: search_disease, query_graph, search_by_symptom"
        except Exception as e:
            return f"工具执行失败: {str(e)}"

    def _fallback_consult(self, query: str, response: AgentResponse, total_start: float) -> AgentResponse:
        """无 LLM 时的降级逻辑 — 基于关键词的本地检索。"""
        # 尝试从 query 中提取疾病名
        disease = ""
        for name in sorted(self._local_data.keys(), key=len, reverse=True):
            if name in query:
                disease = name
                break

        if not disease:
            response.answer = "请告诉我您想了解哪种疾病？例如: '百日咳有什么症状？'"
            response.success = True
            response.latency_ms = (time.time() - total_start) * 1000
            return response

        # 用 mock_query 按类别检索
        from src.cypher_generator import CypherGenerator
        cg = CypherGenerator()
        from src.models import QueryIntent

        # 简单意图识别
        category = "概述"
        cat_keywords = {
            "病原体": ["病原", "细菌", "病毒", "什么引起的"],
            "传播途径": ["传播", "传染", "怎么得"],
            "症状": ["症状", "表现", "特征"],
            "药物": ["药", "抗生素", "吃什么药"],
            "并发症": ["并发症"],
            "治疗": ["治疗", "治法", "主方"],
            "预防": ["预防", "隔离"],
            "护理": ["护理", "注意"],
            "饮食": ["吃", "食", "忌口"],
        }
        for cat, kws in cat_keywords.items():
            if any(kw in query for kw in kws):
                category = cat
                break

        intent = QueryIntent(disease=disease, category=category, raw_query=query)
        kg_data = mock_query(disease, category)

        response.answer = f"关于「{disease}」的{category}信息:\n\n{kg_data[:1500]}\n\n⚠ 本回答仅供参考，具体诊疗请咨询专业医生。"
        response.reasoning_steps = [{
            "iteration": 1, "thought": f"降级模式: 识别疾病={disease}, 类别={category}",
            "action": "local_search", "observation": kg_data[:300]
        }]
        response.success = True
        response.latency_ms = (time.time() - total_start) * 1000
        return response

    def close(self) -> None:
        """关闭连接，释放资源。"""
        self.graph_query.close()
        logger.info("Medical Agent 已关闭")
