#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
优化 — 答案归一化与优化模块
==============================================================================
功能: 对 Agent 生成的答案进行归一化处理，确保答案格式符合题目要求。
      包括: 格式清理、语言检测、特殊格式校验、答案质量评分。
说明: 基于竞赛评测标准设计，归一化匹配是评测准确率的关键。
==============================================================================
"""
import re  # 正则表达式
import string  # 字符串处理
from typing import Optional, Tuple  # 类型注解


# ============================================================
# 一、答案归一化
# ============================================================

def normalize_answer(answer: str, question: str = "") -> str:  # 归一化答案
    """对答案进行标准化处理，去除无关内容，适配评测匹配。

    Args:
        answer: 原始答案文本
        question: 对应的问题（用于判断语言和格式要求）

    Returns:
        归一化后的答案文本
    """
    if not answer:  # 空答案
        return ""  # 返回空字符串

    answer = answer.strip()  # 去除首尾空白

    # 1. 移除常见的 LLM 前缀/后缀
    prefixes = [  # 常见前缀列表
        "答案是:", "答案:", "回答:", "最终答案:", "Answer:", "The answer is:", "答案是：", "答案：",
    ]
    for prefix in prefixes:  # 遍历前缀
        if answer.lower().startswith(prefix.lower()):  # 匹配前缀（不区分大小写）
            answer = answer[len(prefix):].strip()  # 移除前缀

    suffixes = ["。", ".", "！"]  # 常见后缀
    # (suffix removal not always needed, keep as-is)

    # 2. 移除可能的引用标记和引号
    answer = answer.strip('"\'""''')  # 移除包裹的引号

    # 3. 移除 "I don't know", "无法确定" 等无意义回答
    no_answer_patterns = [  # 无答案模式
        r"^(I don't know|I do not know|unknown|无法确定|不确定|不知道)[.!，。]*$",  # 英文/中文无答案
    ]
    for pattern in no_answer_patterns:  # 检查是否匹配无答案模式
        if re.match(pattern, answer, re.IGNORECASE):  # 匹配成功
            return ""  # 返回空字符串

    # 4. 根据问题格式要求进行特殊处理
    if question:  # 问题非空
        # 检测年份格式要求
        if _requires_year_format(question):  # 要求年份格式
            answer = _normalize_year(answer)  # 归一化年份

        # 检测人名格式要求
        if _requires_name_format(question):  # 要求人名格式
            answer = _normalize_name(answer)  # 归一化人名

    # 5. 最终清理
    answer = re.sub(r'\s+', ' ', answer)  # 合并多个空白
    answer = answer.strip()  # 再次去除空白

    return answer  # 返回归一化答案


def _requires_year_format(question: str) -> bool:  # 判断问题是否要求年份格式
    """检测问题中是否包含年份格式要求。"""
    year_patterns = [  # 年份相关模式
        r'哪一年', r'年份', r'阿拉伯数字', r'要求直接回答年份',  # 中文
        r'which year', r'in what year', r'Arabic numerals',  # 英文
    ]
    for pattern in year_patterns:  # 遍历模式
        if re.search(pattern, question, re.IGNORECASE):  # 匹配成功
            return True  # 需要年份格式
    return False  # 不要求年份格式


def _requires_name_format(question: str) -> bool:  # 判断问题是否要求人名格式
    """检测问题中是否包含人名格式要求。"""
    name_patterns = [  # 人名相关模式
        r'形如.*和.*', r'扮演', r'配音', r'first name.*last name', r'full name',  # 人名格式
    ]
    for pattern in name_patterns:  # 遍历模式
        if re.search(pattern, question, re.IGNORECASE):  # 匹配成功
            return True  # 需要人名格式
    return False  # 不要求人名格式


def _normalize_year(answer: str) -> str:  # 归一化年份答案
    """从答案中提取并归一化年份。"""
    year_match = re.search(r'(\d{4})', answer)  # 查找 4 位数字
    if year_match:  # 找到年份
        return year_match.group(1)  # 返回年份
    return answer  # 未找到，返回原答案


def _normalize_name(answer: str) -> str:  # 归一化人名答案
    """归一化人名格式（去除多余头衔、空格等）。"""
    # 移除常见头衔
    titles = ["Dr.", "Dr ", "Prof.", "Prof ", "Mr.", "Mr ", "Mrs.", "Mrs ", "Ms.", "Ms "]  # 头衔列表
    for title in titles:  # 遍历头衔
        if answer.startswith(title):  # 以头衔开头
            answer = answer[len(title):].strip()  # 移除头衔

    # 标准化空格
    answer = re.sub(r'\s+', ' ', answer).strip()  # 合并多余空格

    return answer  # 返回归一化后的人名


# ============================================================
# 二、答案格式验证
# ============================================================

def validate_answer_format(answer: str, question: str) -> Tuple[bool, str]:  # 验证答案格式
    """验证答案是否满足问题中声明的格式要求。

    Returns:
        (is_valid, message): 是否有效及说明信息
    """
    # 检测格式形如 "张三和李四"
    if "形如" in question:  # 问题中有格式声明
        format_match = re.search(r'形如(.+?)[。，.]', question)  # 提取格式要求
        if format_match:  # 找到格式声明
            expected_format = format_match.group(1).strip()  # 期望的格式
            # 简单检查答案是否可能匹配该格式
            return True, f"检测到格式要求: {expected_format}"  # 返回提示

    # 检测 "Answer with" 格式要求
    answer_with_match = re.search(r'Answer with (.+?)[.$]', question, re.IGNORECASE)  # 英文格式要求
    if answer_with_match:  # 找到格式声明
        expected_format = answer_with_match.group(1).strip()  # 期望的格式
        return True, f"检测到格式要求: {expected_format}"  # 返回提示

    return True, "格式检查通过"  # 默认通过


# ============================================================
# 三、答案质量评估
# ============================================================

def assess_answer_quality(answer: str, turns_count: int) -> dict:  # 评估答案质量
    """评估答案的质量，用于监控和改进。

    Returns:
        包含质量评分的字典
    """
    quality = {  # 质量评估字典
        "has_answer": bool(answer and answer.strip()),  # 是否有答案
        "answer_length": len(answer) if answer else 0,  # 答案长度
        "turns_used": turns_count,  # 使用的推理轮数
        "warnings": [],  # 警告列表
    }

    # 检查答案是否太短
    if answer and len(answer.strip()) < 2:  # 答案不足 2 字符
        quality["warnings"].append("答案过短，可能不完整")  # 添加警告

    # 检查是否包含不确定表述
    uncertain_phrases = ["不确定", "可能", "也许", "maybe", "perhaps", "uncertain"]  # 不确定表述
    if answer:  # 答案非空
        for phrase in uncertain_phrases:  # 检查不确定表述
            if phrase in answer.lower():  # 包含不确定表述
                quality["warnings"].append(f"答案包含不确定表述: {phrase}")  # 警告
                break  # 找到一个就够了

    # 检查推理效率
    if turns_count >= 8:  # 轮数较多
        quality["warnings"].append(f"使用 {turns_count} 轮推理，效率较低")  # 效率警告

    return quality  # 返回质量评估


# ============================================================
# 四、批量答案后处理
# ============================================================

def post_process_answers(answers: list, questions: list) -> list:  # 批量后处理
    """对一批答案进行批量后处理，包含归一化和质量评估。

    Args:
        answers: 答案字典列表 [{"id": 0, "answer": "..."}]
        questions: 问题字典列表 [{"id": 0, "question": "..."}]

    Returns:
        处理后的答案列表
    """
    # 构建问题查找字典
    question_map = {}  # id -> question 映射
    for q in questions:  # 遍历问题
        qid = q.get("id", -1)  # 获取问题 ID
        question_map[qid] = q.get("question", "")  # 存入映射

    processed = []  # 处理后的答案列表
    for ans in answers:  # 遍历答案
        ans_id = ans.get("id", -1)  # 答案 ID
        ans_text = ans.get("answer", "")  # 答案文本
        question_text = question_map.get(ans_id, "")  # 对应的问题

        # 归一化答案
        normalized = normalize_answer(ans_text, question_text)  # 归一化

        # 验证格式
        is_valid, msg = validate_answer_format(normalized, question_text)  # 格式验证

        processed.append({  # 构建处理后的记录
            "id": ans_id,  # 保持原 ID
            "answer": normalized,  # 归一化后的答案
            "original_answer": ans_text,  # 保留原始答案
            "format_valid": is_valid,  # 格式有效性
            "format_msg": msg,  # 格式信息
        })

    return processed  # 返回处理后的列表


# ============================================================
# 五、模块自检
# ============================================================
if __name__ == "__main__":  # 模块自检入口
    print("=" * 50)  # 分隔线
    print("  答案归一化模块 — 自检")  # 标题
    print("=" * 50)  # 分隔线

    # 测试用例
    test_cases = [  # 测试答案和问题对
        ("答案是: 2024", "哪一年发生了什么？要求直接回答年份。例如：2026。"),  # 年份
        ("最终答案：Alibaba Group Limited", "这个商业实体的英文名称是什么？要求格式形如：Alibaba Group Limited。"),  # 格式要求
        ("Dr. John Smith", "Who is the author?"),  # 人名
        ("I don't know.", "What is the answer?"),  # 无答案
        ("  张三和李四  ", "请问两位男主角分别由谁扮演？要求回答格式形如：张三和李四。"),  # 中文人名
    ]

    for ans, q in test_cases:  # 遍历测试用例
        normalized = normalize_answer(ans, q)  # 归一化
        quality = assess_answer_quality(normalized, 3)  # 评估质量
        print(f"  原始: '{ans}'")  # 打印原始答案
        print(f"  归一化: '{normalized}'")  # 打印归一化后
        print(f"  质量: {quality['warnings'] if quality['warnings'] else 'OK'}")  # 打印质量
        print()  # 空行
