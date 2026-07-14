#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
研发 — Research Agent 研发层
==============================================================================
包含: LLM 客户端、搜索工具、ReAct Agent 核心、配置管理
==============================================================================
"""
from .config import (  # 导入所有配置项
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,  # LLM 配置
    SERPAPI_API_KEY, SEARCH_NUM_RESULTS,  # 搜索配置
    MAX_AGENT_TURNS, LLM_TEMPERATURE, VERBOSE,  # Agent 参数
    validate_config, print_config,  # 配置函数
)
from .llm_client import DeepSeekClient  # 导入 LLM 客户端
from .search_tools import web_search, web_fetch, format_search_results  # 导入搜索工具
from .agent_core import ResearchAgent  # 导入 Agent 核心
