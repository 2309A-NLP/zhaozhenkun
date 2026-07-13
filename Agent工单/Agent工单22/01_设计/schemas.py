#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
01_设计 — 多领域记忆 Schema 定义与系统架构文档
==============================================================================
基于 mem0 的多领域智能体长期记忆系统
覆盖领域：医疗 / 文旅 / 教育
==============================================================================
"""

# ============================================================
# 一、医疗领域记忆 Schema
# ============================================================
# 核心设计思路：
#   医疗智能体需要记住患者的基本信息、病史、用药和随访记录，
#   确保复诊时不重复问询，提供连续的诊疗建议。
# ============================================================

MEDICAL_SCHEMA = {
    # --- 领域标识 ---
    "domain": "medical",  # 领域代码，用于 mem0 的 agent_id 过滤
    "domain_name": "医疗",  # 中文领域名

    # --- 记忆字段定义 ---
    # 每个字段包含：字段名、类型、中文描述、是否必填
    "fields": {
        "patient_id": {
            "type": "string",
            "description": "患者唯一标识ID",
            "required": True,
        },
        "chief_complaint": {
            "type": "string",
            "description": "主诉症状，患者描述的不适",
            "required": True,
        },
        "diagnosis_history": {
            "type": "list",
            "description": "历史诊断记录列表，每次诊断含日期/疾病/医生",
            "required": False,
        },
        "medication_records": {
            "type": "list",
            "description": "用药记录，含药品名/剂量/频次/起止日期",
            "required": False,
        },
        "follow_up_notes": {
            "type": "list",
            "description": "随访记录，含日期/要点/医生建议",
            "required": False,
        },
        "health_goals": {
            "type": "list",
            "description": "患者个人健康目标，如减重5kg/控制血糖",
            "required": False,
        },
        "allergies": {
            "type": "list",
            "description": "过敏史，含药物/食物/其他过敏原",
            "required": False,
        },
        "vital_signs": {
            "type": "dict",
            "description": "最近一次生命体征：血压/心率/体温等",
            "required": False,
        },
    },

    # --- 记忆写入触发条件 ---
    "write_triggers": [
        "consultation_end",  # 问诊结束时自动摘要写入
        "prescription_issued",  # 开药时记录用药信息
        "diagnosis_made",  # 确诊时记录诊断
    ],

    # --- 记忆读取触发条件 ---
    "read_triggers": [
        "consultation_start",  # 新问诊开始时检索历史记忆
        "patient_asks_history",  # 患者主动询问病史时
    ],

    # --- 记忆过期策略 ---
    "retention": {
        "default_days": 365 * 2,  # 默认保留2年
        "critical_days": 365 * 5,  # 关键信息保留5年（诊断/过敏）
    },
}


# ============================================================
# 二、文旅领域记忆 Schema
# ============================================================
# 核心设计思路：
#   文旅智能体需要了解用户的旅行偏好、历史目的地和消费习惯，
#   从而推荐更符合个人口味的行程。
# ============================================================

TOURISM_SCHEMA = {
    # --- 领域标识 ---
    "domain": "tourism",  # 领域代码
    "domain_name": "文旅",  # 中文领域名

    # --- 记忆字段定义 ---
    "fields": {
        "user_id": {
            "type": "string",
            "description": "用户唯一标识ID",
            "required": True,
        },
        "preferred_destinations": {
            "type": "list",
            "description": "感兴趣的目的地列表，含城市/景点名称",
            "required": False,
        },
        "activity_preferences": {
            "type": "list",
            "description": "偏好的活动类型：徒步/博物馆/美食/购物/摄影等",
            "required": False,
        },
        "travel_history": {
            "type": "list",
            "description": "历史旅行记录，含目的地/日期/评分/备注",
            "required": False,
        },
        "budget_preference": {
            "type": "string",
            "description": "消费偏好档次：经济/舒适/豪华",
            "required": False,
        },
        "companion_info": {
            "type": "dict",
            "description": "同行人信息：家人/朋友/独自/伴侣，含人数",
            "required": False,
        },
        "seasonal_preference": {
            "type": "list",
            "description": "偏好的出行季节：春/夏/秋/冬",
            "required": False,
        },
        "dietary_constraints": {
            "type": "list",
            "description": "饮食限制：素食/清真/过敏源等",
            "required": False,
        },
    },

    # --- 记忆写入触发条件 ---
    "write_triggers": [
        "trip_plan_completed",  # 行程规划完成时保存偏好
        "user_expresses_preference",  # 用户表达新偏好时
        "trip_review_submitted",  # 用户提交旅行评价时
    ],

    # --- 记忆读取触发条件 ---
    "read_triggers": [
        "new_trip_inquiry",  # 新旅行咨询时检索历史偏好
        "destination_recommendation",  # 推荐目的地时参考历史
    ],

    # --- 记忆过期策略 ---
    "retention": {
        "default_days": 365,  # 偏好等默认保留1年
        "history_days": 365 * 3,  # 旅行历史保留3年
    },
}


# ============================================================
# 三、教育领域记忆 Schema
# ============================================================
# 核心设计思路：
#   教育智能体需要追踪学生的学习进度、知识薄弱点和学习风格，
#   提供个性化的辅导和复习建议。
# ============================================================

EDUCATION_SCHEMA = {
    # --- 领域标识 ---
    "domain": "education",  # 领域代码
    "domain_name": "教育",  # 中文领域名

    # --- 记忆字段定义 ---
    "fields": {
        "student_id": {
            "type": "string",
            "description": "学生唯一标识ID",
            "required": True,
        },
        "course_progress": {
            "type": "dict",
            "description": "各课程学习进度：课程名→完成百分比",
            "required": True,
        },
        "knowledge_graph": {
            "type": "dict",
            "description": "知识掌握图谱：知识点→掌握程度(1-5)",
            "required": False,
        },
        "weak_points": {
            "type": "list",
            "description": "易错知识点列表，记录反复出错的题目类型",
            "required": False,
        },
        "learning_style": {
            "type": "string",
            "description": "学习风格偏好：视觉/听觉/动手/阅读",
            "required": False,
        },
        "interaction_history": {
            "type": "list",
            "description": "历史问答记录摘要，含日期/问题/回答正确与否",
            "required": False,
        },
        "study_goals": {
            "type": "list",
            "description": "学习目标列表，如通过某考试/掌握某技能",
            "required": False,
        },
        "attention_span": {
            "type": "string",
            "description": "注意力时长评估：短(<15min)/中/长(>30min)",
            "required": False,
        },
    },

    # --- 记忆写入触发条件 ---
    "write_triggers": [
        "lesson_completed",  # 课程完成时更新进度
        "quiz_submitted",  # 测验提交时分析错题
        "student_expresses_confusion",  # 学生表达疑惑时记录薄弱点
    ],

    # --- 记忆读取触发条件 ---
    "read_triggers": [
        "session_start",  # 学习会话开始时检索历史
        "new_question_asked",  # 新问题提出时检索相关知识
        "review_requested",  # 学生请求复习时
    ],

    # --- 记忆过期策略 ---
    "retention": {
        "default_days": 365,  # 默认保留1年（一个学年）
        "weak_points_days": 180,  # 薄弱点每学期刷新
    },
}


# ============================================================
# 四、系统架构（三层：智能体层 → 记忆处理层 → 基础设施层）
# 数据流：对话结束 → agent_bridge → extractor → memory_processor → mem0
#        新对话开始 → agent_bridge 检索 → 返回上下文 → 智能体
# ============================================================

# 导出所有 schema 供其他模块使用
ALL_SCHEMAS = {
    "medical": MEDICAL_SCHEMA,
    "tourism": TOURISM_SCHEMA,
    "education": EDUCATION_SCHEMA,
}

# 领域配置汇总表
DOMAIN_CONFIG = {
    "medical": {
        "agent_id": "medical_agent",
        "default_user_prefix": "PAT",
        "memory_tags": ["诊断", "用药", "随访", "过敏"],
    },
    "tourism": {
        "agent_id": "tourism_agent",
        "default_user_prefix": "TRV",
        "memory_tags": ["目的地", "偏好", "预算", "旅行"],
    },
    "education": {
        "agent_id": "education_agent",
        "default_user_prefix": "STU",
        "memory_tags": ["课程", "知识点", "错题", "目标"],
    },
}

# ============================================================
# 模块自检（直接运行时打印 schema 摘要）
# ============================================================
if __name__ == "__main__":
    # 打印各领域 schema 概览
    for domain_code, schema in ALL_SCHEMAS.items():
        print(f"\n{'='*50}")
        print(f"领域: {schema['domain_name']} ({schema['domain']})")
        print(f"字段数: {len(schema['fields'])}")
        print(f"写入触发: {schema['write_triggers']}")
        print(f"读取触发: {schema['read_triggers']}")
        # 列出所有字段及其描述
        for field_name, field_info in schema["fields"].items():
            required_mark = " *必填" if field_info["required"] else ""
            print(f"  - {field_name}: {field_info['description']}{required_mark}")
    print(f"\n架构已定义，共 {len(ALL_SCHEMAS)} 个领域。")
