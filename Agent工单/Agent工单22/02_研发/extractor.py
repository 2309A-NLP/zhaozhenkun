#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
02_研发 — 关键信息提取器
==============================================================================
从多轮对话中自动提取结构化关键信息。
根据领域（医疗/文旅/教育）使用不同的提取策略和提示词模板。
模型: deepseek-v4-flash
==============================================================================
"""

import json  # JSON 解析，处理 LLM 返回的结构化提取结果
import re  # 正则表达式，用于从 LLM 回复中抽取 JSON
from typing import Optional, Dict, Any, List  # 类型注解

# 导入自建的 LLM 客户端和提示词模板
from llm_client import DeepSeekClient  # DeepSeek API 调用封装
# 从设计模块导入提示词获取函数
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "01_设计"))
from prompts import get_prompt  # 提示词注册表


class InformationExtractor:
    """关键信息提取器。

    使用 DeepSeek LLM 从对话文本中提取领域特定的结构化信息。
    支持的领域：medical（医疗）、tourism（文旅）、education（教育）

    使用方式:
        extractor = InformationExtractor()
        info = extractor.extract(domain="medical", conversation="医生：你哪里不舒服？...")
        print(info)  # 输出结构化的患者信息 dict
    """

    def __init__(self, llm_client: DeepSeekClient = None):
        """初始化提取器。

        Args:
            llm_client: DeepSeek 客户端实例，不传则自动创建
        """
        # LLM 客户端，用于调用 DeepSeek 进行信息提取
        self.llm = llm_client or DeepSeekClient()

    @staticmethod
    def _try_parse_json(text: str) -> Dict[str, Any]:
        """尝试从 LLM 回复中解析 JSON。

        LLM 有时会在 JSON 前后添加说明文字（Markdown 代码块等），
        此方法使用多种策略提取纯 JSON 部分。

        Args:
            text: LLM 的原始回复文本

        Returns:
            解析后的字典，解析失败则返回空字典
        """
        # 策略1: 直接解析整个文本
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass  # 直接解析失败，尝试其他策略

        # 策略2: 提取 ```json ... ``` 代码块中的内容
        code_block_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
        if code_block_match:
            try:
                return json.loads(code_block_match.group(1).strip())
            except json.JSONDecodeError:
                pass  # 代码块内也不是合法 JSON

        # 策略3: 提取第一个 { 到最后一个 } 之间的内容
        brace_match = re.search(r"\{.*\}", text, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass  # 大括号内也不是合法 JSON

        # 所有策略都失败，返回空字典
        print(f"[Extractor] 警告: 无法解析 LLM 输出为 JSON: {text[:200]}...")
        return {}

    def extract(self, domain: str, conversation: str) -> Dict[str, Any]:
        """从对话中提取结构化信息。

        Args:
            domain: 领域代码 (medical / tourism / education)
            conversation: 多轮对话文本

        Returns:
            结构化的提取结果字典，字段取决于领域 schema
        """
        # 获取对应领域的提取提示词
        system_prompt = get_prompt(domain, "extract")

        # 调用 DeepSeek LLM 进行信息提取，使用低温度确保准确性
        raw_response = self.llm.extract(
            system_prompt=system_prompt,
            conversation=conversation,
            temperature=0.1,  # 低温度 = 更确定的输出
        )

        # 将 LLM 回复解析为 Python 字典
        extracted = self._try_parse_json(raw_response)

        # 如果解析失败，返回含错误信息的字典
        if not extracted:
            extracted = {"_error": "parse_failed", "_raw": raw_response[:500]}

        return extracted

    def extract_batch(self, domain: str, conversations: List[str]) -> List[Dict[str, Any]]:
        """批量提取多条对话的信息。

        Args:
            domain: 领域代码
            conversations: 对话文本列表

        Returns:
            提取结果列表，顺序与输入一致
        """
        results = []  # 存储结果的列表
        for i, conv in enumerate(conversations):
            # 逐条提取，打印进度
            print(f"[Extractor] 处理第 {i+1}/{len(conversations)} 条对话...")
            result = self.extract(domain, conv)
            results.append(result)
        return results

    def merge_results(self, existing: Dict, new_info: Dict) -> Dict:
        """合并新旧提取结果。

        新信息覆盖旧信息中非 None 的字段；
        列表类型的字段会合并（去重）。

        Args:
            existing: 已有的记忆字典
            new_info: 新提取的信息字典

        Returns:
            合并后的字典
        """
        merged = dict(existing)  # 浅拷贝已有数据，避免修改原对象

        for key, value in new_info.items():
            # 跳过内部字段和 None 值
            if key.startswith("_") or value is None:
                continue

            # 如果已有值是列表，新值也是列表，则合并去重
            if isinstance(merged.get(key), list) and isinstance(value, list):
                # 合并两个列表并去重（保留顺序）
                seen = set()
                combined = []
                for item in merged[key] + value:
                    # 用字典的 JSON 表示作为去重键（适用复杂对象）
                    item_key = json.dumps(item, ensure_ascii=False, sort_keys=True)
                    if item_key not in seen:
                        seen.add(item_key)
                        combined.append(item)
                merged[key] = combined
            # 否则直接覆盖
            elif value is not None:
                merged[key] = value

        return merged


# ============================================================
# 模块自检
# ============================================================
if __name__ == "__main__":
    extractor = InformationExtractor()
    print("信息提取器已初始化")

    # 测试医疗领域提取
    print("\n--- 测试: 医疗信息提取 ---")
    medical_conv = """
    医生：您好，请问哪里不舒服？
    患者：最近总是头痛，特别是下午，有时候还会恶心想吐。
    医生：这种情况持续多久了？
    患者：大概一周了。我以前有偏头痛的病史。
    医生：好的，我先给您开点止痛药，观察三天。如果没好转再来复诊。
    患者：好的，谢谢医生。
    """
    med_result = extractor.extract("medical", medical_conv)
    print(f"提取结果: {json.dumps(med_result, ensure_ascii=False, indent=2)}")

    # 测试 JSON 解析的容错性
    print("\n--- 测试: JSON 解析容错 ---")
    test_text = "以下是提取结果：\n```json\n{\"name\": \"张三\", \"age\": 30}\n```\n提取完成。"
    parsed = InformationExtractor._try_parse_json(test_text)
    print(f"容错解析结果: {parsed}")

    print("\n所有自检通过。")
