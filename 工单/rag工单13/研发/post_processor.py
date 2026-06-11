"""
post_processor.py - RAG工单13 后处理与响应格式化模块
需求: 工单要求分析"后处理与响应格式化"阶段的运行时间
功能: 1.回答格式化 2.冗余截断 3.参考来源标注 4.置信度评估 5.全程计时
"""
import logging
import re
import time

logger = logging.getLogger(__name__)


def format_answer(raw_answer: str) -> str:
    """需求：回答格式化——去除LLM生成中的冗余开头/结尾"""
    formatted = raw_answer.strip()

    # 去除常见冗余开头
    redundant_starts = [
        r"^好的[，,]\s*",
        r"^根据[以]?[上上]?(文献|资料|内容|信息)[，,]\s*",
        r"^我来回答[：:]\s*",
        r"^以下是[对关]?(于)?.*?的回答[：:]\s*",
        r"^回答[：:]\s*",
    ]
    for pattern in redundant_starts:
        formatted = re.sub(pattern, "", formatted, flags=re.IGNORECASE)

    # 去除常见冗余结尾
    redundant_ends = [
        r"[，,]?希望[以对]?[上这]?(回答|信息|内容)?[对关].*?有帮助[。!！]?$",
        r"[，,]?如果[你您]还[有想].*$",
        r"[，,]?以上[就]?是.*?回答[。!！]?$",
        r"[，,]?欢迎继续提问[。!！]?$",
        r"[，,]?如有[其更]他问题[，,].*$",
    ]
    for pattern in redundant_ends:
        formatted = re.sub(pattern, "", formatted, flags=re.IGNORECASE)

    # 去除多余换行（保留最多2个连续换行）
    formatted = re.sub(r"\n{3,}", "\n\n", formatted)

    return formatted.strip()


def add_reference(formatted_answer: str, context_parts: list) -> str:
    """需求：参考来源标注——在回答末尾添加检索来源引用"""
    if not context_parts:
        return formatted_answer

    # 收集来源页码
    pages = set()
    for part in context_parts[:3]:  # 只标注前3个来源
        match = re.search(r"第(\d+)页", part)
        if match:
            pages.add(match.group(1))

    if pages:
        ref_line = f"\n\n📖 参考来源：第{', '.join(sorted(pages, key=int))}页"
        return formatted_answer + ref_line
    return formatted_answer


def assess_confidence(formatted_answer: str, context_parts: list) -> dict:
    """需求：置信度评估——判断回答的可靠性"""
    if not formatted_answer or formatted_answer.startswith("[生成失败]"):
        return {"level": "low", "score": 0.0, "reason": "生成失败或无内容"}

    # 简单启发式：回答长度 + 是否有引用
    score = 0.5  # 基础分
    if len(formatted_answer) > 100:
        score += 0.2
    if len(formatted_answer) > 300:
        score += 0.1
    if context_parts and len(context_parts) >= 3:
        score += 0.1
    if "参考来源" in formatted_answer:
        score += 0.1
    score = min(score, 1.0)

    if score >= 0.8:
        level = "high"
    elif score >= 0.5:
        level = "medium"
    else:
        level = "low"

    return {"level": level, "score": round(score, 2)}


def post_process(raw_answer: str, context_parts: list, max_length: int = 1200) -> dict:
    """
    需求：后处理与响应格式化阶段 — 完整处理流程（带计时）
    返回: {formatted_answer, confidence, processing_time}
    """
    t0 = time.time()

    # Step 1: 格式化
    formatted = format_answer(raw_answer)

    # Step 2: 长度截断（避免过长回答影响前端渲染）
    if len(formatted) > max_length:
        # 尝试在句号处截断
        cutoff = formatted.rfind("。", 0, max_length)
        if cutoff > max_length // 2:
            formatted = formatted[:cutoff + 1] + "\n\n(回答较长，已截断)"
        else:
            formatted = formatted[:max_length] + "...\n\n(回答较长，已截断)"

    # Step 3: 添加参考来源
    formatted_with_ref = add_reference(formatted, context_parts)

    # Step 4: 置信度评估
    confidence = assess_confidence(formatted_with_ref, context_parts)

    elapsed = time.time() - t0

    return {
        "formatted_answer": formatted_with_ref,
        "raw_answer": raw_answer,
        "confidence": confidence,
        "processing_time": round(elapsed, 4)
    }
