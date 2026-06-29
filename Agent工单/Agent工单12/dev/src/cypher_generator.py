"""
src/cypher_generator.py - Cypher 查询生成模块
功能: 根据解析后的查询意图 (QueryIntent) 生成对应的 Neo4j Cypher 查询语句。
      支持 15 种查询类别，每种映射到特定的图查询模式。
      验收标准: 覆盖 10 个核心测试案例及 30+ 变体场景
工单编号: 人工智能NLP-Agent数字人项目-医疗智能体-健康咨询
"""
import logging

from src.models import QueryIntent  # 查询意图

logger = logging.getLogger(__name__)


# ============================================================
# 查询类别 → Cypher 模板 映射表
# 每个模板返回对应关系的节点属性或关系目标节点名称
# ============================================================

# Cypher 查询模板字典
# key: 查询类别, value: (Cypher语句, 返回字段名, 返回说明)
_CYPHER_TEMPLATES = {
    # ---- 病因/病原体 ----
    "病原体": (
        "MATCH (d:Disease {name: $disease}) RETURN d.cause AS result",
        "result", "病原体/病因信息"
    ),
    # ---- 传播途径 ----
    "传播途径": (
        "MATCH (d:Disease {name: $disease}) RETURN d.get_way AS result",
        "result", "传播途径"
    ),
    # ---- 症状 ----
    "症状": (
        "MATCH (d:Disease {name: $disease}) "
        "OPTIONAL MATCH (d)-[:HAS_SYMPTOM]->(s:Symptom) "
        "RETURN d.symptom AS symptom, collect(DISTINCT s.name) AS symptom_list",
        "symptom", "症状信息"
    ),
    # ---- 诊断 ----
    "诊断": (
        "MATCH (d:Disease {name: $disease}) "
        "RETURN d.symptom AS symptom, d.intro AS intro, "
        "d.treat_detail AS treat_detail, d.cause AS cause",
        "symptom", "诊断参考信息"
    ),
    # ---- 治疗药物（含 treat_detail 中的抗生素等药物信息）- ---
    "药物": (
        "MATCH (d:Disease {name: $disease}) "
        "OPTIONAL MATCH (d)-[:USES_DRUG]->(drug:Drug) "
        "RETURN collect(DISTINCT drug.name) AS drugs, "
        "d.treat_detail AS treat_detail, d.treat AS treat",
        "drugs", "治疗药物列表"
    ),
    # ---- 并发症 ----
    "并发症": (
        "MATCH (d:Disease {name: $disease})-[:HAS_COMPLICATION]->(c:Complication) "
        "RETURN collect(DISTINCT c.name) AS result",
        "result", "并发症列表"
    ),
    # ---- 治疗方案 ----
    "治疗": (
        "MATCH (d:Disease {name: $disease}) "
        "OPTIONAL MATCH (d)-[:TREATED_WITH]->(t:Treatment) "
        "RETURN collect(DISTINCT t.name) AS result, "
        "d.treat_detail AS detail, d.treat AS treat_list",
        "result", "治疗方案"
    ),
    # ---- 预防措施（含护理中的隔离信息）- ---
    "预防": (
        "MATCH (d:Disease {name: $disease}) "
        "OPTIONAL MATCH (d)-[:HAS_PREVENTION]->(p:Prevention) "
        "RETURN d.prevent AS prevent, d.nursing AS nursing, "
        "collect(DISTINCT p.name) AS prevent_list",
        "prevent", "预防措施"
    ),
    # ---- 护理建议 ----
    "护理": (
        "MATCH (d:Disease {name: $disease}) "
        "OPTIONAL MATCH (d)-[:HAS_NURSING]->(n:Nursing) "
        "RETURN d.nursing AS nursing, collect(DISTINCT n.name) AS nursing_list",
        "nursing", "护理建议"
    ),
    # ---- 饮食建议 ----
    "饮食": (
        "MATCH (d:Disease {name: $disease}) "
        "OPTIONAL MATCH (d)-[:CAN_EAT]->(f1:Food) "
        "OPTIONAL MATCH (d)-[:AVOID_EAT]->(f2:Food) "
        "RETURN collect(DISTINCT f1.name) AS can_eat, "
        "collect(DISTINCT f2.name) AS avoid_eat",
        "can_eat", "饮食建议"
    ),
    # ---- 就诊科室 ----
    "科室": (
        "MATCH (d:Disease {name: $disease})-[:TREATED_BY]->(dept:Department) "
        "RETURN collect(DISTINCT dept.name) AS result",
        "result", "就诊科室"
    ),
    # ---- 治疗费用 ----
    "费用": (
        "MATCH (d:Disease {name: $disease}) RETURN d.treat_cost AS result",
        "result", "治疗费用参考"
    ),
    # ---- 治疗周期 ----
    "周期": (
        "MATCH (d:Disease {name: $disease}) RETURN d.treat_period AS result",
        "result", "治疗周期"
    ),
    # ---- 治愈概率 ----
    "概率": (
        "MATCH (d:Disease {name: $disease}) RETURN d.treat_prob AS result",
        "result", "治愈概率"
    ),
    # ---- 疾病概述 ----
    "概述": (
        "MATCH (d:Disease {name: $disease}) RETURN d.intro AS result",
        "result", "疾病概述"
    ),
}


# ============================================================
# 类别别名映射 — 将 LLM 返回的各种表述统一到标准类别
# ============================================================

# 类别别名表：将 LLM 可能返回的变体表述映射到标准类别名
_CATEGORY_ALIASES = {
    "病原体": "病原体", "病因": "病原体", "致病菌": "病原体",
    "传播途径": "传播途径", "传播": "传播途径", "传染": "传播途径",
    "症状": "症状", "临床表现": "症状", "特征": "症状",
    "诊断": "诊断", "检查": "诊断", "检测": "诊断",
    "药物": "药物", "药品": "药物", "用药": "药物",
    "并发症": "并发症", "后遗症": "并发症",
    "治疗": "治疗", "治疗方案": "治疗", "治法": "治疗",
    "预防": "预防", "隔离": "预防", "疫苗": "预防",
    "护理": "护理", "照护": "护理", "注意事项": "护理",
    "饮食": "饮食", "食物": "饮食", "忌口": "饮食",
    "科室": "科室", "就诊科室": "科室",
    "费用": "费用", "花费": "费用", "价格": "费用",
    "周期": "周期", "时长": "周期", "时间": "周期",
    "概率": "概率", "治愈率": "概率",
    "概述": "概述", "简介": "概述", "介绍": "概述",
}


class CypherGenerator:
    """
    Cypher 查询语句生成器。

    将 QueryIntent 中的类别映射到预定义的 Cypher 模板，
    生成可直接在 Neo4j 中执行的查询语句。
    """

    def generate(self, intent: QueryIntent) -> str:
        """
        根据查询意图生成 Cypher 查询语句。

        参数:
            intent: 解析后的查询意图

        返回:
            Neo4j Cypher 查询字符串
        """
        disease = intent.disease  # 目标疾病名
        # 如果未识别到疾病名，尝试简单的全文搜索
        if not disease:
            return self._fallback_query(intent)
        # 将 LLM 返回的类别归一化到标准类别
        raw_category = intent.category  # LLM 原始类别
        normalized = _CATEGORY_ALIASES.get(raw_category, "概述")  # 归一化
        # 查找对应的 Cypher 模板
        template_info = _CYPHER_TEMPLATES.get(
            normalized,  # 用归一化后的类别查找
            _CYPHER_TEMPLATES["概述"]  # 未匹配时默认概述
        )
        cypher = template_info[0]  # 取 Cypher 语句
        logger.info(f"Cypher 生成: {disease}/{normalized}")
        return cypher

    def _fallback_query(self, intent: QueryIntent) -> str:
        """
        当无法识别疾病名时的回退查询。

        尝试从 query 中提取疑似疾病名进行模糊搜索。

        参数:
            intent: 查询意图

        返回:
            Cypher 查询字符串
        """
        # 从原始问题中取前两个词作为模糊搜索关键词
        query = intent.raw_query
        # 简单启发式：取前6个字符作为可能的疾病名
        guess = query[:6] if len(query) > 6 else query
        logger.info(f"疾病名未识别，模糊搜索: '{guess}'")
        # 使用 CONTAINS 进行模糊匹配
        return (
            "MATCH (d:Disease) "
            "WHERE d.name CONTAINS $disease "
            "RETURN d.name AS name, d.intro AS intro "
            "LIMIT 5"
        )

    def get_return_field(self, intent: QueryIntent) -> str:
        """
        获取查询结果中的关键返回字段名。

        参数:
            intent: 查询意图

        返回:
            返回字段名（如 'result', 'symptom' 等）
        """
        raw_category = intent.category
        normalized = _CATEGORY_ALIASES.get(raw_category, "概述")
        template_info = _CYPHER_TEMPLATES.get(
            normalized, _CYPHER_TEMPLATES["概述"]
        )
        return template_info[1]  # 返回字段名

    def get_category_description(self, intent: QueryIntent) -> str:
        """
        获取查询类别的中文描述。

        参数:
            intent: 查询意图

        返回:
            中文描述字符串
        """
        raw_category = intent.category
        normalized = _CATEGORY_ALIASES.get(raw_category, "概述")
        template_info = _CYPHER_TEMPLATES.get(
            normalized, _CYPHER_TEMPLATES["概述"]
        )
        return template_info[2]  # 描述文本
