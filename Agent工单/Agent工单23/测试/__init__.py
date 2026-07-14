#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
测试 — 测试模块入口
==============================================================================
"""
from .generate_answers import (  # 导入答案生成相关函数
    load_questions,  # 加载题目
    load_existing_answers,  # 加载已有答案
    answer_single_question,  # 单题回答
    main,  # 主函数
)
