# -*- coding: utf-8 -*-  # 指定源码编码。
# 工单编号：人工智能CV-AIGC-19-文旅Agent任务工单-创意策划与内容生成V1.1-20260306  # 标记工单来源。
"""planner_service.py - 用户 brief 结构化与策划框架生成模块。"""  # 说明当前文件职责。


from services.llm_service import chat_text  # 导入 DeepSeek 文本生成函数。
from services.prompt_service import build_prompt  # 导入业务提示词构造函数。
from services.prompt_service import get_system_prompt  # 导入系统提示词读取函数。


def build_brief(data: dict, config: dict) -> dict:  # 把用户输入整理成标准 brief。
    theme = str(data.get("theme", "")).strip() or config["DEFAULT_THEME"]  # 读取主题并处理默认值。
    city = str(data.get("city", "")).strip() or config["DEFAULT_CITY"]  # 读取城市并处理默认值。
    spot = str(data.get("spot", "")).strip()  # 读取景点名称。
    region = str(data.get("region", "")).strip()  # 读取地区名称。
    return {  # 返回统一 brief 结构。
        "theme": theme,  # 保存主题。
        "city": city,  # 保存城市。
        "spot": spot,  # 保存景点。
        "region": region,  # 保存地区。
        "audience": str(data.get("audience", "大众游客")).strip() or "大众游客",  # 保存目标人群。
        "duration": str(data.get("duration", "1天")).strip() or "1天",  # 保存持续时间。
        "budget": str(data.get("budget", "中等预算")).strip() or "中等预算",  # 保存预算信息。
        "keywords": str(data.get("keywords", "文化、创意、传播")).strip() or "文化、创意、传播",  # 保存关键词。
        "goal": str(data.get("goal", "提升体验与传播")).strip() or "提升体验与传播",  # 保存业务目标。
    }  # brief 结构结束。


def _fallback_plan_text(brief: dict) -> str:  # 生成默认策划长文结果。
    spot_name = brief.get("spot") or brief["city"]  # 读取景点名称或回退到城市。
    return (  # 返回默认长文结果。
        f"建议围绕{spot_name}的{brief['theme']}建立主题定位，先用城市文化故事做开场，再安排核心互动体验，最后通过社交传播完成扩散。"  # 返回第一段建议。
        f"在执行上重点服务{brief['audience']}，并结合{brief['budget']}配置活动资源与传播节奏。"  # 返回第二段建议。
    )  # 默认策划长文结束。


def generate_plan_outline(brief: dict, knowledge: list) -> dict:  # 生成结构化策划结果。
    spot_name = brief.get("spot") or brief["city"]  # 读取景点名称或回退到城市。
    highlights = [  # 定义策划亮点列表。
        f"围绕{brief['theme']}打造沉浸式体验主线",  # 亮点一。
        f"结合{spot_name}在地文化做差异化表达",  # 亮点二。
        f"面向{brief['audience']}设计传播与消费转化路径",  # 亮点三。
    ]  # 亮点列表结束。
    activities = [  # 定义活动安排列表。
        {"name": "主题开场", "detail": f"用故事化方式引入{brief['theme']}价值。"},  # 活动一。
        {"name": "核心体验", "detail": "设置互动打卡、文化解读、创意演绎等关键环节。"},  # 活动二。
        {"name": "传播扩散", "detail": "结合社交媒体话题、UGC 征集与短视频素材产出。"},  # 活动三。
    ]  # 活动列表结束。
    prompt = build_prompt("plan", brief, knowledge)  # 构造策划场景提示词。
    generated_text = chat_text(prompt, get_system_prompt(), 0.6)  # 调用 DeepSeek 生成策划长文。
    return {  # 返回策划结构化内容。
        "brief": brief,  # 回传结构化 brief。
        "positioning": f"这是一个以{brief['theme']}为核心、依托{spot_name}场景、服务于{brief['audience']}的文旅策划方案。",  # 返回定位描述。
        "highlights": highlights,  # 返回亮点列表。
        "activities": activities,  # 返回活动流程列表。
        "knowledge": knowledge,  # 返回知识增强结果。
        "plan_text": generated_text or _fallback_plan_text(brief),  # 返回模型生成或默认策划长文。
        "risk_tips": ["注意高峰期人流组织。", "提前准备社交传播素材。", "设置雨天替代方案。"],  # 返回风险提醒。
    }  # 策划结果结束。
