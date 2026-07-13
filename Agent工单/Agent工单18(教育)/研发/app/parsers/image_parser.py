# -*- coding: utf-8 -*-  # 工单18：指定源码编码为 UTF-8。
"""image_parser.py - 工单18智能助教的图片知识解析模块。"""  # 工单18：声明当前文件功能。

from __future__ import annotations  # 工单18：启用延迟类型注解。

from app.llm_client import llm_client  # 工单18：导入统一大模型客户端。


VISION_SYSTEM_PROMPT = "你是教育场景中的视觉助教，请识别图片中的题目、文字、图表或板书，并输出结构化学习说明。"  # 工单18：定义视觉解析系统提示词。
VISION_USER_PROMPT = "请提取图片中的主要文字与关键信息，并给出适合知识库入库的摘要。"  # 工单18：定义视觉解析用户提示词。


def parse_image(file_name: str, file_bytes: bytes, provider: str = "qwen") -> dict:  # 工单18：解析图片并尽量调用视觉模型生成知识文本。
    try:  # 工单18：优先尝试调用视觉模型完成图片理解。
        result = llm_client.chat_vision(provider, VISION_SYSTEM_PROMPT, VISION_USER_PROMPT, file_name, file_bytes)  # 工单18：调用视觉模型识别图片内容。
        text = result["answer"].strip() or f"图片资源 {file_name} 未返回有效视觉解析文本。"  # 工单18：读取并兜底视觉解析结果。
    except Exception:  # 工单18：在视觉接口不可用时退回可解释占位文本。
        text = f"图片资源 {file_name} 已上传，但当前环境未完成视觉解析，建议使用千问视觉模型进一步识别题目、图表或板书内容。"  # 工单18：写入视觉降级提示信息。
    chunk = {"content": text, "summary": text[:60], "location": {"kind": "image"}, "modality": "image"}  # 工单18：构造图片型结构化片段。
    return {"content_text": text, "chunks": [chunk]}  # 工单18：返回统一解析结果。
