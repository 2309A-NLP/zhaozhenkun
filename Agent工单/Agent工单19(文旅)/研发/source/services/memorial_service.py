# -*- coding: utf-8 -*-  # 指定源码编码。
# 工单编号：人工智能CV-AIGC-19-文旅Agent任务工单-创意策划与内容生成V1.1-20260306  # 标记工单来源。
"""memorial_service.py - 纪念内容生成与分享文案组织模块。"""  # 说明当前文件职责。

from services.llm_service import chat_text  # 导入 DeepSeek 文本生成函数。
from services.prompt_service import build_prompt  # 导入业务提示词构造函数。
from services.prompt_service import get_system_prompt  # 导入系统提示词读取函数。


def _fallback_memorial_text(brief: dict) -> str:  # 生成默认纪念长文结果。
    spot_name = brief.get("spot") or brief["city"]  # 读取景点名称或回退到城市。
    return (  # 返回默认纪念长文内容。
        f"建议围绕{spot_name}的{brief['theme']}体验设计游客纪念表达，突出在地文化、游玩记忆与社交分享三个方向。"  # 返回第一段内容。
        f"纪念内容可面向{brief['audience']}生成更具情绪价值和传播感的寄语、海报与相册文案。"  # 返回第二段内容。
    )  # 默认纪念长文结束。


def generate_memorial_package(brief: dict, knowledge: list) -> dict:  # 生成纪念内容结果包。
    spot_name = brief.get("spot") or brief["city"]  # 读取景点名称或回退到城市。
    prompt = build_prompt("memorial", brief, knowledge)  # 构造纪念内容场景提示词。
    generated_text = chat_text(prompt, get_system_prompt(), 0.7)  # 调用 DeepSeek 生成纪念长文。
    return {  # 返回纪念内容结果。
        "memorial_text": generated_text or _fallback_memorial_text(brief),  # 返回模型生成或默认纪念长文。
        "postcard_text": f"来自{brief['city']}{spot_name}的问候：愿你在{brief['theme']}主题旅程里，把风景、故事与当下心情一起珍藏。",  # 返回明信片寄语。
        "poster_title": f"{brief['city']}·{spot_name}·{brief['theme']}纪念海报",  # 返回纪念海报标题。
        "album_cover": f"{spot_name}{brief['theme']}主题旅程纪念册",  # 返回电子相册封面文案。
        "virtual_photo_prompt": f"以{spot_name}在地场景为背景，突出{brief['theme']}氛围，生成适合{brief['audience']}分享的文旅纪念合影画面。",  # 返回虚拟合影提示词。
        "share_copy": f"我在{brief['city']}的{spot_name}完成了一次{brief['theme']}主题体验，把故事带回家，也把记忆分享给朋友。",  # 返回社交分享文案。
        "souvenir_title": f"{brief['city']}{spot_name}{brief['theme']}专属纪念卡",  # 返回纪念卡标题。
    }  # 纪念内容结果结束。
