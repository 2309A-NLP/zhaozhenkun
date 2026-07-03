"""
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-健康咨询 V1.1
知识图谱模块 —— 双后端支持（Neo4j 图数据库 + Python 内存搜索）
"""
from kg.knowledge import answer_question, search_disease, get_disease_by_name
from kg.neo4j_client import get_neo4j_client, Neo4jClient
