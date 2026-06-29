"""
src/models.py - 数据模型定义
功能: 定义知识图谱中的实体、关系和 Agent 请求/响应数据模型。
      使用 dataclass 提供类型安全的实体表示。
工单编号: 人工智能NLP-Agent数字人项目-医疗智能体-健康咨询
"""
from dataclasses import dataclass, field
from typing import Optional


# ============================================================
# 知识图谱实体模型 — 对应 medical.json 中的字段
# ============================================================

@dataclass
class DiseaseEntity:
    """
    疾病实体，对应知识图谱中的 Disease 节点。

    包含疾病的基本信息、病因、症状、治疗方案、
    并发症、预防措施、护理建议等完整医疗数据。
    """
    # 疾病唯一ID（来自 medical.json）
    disease_id: str = ""
    # 疾病名称
    name: str = ""
    # 疾病简介/概述
    intro: str = ""
    # 病因/发病原因
    cause: str = ""
    # 典型症状（JSONL数据中始终为列表，如 ['干咳', '惊厥', ...]）
    symptom: list = field(default_factory=list)
    # 就诊科室列表
    cure_dept: list = field(default_factory=list)
    # 治疗药品列表
    drug: list = field(default_factory=list)
    # 治疗方案列表
    treat: list = field(default_factory=list)
    # 详细治疗说明
    treat_detail: str = ""
    # 治愈概率
    treat_prob: str = ""
    # 治疗周期
    treat_period: str = ""
    # 治疗费用参考
    treat_cost: str = ""
    # 并发症列表
    neopathy: list = field(default_factory=list)
    # 传播途径
    get_way: str = ""
    # 易感人群
    easy_get: str = ""
    # 发病率
    get_prob: str = ""
    # 是否医保
    insurance: str = ""
    # 预防措施
    prevent: str = ""
    # 护理建议
    nursing: str = ""
    # 建议食用食物
    can_eat: str = ""
    # 禁忌食物
    not_eat: str = ""


@dataclass
class QueryIntent:
    """
    用户查询意图解析结果。

    Agent 首先将自然语言问题解析为结构化的查询意图，
    包括目标疾病、查询类别和关键实体。
    """
    # 目标疾病名称
    disease: str = ""
    # 查询类别（如：病原体/症状/治疗/药物/并发症/预防/护理/饮食/诊断/传播）
    category: str = ""
    # 原始用户问题
    raw_query: str = ""
    # 提取的关键词列表
    keywords: list = field(default_factory=list)


@dataclass
class AgentResponse:
    """
    Agent 最终响应模型。

    包含完整的 ReAct 推理链路结果和执行状态。
    """
    # 原始问题
    query: str = ""
    # Agent 思考步骤列表 (每步包含 thought/action/observation)
    reasoning_steps: list = field(default_factory=list)
    # 知识图谱查询结果
    kg_result: list = field(default_factory=list)
    # 最终答案
    answer: str = ""
    # 响应耗时（毫秒）
    latency_ms: float = 0.0
    # 是否成功
    success: bool = False
    # 错误信息
    error: str = ""
