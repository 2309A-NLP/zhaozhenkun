"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-健康咨询 V1.1
Neo4j 知识图谱客户端 —— 查询模板、意图分类与 Cypher 执行
================================================================================
功能：
  1. 自然语言问题 → Cypher 查询模板映射
  2. 意图分类（正则匹配）
  3. Cypher 查询执行（在线 + 离线模式）
  4. 疾病模糊搜索与名称列表获取

注意：本模块的方法通过 monkey-patch 挂载到 Neo4jClient 类上，
      导入本模块即自动完成挂载。
================================================================================
"""
import re
from typing import List, Dict, Tuple

from .neo4j_core import Neo4jClient, NEO4J_DATABASE, _log

# ============================================================
# 问题类型 → Cypher 查询模板
# ============================================================
QUERY_TEMPLATES = {
    # 1. 病原体识别: 百日咳的致病病原体是什么？
    "pathogen": """
        MATCH (d:Disease {name: $disease_name})-[:CAUSED_BY]->(p:Pathogen)
        RETURN d.name AS disease, p.name AS pathogen
    """,
    # 2. 传播途径: 百日咳主要通过什么途径传播？
    "transmission": """
        MATCH (d:Disease {name: $disease_name})-[:TRANSMITTED_BY]->(t:Transmission)
        RETURN d.name AS disease, t.name AS transmission_route
    """,
    # 3. 典型症状: 百日咳最具特征性的临床表现是什么？
    "symptom": """
        MATCH (d:Disease {name: $disease_name})-[:HAS_SYMPTOM]->(s:Symptom)
        RETURN d.name AS disease, collect(s.name) AS symptoms
    """,
    # 4. 实验室诊断: 血常规呈什么特征？
    "diagnosis": """
        MATCH (d:Disease {name: $disease_name})-[:DIAGNOSED_BY]->(dx:Diagnosis)
        RETURN d.name AS disease, dx.name AS diagnostic_method, dx.detail AS detail
    """,
    # 5. 治疗药物: 首选的抗生素是什么？
    "treatment_drug": """
        MATCH (d:Disease {name: $disease_name})-[:TREATED_WITH]->(dr:Drug)
        RETURN d.name AS disease, collect(dr.name) AS drugs, d.treat AS treatment_info
    """,
    # 6. 并发症: 最常见的严重并发症是什么？
    "complication": """
        MATCH (d:Disease {name: $disease_name})-[:HAS_COMPLICATION]->(c:Complication)
        RETURN d.name AS disease, collect(c.name) AS complications
    """,
    # 7. 中医治疗: 中医治疗痉咳期的主方是什么？
    "tcm_treatment": """
        MATCH (d:Disease {name: $disease_name})
        RETURN d.name AS disease, d.treat AS tcm_treatment, d.treat_detail AS detail
    """,
    # 8. 预防/隔离: 隔离期应持续多久？
    "prevention": """
        MATCH (d:Disease {name: $disease_name})-[:PREVENTED_BY]->(p:Prevention)
        RETURN d.name AS disease, collect(p.name) AS prevention_measures
    """,
    # 9. 护理要点: 护理时特别注意什么？
    "nursing": """
        MATCH (d:Disease {name: $disease_name})-[:NEEDS_NURSING]->(n:Nursing)
        RETURN d.name AS disease, collect(n.name) AS nursing_points
    """,
    # 10. 饮食指导: 应避免哪类食物？
    "diet": """
        MATCH (d:Disease {name: $disease_name})
        OPTIONAL MATCH (d)-[:CAN_EAT]->(f1:Food)
        OPTIONAL MATCH (d)-[:AVOID_EAT]->(f2:Food)
        RETURN d.name AS disease,
               collect(DISTINCT f1.name) AS can_eat,
               collect(DISTINCT f2.name) AS not_eat
    """,
    # 科室查询
    "department": """
        MATCH (d:Disease {name: $disease_name})-[:BELONGS_TO]->(dept:Department)
        RETURN d.name AS disease, dept.name AS department
    """,
    # 疾病概述
    "overview": """
        MATCH (d:Disease {name: $disease_name})
        RETURN d.name AS disease, d.intro AS overview, d.cause AS cause, d.get_way AS transmission
    """,
}

# 自然语言 → Cypher 模板 的意图映射
INTENT_PATTERNS = [
    (r"病原|致病.*原|cause|病因|什么引起|什么导致", "pathogen"),
    (r"传播|传染|get_way|怎么.*传|如何.*染", "transmission"),
    (r"症状|表现|symptom|临床.*表现|特征.*表现|什么.*症", "symptom"),
    (r"诊断|检查|血常规|实验室|检验|怎么.*查|如何.*诊断", "diagnosis"),
    (r"并发症|neopathy|合并.*症|继发", "complication"),
    (r"抗生素|药物|吃什么药|首选.*药|治疗.*药|用什么药|drug", "treatment_drug"),
    (r"中医|辨证|方剂|方药|中药|treat(?!.*detail)", "tcm_treatment"),
    (r"预防|隔离|vaccine|prevent|多久.*隔离|隔离.*多久", "prevention"),
    (r"护理|nursing|注意.*什么.*护理|照顾", "nursing"),
    (r"营养|饮食|吃|食物|can_eat|not_eat|忌口|禁忌|避免.*食", "diet"),
    (r"科室|挂什么科|cure_dept|什么.*科室|去.*科", "department"),
    (r"intro|介绍|概述|简介|什么是|是什么病", "overview"),
]


# ================================================================
# 查询方法（将被 monkey-patch 到 Neo4jClient 上）
# ================================================================

def _classify_intent(self, question: str) -> str:
    """将自然语言问题分类到查询模板类型"""
    q = question.lower()
    for pattern, intent in INTENT_PATTERNS:
        if re.search(pattern, q):
            return intent
    return "overview"  # 默认返回概述


def _generate_cypher(self, question: str, disease_name: str) -> Tuple[str, str, dict]:
    """
    根据问题和疾病名生成 Cypher 查询语句

    返回: (cypher_query, intent_type, params)
    """
    intent = self.classify_intent(question)
    template = QUERY_TEMPLATES.get(intent, QUERY_TEMPLATES["overview"])
    params = {"disease_name": disease_name}
    return template, intent, params


def _execute_cypher(self, cypher: str, params: dict) -> List[Dict]:
    """执行 Cypher 查询并返回结果"""
    if self._connected and self._driver:
        try:
            with self._driver.session(database=NEO4J_DATABASE) as session:
                result = session.run(cypher, **params)
                return [record.data() for record in result]
        except Exception as e:
            _log.error("Cypher 执行失败: %s", e)
            return []
    else:
        # 离线模式
        return self._offline_execute(cypher, params)


def _offline_execute(self, cypher: str, params: dict) -> List[Dict]:
    """离线模式：用 Python 字典模拟 Cypher 查询"""
    disease_name = params.get("disease_name", "")
    disease = self._offline_data.get(disease_name, {})
    if not disease:
        return []

    intent = self.classify_intent_from_cypher(cypher)

    # 根据查询意图返回对应的结构化数据
    result_map = {
        "pathogen": [{"disease": disease_name, "pathogen": disease.get("cause", "未知")}],
        "transmission": [{"disease": disease_name, "transmission_route": disease.get("get_way", "未知")}],
        "symptom": [{"disease": disease_name, "symptoms": self._split_value(disease.get("symptom", ""))}],
        "diagnosis": [{"disease": disease_name,
                      "diagnostic_method": "实验室检查",
                      "detail": disease.get("treat_detail", "")}],
        "treatment_drug": [{"disease": disease_name,
                          "drugs": self._split_value(disease.get("drug", "")),
                          "treatment_info": disease.get("treat", "")}],
        "complication": [{"disease": disease_name,
                        "complications": self._split_value(disease.get("neopathy", ""))}],
        "tcm_treatment": [{"disease": disease_name,
                         "tcm_treatment": disease.get("treat", ""),
                         "detail": disease.get("treat_detail", "")}],
        "prevention": [{"disease": disease_name,
                      "prevention_measures": self._split_value(disease.get("prevent", ""))}],
        "nursing": [{"disease": disease_name,
                   "nursing_points": self._split_value(disease.get("nursing", ""))}],
        "diet": [{"disease": disease_name,
                 "can_eat": self._split_value(disease.get("can_eat", "")),
                 "not_eat": self._split_value(disease.get("not_eat", ""))}],
        "department": [{"disease": disease_name,
                      "department": disease.get("cure_dept", "")}],
        "overview": [{"disease": disease_name,
                     "overview": disease.get("intro", ""),
                     "cause": disease.get("cause", ""),
                     "transmission": disease.get("get_way", "")}],
    }
    return result_map.get(intent, result_map["overview"])


def _classify_intent_from_cypher(self, cypher: str) -> str:
    """从 Cypher 语句反推意图类型（离线模式用）"""
    rel_keywords = {
        "pathogen": "CAUSED_BY", "transmission": "TRANSMITTED_BY",
        "symptom": "HAS_SYMPTOM", "diagnosis": "DIAGNOSED_BY",
        "treatment_drug": "TREATED_WITH", "complication": "HAS_COMPLICATION",
        "tcm_treatment": "d.treat AS", "prevention": "PREVENTED_BY",
        "nursing": "NEEDS_NURSING", "diet": "CAN_EAT|AVOID_EAT",
        "department": "BELONGS_TO", "overview": "d.intro AS",
    }
    for intent, keyword in rel_keywords.items():
        if re.search(keyword, cypher):
            return intent
    return "overview"


def _search_diseases(self, keyword: str, limit: int = 5) -> List[Dict]:
    """模糊搜索疾病（用于找不到精确匹配时）"""
    if self._connected and self._driver:
        try:
            with self._driver.session(database=NEO4J_DATABASE) as session:
                result = session.run("""
                    MATCH (d:Disease)
                    WHERE d.name CONTAINS $kw OR d.intro CONTAINS $kw
                    RETURN d.name AS name, d.intro AS intro
                    LIMIT $limit
                """, kw=keyword, limit=limit)
                return [r.data() for r in result]
        except Exception:
            pass

    # 离线模式搜索
    results = []
    for name, data in self._offline_data.items():
        if keyword in name or keyword in data.get("intro", ""):
            results.append({"name": name, "intro": data.get("intro", "")[:200]})
        if len(results) >= limit:
            break
    return results


def _get_disease_names(self) -> List[str]:
    """获取所有疾病名称列表"""
    if self._connected and self._driver:
        try:
            with self._driver.session(database=NEO4J_DATABASE) as session:
                result = session.run("MATCH (d:Disease) RETURN d.name AS name ORDER BY d.name")
                return [r["name"] for r in result]
        except Exception:
            pass
    return sorted(self._offline_data.keys())


# ================================================================
# 将查询方法 monkey-patch 到 Neo4jClient 类上
# ================================================================
Neo4jClient.classify_intent = _classify_intent
Neo4jClient.generate_cypher = _generate_cypher
Neo4jClient.execute_cypher = _execute_cypher
Neo4jClient._offline_execute = _offline_execute
Neo4jClient.classify_intent_from_cypher = _classify_intent_from_cypher
Neo4jClient.search_diseases = _search_diseases
Neo4jClient.get_disease_names = _get_disease_names
