"""
src/kg_builder.py - 医疗知识图谱构建模块
功能: 解析 medical.json 的 JSONL 数据，设计并构建 Neo4j 医疗知识图谱。
      包括实体节点创建、关系边建立、批量导入和索引优化。
      图谱 Schema:
        Disease(疾病) → 关联 → Department(科室), Drug(药品),
        Complication(并发症), Treatment(治疗方案), Food(食物),
        Symptom(症状), Prevention(预防), Nursing(护理)
工单编号: 人工智能NLP-Agent数字人项目-医疗智能体-健康咨询
"""
import json
import logging
import time
from typing import Optional

from neo4j import GraphDatabase, Driver  # Neo4j 官方 Python 驱动
from neo4j.exceptions import ServiceUnavailable  # 连接异常

from src.models import DiseaseEntity  # 疾病实体数据模型
from src.config import AppConfig  # 应用配置

logger = logging.getLogger(__name__)


# ============================================================
# JSONL 数据解析 — 从 medical.json 读取疾病数据
# ============================================================

def parse_medical_jsonl(file_path: str) -> list[DiseaseEntity]:
    """
    解析 medical.json 的 JSONL 格式数据，返回 DiseaseEntity 列表。

    参数:
        file_path: medical.json 文件路径

    返回:
        DiseaseEntity 对象列表，每个代表一种疾病
    """
    diseases: list[DiseaseEntity] = []  # 收集解析结果
    # 逐行读取 JSONL 文件（每行一个完整的 JSON 对象）
    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()  # 去除首尾空白
            if not line:
                continue  # 跳过空行
            try:
                obj = json.loads(line)  # 解析 JSON 行
                # 安全提取字符串字段（字段可能缺失）
                dept = obj.get("cure_dept", "")
                drug = obj.get("drug", "")
                treat_list = obj.get("treat", "")
                neop = obj.get("neopathy", "")

                # 构建 DiseaseEntity 对象
                disease = DiseaseEntity(
                    disease_id=obj.get("id", ""),
                    name=obj.get("name", ""),
                    intro=obj.get("intro", ""),
                    cause=obj.get("cause", ""),
                    symptom=obj.get("symptom", ""),
                    # 科室可能是列表或逗号分隔的字符串，需要统一处理
                    cure_dept=_parse_list_field(dept),
                    drug=_parse_list_field(drug),
                    treat=_parse_list_field(treat_list),
                    treat_detail=obj.get("treat_detail", ""),
                    treat_prob=obj.get("treat_prob", ""),
                    treat_period=obj.get("treat_period", ""),
                    treat_cost=obj.get("treat_cost", ""),
                    neopathy=_parse_list_field(neop),
                    get_way=obj.get("get_way", ""),
                    easy_get=obj.get("easy_get", ""),
                    get_prob=obj.get("get_prob", ""),
                    insurance=obj.get("insurance", ""),
                    prevent=obj.get("prevent", ""),
                    nursing=obj.get("nursing", ""),
                    can_eat=obj.get("can_eat", ""),
                    not_eat=obj.get("not_eat", ""),
                )
                diseases.append(disease)  # 添加到结果列表
            except json.JSONDecodeError as e:
                # JSON 解析失败时记录警告并跳过
                logger.warning(f"第 {line_num} 行 JSON 解析失败: {e}")
    # 日志输出解析统计
    logger.info(f"解析完成: {len(diseases)} 种疾病")
    return diseases


def _parse_list_field(value) -> list:
    """
    将可能是字符串列表表示、JSON 数组字符串或普通字符串的字段
    统一转换为 Python 列表。

    参数:
        value: 原始字段值（可能是 str/list/None）

    返回:
        清洗后的字符串列表
    """
    if not value:
        return []  # 空值返回空列表
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    # 尝试解析为 JSON 数组字符串（如 '["儿科","内科"]'）
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(v).strip() for v in parsed if str(v).strip()]
        except (json.JSONDecodeError, TypeError):
            pass
        # 按逗号/中文逗号/分号分割
        parts = value.replace("；", ";").replace("，", ",").split(",")
        return [p.strip() for p in parts if p.strip()]
    return []


# ============================================================
# Neo4j 知识图谱构建 — 创建节点和关系
# ============================================================

# 注: Neo4j 导入逻辑已拆分到 src/kg_importer.py，保持本文件 ≤300 行
