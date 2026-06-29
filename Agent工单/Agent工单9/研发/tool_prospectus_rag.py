# -*- coding: utf-8 -*-
"""
tool_prospectus_rag.py — 招股书 RAG 问答引擎（阶段3-4: 段落提取 + AI问答）
--------------------------------------------------------------
功能: 接收已匹配的最佳招股书文件，提取最相关段落并进行两轮 RAG 问答。
      精准词定位 + 通用词补充 + 数据扫荡（正则匹配数字+单位序列）。
      保证段落 + 相关性排序 + 两轮 RAG（标准 + 数据扫荡回退）。

被 tool_prospectus.py 的 tool_prospectus_qa 调用。

工单编号: 人工智能NLP-Agent数字人项目-智能体任务
所属目录: 研发
"""
import re          # 正则（数字数据匹配、关键词提取）
import logging     # 日志记录

from tool_utils import call_deepseek  # 共享 DeepSeek API 调用

logger = logging.getLogger("agent.tools")


def prospectus_rag_answer(
    best_file: str,
    best_name: str,
    query: str,
    company_candidates: list,
    all_words: list,
) -> str:
    """招股书 RAG 问答 — 段落提取 + 两轮 AI 问答

    参数:
        best_file (str): 最佳匹配的招股书文本全文
        best_name (str): 匹配到的文件名（用于日志）
        query (str): 用户原始查询
        company_candidates (list): 阶段1提取的公司名候选列表
        all_words (list): 从query中提取的关键词列表

    返回:
        str: AI 生成的答案
    """
    # ================================================================
    # 阶段3: 段落提取 + 相关性排序
    # ================================================================

    # --- 构建查询关键词集 ---
    query_keywords = [w for w in all_words if len(w) >= 2]
    # 加入公司名片段
    for cand in company_candidates:
        for n in [2, 3, 4]:
            for i in range(len(cand) - n + 1):
                piece = cand[i:i + n]
                if piece not in query_keywords:
                    query_keywords.append(piece)

    # --- 方法A: 精准词定位 ---
    # 使用低频高特异性词定位，在其周围提取段落
    precise_terms = [
        kw for kw in query_keywords
        if len(kw) >= 3 and best_file.count(kw) <= 50
    ]
    if not precise_terms:
        precise_terms = [
            kw for kw in query_keywords
            if len(kw) >= 2 and best_file.count(kw) <= 100
        ]

    raw_paragraphs = []
    for term in precise_terms[:10]:
        pos = 0
        count = 0
        while pos < len(best_file) and count < 15:
            pos = best_file.find(term, pos)
            if pos < 0:
                break
            # 上下文: 前1000字 + 后3000字
            start = max(0, pos - 1000)
            end = min(len(best_file), pos + 3000)
            para = best_file[start:end]
            if len(para) > 100:
                raw_paragraphs.append(para)
            pos += len(term)
            count += 1

    # --- 方法B: 通用词补充（精准词不足5段时）---
    if len(raw_paragraphs) < 5:
        for term in ['收入', '合计', '分别为', '万元', '占比', '发行', '募集']:
            if term in best_file:
                pos = best_file.find(term)
                if pos >= 0:
                    start = max(0, pos - 500)
                    end = min(len(best_file), pos + 2500)
                    para = best_file[start:end]
                    if len(para) > 100:
                        raw_paragraphs.append(para)
                if len(raw_paragraphs) >= 10:
                    break

    # --- ★ 数据扫荡: 正则匹配"数字+单位"密集段落 ---
    data_pattern = re.compile(
        r'(?:\d{1,3}(?:,\d{3})*\.?\d*\s*[万元亿%个百千万]+\s*[、，,和及与或\s]+){2,}'
        r'\d{1,3}(?:,\d{3})*\.?\d*\s*[万元亿%个百千万]+'
    )
    for m in data_pattern.finditer(best_file):
        pos = m.start()
        start = max(0, pos - 600)
        end = min(len(best_file), pos + 2000)
        dp = best_file[start:end]
        if len(dp) > 100:
            raw_paragraphs.append(dp)
        if len(raw_paragraphs) >= 30:
            break

    # --- 兜底: 无段落命中时取文件前12000字 ---
    if not raw_paragraphs:
        raw_paragraphs = [best_file[:12000]]
        logger.warning("无段落命中，使用文件前12000字")

    # --- 去重 ---
    seen = set()
    paragraphs = []
    for p in raw_paragraphs:
        key = p[200:500]  # 用中间段作为去重指纹
        if key not in seen:
            seen.add(key)
            paragraphs.append(p)

    # --- 相关性评分 ---
    query_kw_set = set(query_keywords)
    # 扩展关键词集（招股书常见术语）
    for term in [
        '军用', '军方', '军品', '国防', '军队',
        '收入', '营收', '营业收入', '主营业务收入',
        '分别为', '万元', '亿元', '发行', '配售', '上市',
        '募集', '股东', '出资', '占比', '报告期', '年度', '披露', '合计'
    ]:
        query_kw_set.add(term)

    def relevance_score(para: str) -> int:
        """段落相关性评分: 关键词命中×10 + 数据点数"""
        hits = sum(1 for kw in query_kw_set if kw in para)
        data_bonus = len(re.findall(r'\d+\.?\d*\s*[万元亿%]', para))
        return hits * 10 + data_bonus

    # --- 强制保留: 原始查询词首次出现位置的段落 ---
    guaranteed_paragraphs = []
    for term in all_words[:5]:
        if len(term) >= 2:
            pos = best_file.find(term)
            if pos >= 0:
                start = max(0, pos - 1000)
                end = min(len(best_file), pos + 3000)
                gp = best_file[start:end]
                if len(gp) > 100:
                    guaranteed_paragraphs.append(gp)

    # 去重保证段落
    seen_g = set()
    guaranteed_unique = []
    for p in guaranteed_paragraphs:
        key = p[200:500]
        if key not in seen_g:
            seen_g.add(key)
            guaranteed_unique.append(p)

    # 排序: 保证段落排最前，其余按相关性降序
    paragraphs.sort(key=relevance_score, reverse=True)
    guaranteed_keys = {p[200:500] for p in guaranteed_unique}
    other_paragraphs = [
        p for p in paragraphs if p[200:500] not in guaranteed_keys
    ]
    final_paragraphs = guaranteed_unique + other_paragraphs
    context = "\n\n---\n\n".join(final_paragraphs[:8])

    logger.info("招股书段落: %d段 (保证%d段, top得分=%s)",
                 len(final_paragraphs[:8]), len(guaranteed_unique),
                 [relevance_score(p) for p in final_paragraphs[:3]])

    # ================================================================
    # 阶段4: RAG 问答（两轮: 标准 + 数据扫荡回退）
    # ================================================================
    sys_prompt = (
        "你是专业的招股说明书分析师。请严格基于提供的文本内容回答问题。\n"
        "规则:\n"
        "1. 只引用文本中有的数据，不要编造\n"
        "2. 保留原始数据的精度和单位\n"
        "3. 如果有多个数据点，请逐项列出\n"
        "4. 如果精确术语未出现，请搜索相关概念（如'配售'→'发行'/'网下配售'等）\n"
        "5. 尽量找到相关信息回答——即使不精确匹配，也要提供最接近的内容\n"
        "6. 确实完全无关时才说'未找到'，并说明搜索了哪些相关词\n"
        "7. 用简洁清晰的中文回复，信息要完整，至少2-3句话"
    )
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": (
            f"## 招股书文本\n\n{context[:12000]}\n\n"
            f"## 问题\n{query}\n\n"
            f"请根据以上文本回答（如果精确术语未出现，请用相关概念搜索）："
        )}
    ]
    answer = call_deepseek(messages, max_tokens=3072)

    # ★ 两轮 RAG: 第一轮未找到时合并数据扫荡重试
    not_found_markers = ['未找到', '未在文本', '没有相关', '未披露', '未发现']
    if answer and any(kw in answer for kw in not_found_markers):
        logger.warning("第一轮 RAG 未找到，启动合并数据扫荡重试...")
        # 合并数据密集段落
        data_paras = [
            p for p in raw_paragraphs
            if re.findall(r'\d+\.?\d*\s*[万元亿%]', p)
        ]
        data_paras.sort(
            key=lambda p: -len(re.findall(r'\d+\.?\d*\s*[万元亿%]', p))
        )
        # 取并集: 保证段落 + 数据段落 + 原始段落
        merged = guaranteed_unique.copy()
        seen_m = {p[200:500] for p in merged}
        for p in data_paras + final_paragraphs:
            key = p[200:500]
            if key not in seen_m:
                seen_m.add(key)
                merged.append(p)
        retry_context = "\n\n---\n\n".join(merged[:12])

        retry_prompt = (
            "你是专业的招股说明书分析师。以下是招股书的完整数据段落"
            "（含原文段落和数字密集段落）。\n"
            "请仔细阅读，找到与问题最相关的数据并完整回答。\n"
            "不要轻易说'未找到'——如果精确术语未出现，请用最接近的内容回答。\n"
            "规则: 1)只引用文本数据 2)保留精度和单位 3)逐项列出 4)信息完整"
        )
        retry_msg = [
            {"role": "system", "content": retry_prompt},
            {"role": "user", "content": (
                f"## 招股书段落\n\n{retry_context[:12000]}\n\n"
                f"## 问题\n{query}\n\n请根据以上文本回答："
            )}
        ]
        retry_answer = call_deepseek(retry_msg, max_tokens=3072)
        if retry_answer and len(retry_answer.strip()) >= 20:
            answer = retry_answer
            logger.info("第二轮 RAG 成功: %s", answer[:80])

    return answer if answer else "生成失败"
