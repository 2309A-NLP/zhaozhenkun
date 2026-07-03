"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-健康咨询 V1.1
Neo4j 知识图谱客户端 —— 兼容性重导出模块
================================================================================

本模块已拆分为两个子模块:
  - kg/neo4j_core.py    —— Neo4jClient 核心类、连接管理、图谱构建、get_neo4j_client()
  - kg/neo4j_queries.py —— QUERY_TEMPLATES、INTENT_PATTERNS、意图分类、Cypher 执行

导入本模块会自动组装完整的 Neo4jClient（含 monkey-patch 的查询方法），
保持向后兼容。原有导入语句无需修改:

    from kg.neo4j_client import Neo4jClient, get_neo4j_client
    from kg.neo4j_client import QUERY_TEMPLATES, INTENT_PATTERNS
================================================================================
"""
# 先导入核心模块（带有基础 Neo4jClient 类）
from .neo4j_core import (
    Neo4jClient,
    get_neo4j_client,
    NEO4J_URI,
    NEO4J_USER,
    NEO4J_PASSWORD,
    NEO4J_DATABASE,
    _log,
)

# 导入查询模块以触发 monkey-patch（将查询方法挂载到 Neo4jClient 上）
from .neo4j_queries import (
    QUERY_TEMPLATES,
    INTENT_PATTERNS,
    _classify_intent,
    _generate_cypher,
    _execute_cypher,
    _offline_execute,
    _classify_intent_from_cypher,
    _search_diseases,
    _get_disease_names,
)

# 重新导出所有公开符号，使 `from kg.neo4j_client import *` 行为一致
__all__ = [
    "Neo4jClient",
    "get_neo4j_client",
    "QUERY_TEMPLATES",
    "INTENT_PATTERNS",
    "NEO4J_URI",
    "NEO4J_USER",
    "NEO4J_PASSWORD",
    "NEO4J_DATABASE",
]
