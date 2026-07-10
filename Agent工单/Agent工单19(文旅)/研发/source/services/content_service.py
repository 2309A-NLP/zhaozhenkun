# -*- coding: utf-8 -*-  # 指定源码编码。
# 工单编号：人工智能CV-AIGC-19-文旅Agent任务工单-创意策划与内容生成V1.1-20260306  # 标记工单来源。
"""content_service.py - 内容生成与推荐结果组织模块。"""  # 说明当前文件职责。

from services.llm_service import chat_text  # 导入 DeepSeek 文本生成函数。
from services.prompt_service import build_prompt  # 导入提示词构造函数。
from services.prompt_service import get_system_prompt  # 导入系统提示词读取函数。


def _build_titles(brief: dict) -> list:  # 生成标题候选列表。
    spot_name = brief.get("spot") or brief["city"]  # 读取景点名称或回退到城市。
    return [  # 返回标题列表。
        f"{brief['city']}{spot_name}{brief['theme']}创意策划方案",  # 返回标题一。
        f"一场围绕{spot_name}{brief['theme']}展开的文旅新体验",  # 返回标题二。
        f"面向{brief['audience']}的{spot_name}文旅内容提案",  # 返回标题三。
    ]  # 标题列表结束。


def _fallback_content_text(brief: dict) -> str:  # 生成默认传播长文结果。
    spot_name = brief.get("spot") or brief["city"]  # 读取景点名称或回退到城市。
    return (  # 返回默认长文内容。
        f"建议以{spot_name}的{brief['theme']}为传播母题，围绕城市在地文化、沉浸体验与用户分享三个层面展开内容表达。"  # 返回第一段内容。
        f"传播上建议重点覆盖{brief['audience']}常用平台，并通过短视频与图文联动提升触达效率。"  # 返回第二段内容。
    )  # 默认传播长文结束。


def generate_content_package(brief: dict, knowledge: list) -> dict:  # 生成内容传播包。
    prompt = build_prompt("content", brief, knowledge)  # 构造内容场景提示词。
    generated_text = chat_text(prompt, get_system_prompt(), 0.7)  # 调用 DeepSeek 生成传播长文。
    title = _build_titles(brief)[0]  # 取第一条标题作为主标题。
    return {  # 返回内容生成结果。
        "prompt_preview": prompt,  # 回传提示词预览。
        "title": title,  # 返回主标题。
        "content_text": generated_text or _fallback_content_text(brief),  # 返回模型生成或默认传播长文。
        "highlights": [  # 返回亮点文案列表。
            f"用{brief['theme']}串联游览、互动与消费场景。",  # 亮点一。
            f"融入{brief.get('spot') or brief['city']}在地文化元素，增强记忆点。",  # 亮点二。
            f"为{brief['audience']}提供易传播、易参与、易转化的内容表达。",  # 亮点三。
        ],  # 亮点列表结束。
        "social_posts": [  # 返回社交媒体短文案。
            f"来{brief['city']}的{brief.get('spot') or brief['theme']}，解锁一场关于{brief['theme']}的沉浸式旅程。",  # 短文案一。
            f"把{brief.get('spot') or brief['city']}的文化看见、把体验带走、把故事分享出去。",  # 短文案二。
        ],  # 社交文案列表结束。
        "video_script": [  # 返回短视频脚本分镜。
            "镜头1：城市地标开场，字幕点出活动主题。",  # 分镜一。
            "镜头2：切入核心体验节点，展示互动内容。",  # 分镜二。
            "镜头3：游客参与与分享，结尾引导预约或到访。",  # 分镜三。
        ],  # 分镜列表结束。
        "host_lines": [  # 返回主持人口播词。
            f"欢迎来到{brief['city']}的{brief.get('spot') or brief['theme']}，今天我们将开启一场{brief['theme']}主题体验。",  # 口播一。
            "接下来请跟随路线逐步解锁文化亮点与互动玩法。",  # 口播二。
        ],  # 口播列表结束。
    }  # 内容包生成结束。


def generate_recommendation_package(brief: dict, knowledge: list) -> dict:  # 生成路线推荐包。
    prompt = build_prompt("recommend", brief, knowledge)  # 构造推荐场景提示词。
    generated_text = chat_text(prompt, get_system_prompt(), 0.6)  # 调用 DeepSeek 生成推荐长文。
    return {  # 返回推荐结果。
        "route_name": f"{brief['city']}·{brief.get('spot') or brief['theme']}主题一日体验路线",  # 返回路线名称。
        "route_steps": [  # 返回路线节点。
            "上午：城市文化地标导入与主题认知。",  # 节点一。
            "中午：特色餐饮与在地生活体验。",  # 节点二。
            "下午：核心互动活动与创意传播采风。",  # 节点三。
            "傍晚：总结分享与二次传播引导。",  # 节点四。
        ],  # 路线节点结束。
        "fit_people": brief["audience"],  # 返回适合人群。
        "recommendation_text": generated_text or _fallback_content_text(brief),  # 返回模型生成或默认推荐长文。
        "tips": ["提前预约热门场馆。", "预留拍摄与分享时间。", "选择便于传播的话题标签。"],  # 返回出行提示。
        "knowledge": knowledge,  # 返回知识增强内容。
    }  # 推荐结果结束。
