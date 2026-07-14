"""文件功能：集中生成问答、多模态理解和数字人任务的提示词。"""

from __future__ import annotations  # 启用延后类型注解支持。


def build_dialogue_system_prompt(persona_name: str, voice_style: str, knowledge_text: str, image_summary: str) -> str:  # 生成问答系统提示词。
    knowledge_block = knowledge_text.strip() or "暂无知识库资料，请基于用户输入进行审慎回答。"  # 准备知识库文本块。
    image_block = image_summary.strip() or "本轮没有额外图片分析结果。"  # 准备图像分析文本块。
    return (  # 返回完整系统提示词。
        f"你是一名个人数字人的对话内核。\n"  # 说明助手角色。
        f"请使用{voice_style}的表达风格回答问题。\n"  # 说明语言风格。
        f"当前数字人名称：{persona_name or '未命名数字人'}。\n"  # 注入数字人名称。
        f"知识库摘要：\n{knowledge_block}\n\n"  # 注入知识库上下文。
        f"图像理解摘要：\n{image_block}\n\n"  # 注入多模态摘要。
        "请输出准确、克制、适合口播的中文答案，并优先使用知识库信息。"  # 规定输出要求。
    )  # 结束系统提示词拼接。


def build_visual_prompt(question: str) -> str:  # 生成图像理解提示词。
    return (  # 返回图像理解提示词。
        "请先识别图像中的人物、场景、动作、服装、镜头信息，再结合问题给出简洁结论。\n"  # 规定分析维度。
        f"用户问题：{question.strip()}"  # 注入用户问题。
    )  # 结束图像理解提示词。


def build_avatar_script_prompt(answer_text: str, motion_style: str) -> str:  # 生成数字人播报脚本提示词。
    return (  # 返回数字人脚本提示词。
        "请把下面的答案整理成适合数字人口播的短脚本。\n"  # 规定输出目标。
        f"动作风格：{motion_style or '自然'}。\n"  # 注入动作风格。
        "输出要求：一句一行，节奏自然，不要添加解释说明。\n"  # 规定脚本格式。
        f"原始答案：{answer_text.strip()}"  # 注入待整理答案。
    )  # 结束数字人脚本提示词拼接。
