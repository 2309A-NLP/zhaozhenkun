#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
设计 — Research Agent 设计层
==============================================================================
包含: System Prompt 设计、Few-Shot 模板、答案格式定义等
==============================================================================
"""
from .prompts import (  # 导入所有提示词模板
    RESEARCH_AGENT_SYSTEM_PROMPT,  # Agent 系统提示词
    SUMMARIZE_SEARCH_RESULTS_PROMPT,  # 搜索结果压缩提示词
    EXTRACT_FINAL_ANSWER_PROMPT,  # 最终答案提取提示词
    ANALYZE_QUESTION_PROMPT,  # 问题分析提示词
    VALIDATE_FORMAT_PROMPT,  # 答案格式验证提示词
)
