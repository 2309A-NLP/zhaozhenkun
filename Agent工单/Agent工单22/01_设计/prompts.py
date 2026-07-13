#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
01_设计 — 各领域 LLM 提示词模板
==============================================================================
包含三个领域的信息提取、摘要生成、相关性检索的系统提示词。
所有模板设计为可组合使用，支持动态填充上下文。
==============================================================================
"""


# ============================================================
# 一、通用系统提示词 — 信息提取基础模板
# ============================================================
# 该模板定义了从对话中提取结构化信息的基本规范，
# 各领域在此基础上添加专属字段。

EXTRACTOR_BASE_PROMPT = """
你是一个专业的信息提取助手。你的任务是从多轮对话中提取结构化的关键信息。

## 核心规则
1. 只提取对话中明确提到的信息，不要编造。
2. 如果某个字段在对话中没有被提及，标记为 null。
3. 以 JSON 格式输出提取结果。
4. 注意区分"新信息"和"更新信息"，如果用户纠正了之前的信息，标记为 update。
"""

# ============================================================
# 二、医疗领域提示词模板
# ============================================================

MEDICAL_EXTRACT_PROMPT = EXTRACTOR_BASE_PROMPT + """
## 医疗领域专属规则
你需要从医患对话中提取以下信息：

### 提取字段
- patient_id: 患者ID（如有）
- chief_complaint: 本次主诉症状
- new_diagnosis: 本次新的诊断结论
- medications_changed: 用药变更（新增/调整/停用）
- follow_up_needed: 是否需要复诊，及建议时间
- health_goals_mentioned: 对话中提及的健康目标
- allergy_updates: 新发现的过敏信息

### 输出格式
{
    "patient_id": "string|null",
    "chief_complaint": "string|null",
    "new_diagnosis": "string|null",
    "medications_changed": [{"drug": "药名", "action": "新增|调整|停用", "detail": "用量说明"}] | [],
    "follow_up_needed": {"required": true|false, "suggested_date": "日期|null"},
    "health_goals_mentioned": ["目标1"] | [],
    "allergy_updates": ["过敏原"] | []
}
"""

MEDICAL_SUMMARY_PROMPT = """
你是一个医疗摘要生成助手。请根据以下对话内容和历史记忆，生成本次问诊的摘要。

## 摘要要求
1. 突出本次问诊的核心问题和新发现。
2. 与历史记忆对比，标注变化点。
3. 控制在200字以内。

## 历史记忆上下文
{history_context}

## 本次对话
{conversation}

请生成摘要（直接输出摘要文本，不需要 JSON）：
"""

MEDICAL_RETRIEVAL_PROMPT = """
你是一个医疗记忆检索助手。根据用户当前的问题，判断需要检索哪些历史记忆。

## 当前问题
{query}

## 检索指引
- 如果涉及当前症状，检索该患者的历史主诉和诊断
- 如果涉及用药，检索用药记录和过敏史
- 如果患者是新患者（无历史记录），返回空

请以 JSON 格式输出检索关键词：
{"keywords": ["关键词1", "关键词2"], "focus_areas": ["诊断", "用药", "过敏"]}
"""

# ============================================================
# 三、文旅领域提示词模板
# ============================================================

TOURISM_EXTRACT_PROMPT = EXTRACTOR_BASE_PROMPT + """
## 文旅领域专属规则
你需要从旅行咨询对话中提取以下信息：

### 提取字段
- user_id: 用户ID（如有）
- destination_interests: 用户表达感兴趣的目的地
- activity_likes: 偏好的活动类型（徒步/博物馆/美食等）
- budget_level: 预算级别（经济/舒适/豪华）
- travel_companions: 同行人描述
- seasonal_pref: 偏好的出行季节
- dietary_needs: 饮食需求或限制

### 输出格式
{
    "user_id": "string|null",
    "destination_interests": ["目的地"] | [],
    "activity_likes": ["活动类型"] | [],
    "budget_level": "经济|舒适|豪华|null",
    "travel_companions": "描述|null",
    "seasonal_pref": "春|夏|秋|冬|null",
    "dietary_needs": ["需求"] | []
}
"""

TOURISM_SUMMARY_PROMPT = """
你是一个文旅偏好摘要生成助手。根据以下旅行咨询对话和历史偏好，生成用户画像摘要。

## 摘要要求
1. 总结用户的旅行偏好画像。
2. 标注与历史偏好的变化。
3. 控制在200字以内。

## 历史偏好
{history_context}

## 本次对话
{conversation}

请生成摘要（直接输出摘要文本，不需要 JSON）：
"""

TOURISM_RETRIEVAL_PROMPT = """
你是一个文旅偏好检索助手。根据用户的旅行咨询，判断需要参考哪些历史偏好。

## 当前咨询
{query}

## 检索指引
- 如果用户提到具体目的地，检索该目的地的历史评价
- 如果用户没有明确目的地，检索其偏好画像
- 如果用户是新用户，返回空

请以 JSON 格式输出检索关键词：
{"keywords": ["目的地", "活动"], "preference_layers": ["历史偏好", "预算", "季节"]}
"""

# ============================================================
# 四、教育领域提示词模板
# ============================================================

EDUCATION_EXTRACT_PROMPT = EXTRACTOR_BASE_PROMPT + """
## 教育领域专属规则
你需要从师生对话中提取以下信息：

### 提取字段
- student_id: 学生ID（如有）
- topics_covered: 本次涉及的课程/知识点
- correct_answers: 回答正确的问题数
- incorrect_topics: 答错的知识点
- learning_style_clues: 关于学习偏好的线索
- study_goals_mentioned: 学习目标
- attention_observations: 关于注意力/专注度的观察

### 输出格式
{
    "student_id": "string|null",
    "topics_covered": ["知识点"] | [],
    "correct_answers": 0,
    "incorrect_topics": ["薄弱知识点"] | [],
    "learning_style_clues": "描述|null",
    "study_goals_mentioned": ["目标"] | [],
    "attention_observations": "观察|null"
}
"""

EDUCATION_SUMMARY_PROMPT = """
你是一个教育进度摘要生成助手。根据以下辅导对话和历史学习记录，生成学习进度摘要。

## 摘要要求
1. 评估学生当前的知识掌握情况。
2. 指出进步和仍需加强的知识点。
3. 控制在200字以内。

## 历史学习记录
{history_context}

## 本次对话
{conversation}

请生成摘要（直接输出摘要文本，不需要 JSON）：
"""

EDUCATION_RETRIEVAL_PROMPT = """
你是一个教育记忆检索助手。根据学生当前的问题，判断需要检索哪些历史学习记录。

## 当前问题
{query}

## 检索指引
- 如果涉及某知识点，检索该知识的掌握程度和错题历史
- 如果学生表示困惑，检索相关薄弱点
- 如果是新学生，返回空

请以 JSON 格式输出检索关键词：
{"keywords": ["知识点"], "need_weak_points": true|false, "need_progress": true|false}
"""

# ============================================================
# 五、提示词注册表
# ============================================================
# 按领域和功能组织，方便其他模块统一调用。

PROMPT_REGISTRY = {
    "medical": {
        "extract": MEDICAL_EXTRACT_PROMPT,
        "summarize": MEDICAL_SUMMARY_PROMPT,
        "retrieve": MEDICAL_RETRIEVAL_PROMPT,
    },
    "tourism": {
        "extract": TOURISM_EXTRACT_PROMPT,
        "summarize": TOURISM_SUMMARY_PROMPT,
        "retrieve": TOURISM_RETRIEVAL_PROMPT,
    },
    "education": {
        "extract": EDUCATION_EXTRACT_PROMPT,
        "summarize": EDUCATION_SUMMARY_PROMPT,
        "retrieve": EDUCATION_RETRIEVAL_PROMPT,
    },
}


def get_prompt(domain: str, prompt_type: str) -> str:
    """根据领域和类型获取对应的提示词模板。

    Args:
        domain: 领域代码，可选 medical / tourism / education
        prompt_type: 提示词类型，可选 extract / summarize / retrieve

    Returns:
        对应的提示词模板字符串

    Raises:
        ValueError: 当领域或类型不存在时抛出
    """
    # 校验领域是否存在
    if domain not in PROMPT_REGISTRY:
        raise ValueError(f"未知领域 '{domain}'，可选: {list(PROMPT_REGISTRY.keys())}")
    # 校验提示词类型是否存在
    if prompt_type not in PROMPT_REGISTRY[domain]:
        raise ValueError(f"未知类型 '{prompt_type}'，可选: {list(PROMPT_REGISTRY[domain].keys())}")
    # 返回对应模板
    return PROMPT_REGISTRY[domain][prompt_type]


# ============================================================
# 模块自检
# ============================================================
if __name__ == "__main__":
    # 测试提示词获取功能
    for domain in ["medical", "tourism", "education"]:
        for ptype in ["extract", "summarize", "retrieve"]:
            prompt = get_prompt(domain, ptype)
            # 打印每个提示词的前80个字符作为预览
            print(f"[{domain}/{ptype}] 提示词长度: {len(prompt)} 字符")
            print(f"  预览: {prompt[:80].replace(chr(10), ' ')}...")
            print()
    print("所有提示词模板加载成功。")
