#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
测试 — 批量答案生成与评测脚本
==============================================================================
功能: 读取 question.jsonl 中的 100 道题目，使用 Research Agent 逐题回答，
      生成符合竞赛要求的 answer.jsonl 答案文件。
      支持: 断点续传、进度跟踪、答案归一化。
用法: python generate_answers.py [--start 0] [--end 100] [--no-resume]
==============================================================================
"""
import json  # JSON 读写
import os  # 文件路径操作
import sys  # 系统接口
import time  # 时间统计
import argparse  # 命令行参数解析
from datetime import datetime  # 日期时间
from typing import List, Dict, Set  # 类型注解

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 项目根目录

from 研发.agent_core import ResearchAgent  # 导入 Research Agent
from 研发.config import print_config, validate_config  # 导入配置函数
from 优化.answer_normalizer import normalize_answer, assess_answer_quality  # 导入答案优化


# ============================================================
# 一、常量定义
# ============================================================
# 项目根目录
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目根目录
# 默认输入文件（题目）
QUESTION_FILE = os.path.join(ROOT_DIR, "23附件", "question.jsonl")  # 题目文件路径
# 默认输出文件（答案）
OUTPUT_FILE = os.path.join(ROOT_DIR, "answer.jsonl")  # 答案输出路径
# 进度文件（断点续传用）
PROGRESS_FILE = os.path.join(ROOT_DIR, "progress.json")  # 进度文件路径


# ============================================================
# 二、文件读写工具
# ============================================================

def load_questions(filepath: str) -> List[Dict]:  # 加载 JSONL 题目文件
    """从 JSONL/TSV 文件加载所有题目，返回 [{"id":0, "question":"..."}] 列表。"""
    questions = []  # 题目列表
    if not os.path.exists(filepath):  # 文件不存在
        alt = os.path.join(ROOT_DIR, "23附件", "question.jsonl")  # 备用路径
        filepath = alt if os.path.exists(alt) else filepath  # 使用备用路径
        if not os.path.exists(filepath):  # 仍未找到
            print(f"错误: 题目文件不存在: {filepath}")  # 报错
            return questions  # 返回空列表

    with open(filepath, "r", encoding="utf-8") as f:  # 打开文件
        for line in f:  # 逐行读取
            line = line.strip()  # 去除首尾空白
            if not line:  # 空行跳过
                continue
            try:  # 尝试直接解析 JSON
                questions.append(json.loads(line))  # 直接解析并添加
            except json.JSONDecodeError:  # JSON 解析失败，尝试 TSV 格式
                parts = line.split("\t", 1)  # 按 tab 分割
                if len(parts) == 2:  # TSV 格式: id\t{json}
                    try:
                        questions.append(json.loads(parts[1]))  # 解析第二部分
                    except json.JSONDecodeError:  # 解析失败
                        print(f"警告: 跳过无效行: {line[:50]}...")  # 打印警告
    return questions  # 返回题目列表


def load_answers(filepath: str) -> Dict[int, Dict]:  # 加载已有答案文件
    """从 answer.jsonl 加载已有答案，返回 {id: answer_obj} 字典（用于断点续传）。"""
    answers = {}  # 答案字典
    if not os.path.exists(filepath):  # 文件不存在
        return answers  # 返回空字典
    with open(filepath, "r", encoding="utf-8") as f:  # 打开文件
        for line in f:  # 逐行读取
            line = line.strip()  # 去除空白
            if not line:  # 空行跳过
                continue
            try:
                obj = json.loads(line)  # 解析 JSON
                if "id" in obj:  # 有 id 字段
                    answers[obj["id"]] = obj  # 存入字典
            except json.JSONDecodeError:  # 解析失败跳过
                pass
    return answers  # 返回答案字典


def load_progress(filepath: str) -> Set[int]:  # 加载已完成题目 ID 集合
    """从进度文件加载已完成题目 ID，用于断点续传。"""
    if not os.path.exists(filepath):  # 文件不存在
        return set()  # 返回空集合
    try:
        with open(filepath, "r", encoding="utf-8") as f:  # 打开文件
            data = json.load(f)  # 解析 JSON
            return set(data.get("completed_ids", []))  # 返回 ID 集合
    except (json.JSONDecodeError, KeyError):  # 解析失败
        return set()  # 返回空集合


def save_progress(completed_ids: Set[int], filepath: str) -> None:  # 保存进度
    """保存已完成题目 ID 到进度文件。"""
    with open(filepath, "w", encoding="utf-8") as f:  # 打开文件
        json.dump({  # 写入 JSON
            "completed_ids": list(completed_ids),  # ID 列表
            "count": len(completed_ids),  # 完成计数
            "last_update": datetime.now().isoformat(),  # 更新时间戳
        }, f, ensure_ascii=False, indent=2)  # 格式化输出


def save_answers_jsonl(answers: Dict[int, Dict], output_path: str) -> None:  # 保存答案
    """按 id 排序后将答案写入 answer.jsonl（竞赛格式: 每行 {"id": N, "answer": "..."}）。"""
    sorted_answers = sorted(answers.values(), key=lambda x: x["id"])  # 按 ID 排序
    with open(output_path, "w", encoding="utf-8") as f:  # 打开文件
        for obj in sorted_answers:  # 遍历答案
            f.write(json.dumps({  # 写入竞赛格式（仅保留 id 和 answer）
                "id": obj["id"],  # 题目 ID
                "answer": obj.get("answer", ""),  # 答案文本
            }, ensure_ascii=False) + "\n")  # 末尾换行


# ============================================================
# 三、单题回答
# ============================================================

def answer_single_question(  # 回答单道题目
    agent: ResearchAgent,  # Agent 实例
    q_obj: Dict,  # 题目对象 {"id": 0, "question": "..."}
    idx: int,  # 当前题目序号
    total: int,  # 总题目数
) -> Dict:  # 返回 {"id": 0, "answer": "...", "turns": N, ...}
    """使用 Agent 回答一道题目，包含错误处理、归一化和质量评估。"""
    qid = q_obj.get("id", idx)  # 题目 ID
    question = q_obj.get("question", "")  # 问题文本

    print(f"\n{'=' * 60}")  # 分隔线
    print(f"[{idx + 1}/{total}] ID={qid}")  # 进度信息
    print(f"问题: {question[:120]}...")  # 问题摘要

    t0 = time.time()  # 记录开始时间
    try:  # 执行 Agent 研究
        result = agent.research(question)  # 调用 Agent
        raw_answer = result.get("answer", "")  # 获取原始答案
        turns = result.get("total_turns", 0)  # 获取推理轮数
    except Exception as e:  # Agent 执行异常
        print(f"  [错误] {e}")  # 打印错误
        raw_answer, turns = "", 0  # 空结果

    # 归一化和质量评估
    normalized = normalize_answer(raw_answer, question)  # 答案归一化
    quality = assess_answer_quality(normalized, turns)  # 质量评估
    elapsed = time.time() - t0  # 计算耗时

    # 打印结果摘要
    print(f"  答案: {normalized[:100]}")  # 答案内容
    print(f"  轮数: {turns}, 耗时: {elapsed:.1f}s")  # 统计信息
    if quality.get("warnings"):  # 有质量警告
        print(f"  警告: {quality['warnings']}")  # 打印警告

    return {  # 返回完整答案记录
        "id": qid, "answer": normalized,  # 基本答案信息
        "raw_answer": raw_answer, "turns": turns,  # 原始和轮数
        "elapsed_seconds": round(elapsed, 1),  # 耗时记录
        "quality_warnings": quality.get("warnings", []),  # 质量警告
    }


# ============================================================
# 四、主流程
# ============================================================

def main():  # 批量答案生成主函数
    """解析参数、加载题目、逐题回答、保存答案的主入口。"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="Research Agent 批量答案生成器")  # 参数解析器
    parser.add_argument("--start", type=int, default=0, help="起始题目索引")  # 起始索引
    parser.add_argument("--end", type=int, default=100, help="结束题目索引（不含）")  # 结束索引
    parser.add_argument("--input", type=str, default=None, help="题目文件路径")  # 自定义输入
    parser.add_argument("--output", type=str, default=None, help="答案输出路径")  # 自定义输出
    parser.add_argument("--resume", action="store_true", default=True, help="断点续传")  # 启用续传
    parser.add_argument("--no-resume", action="store_false", dest="resume")  # 禁用续传
    args = parser.parse_args()  # 解析命令行

    # 确定文件路径
    qfile = args.input or QUESTION_FILE  # 题目文件
    outfile = args.output or OUTPUT_FILE  # 输出文件

    # 打印配置信息
    print("=" * 60)  # 分隔线
    print("  Research Agent — 批量答案生成器")  # 标题
    print("=" * 60)  # 分隔线
    print_config()  # 打印 Agent 配置
    validate_config()  # 验证配置有效性

    # 加载题目
    print(f"\n加载题目文件: {qfile}")  # 打印文件路径
    questions = load_questions(qfile)  # 加载题目
    if not questions:  # 未加载到题目
        print("错误: 未加载到任何题目，请检查文件路径和格式。")  # 错误提示
        sys.exit(1)  # 退出程序
    print(f"成功加载 {len(questions)} 道题目")  # 打印题目数

    # 应用 start/end 范围过滤
    questions = questions[args.start:args.end]  # 切片过滤
    total = len(questions)  # 实际处理数
    print(f"本次处理范围: [{args.start}, {args.end}) 共 {total} 题")  # 打印范围

    # 断点续传：加载已完成题目
    completed_ids = set()  # 已完成 ID 集合
    if args.resume:  # 启用断点续传
        completed_ids = load_progress(PROGRESS_FILE)  # 加载进度
        existing = load_answers(outfile)  # 加载已有答案
        completed_ids.update(existing.keys())  # 合并已有答案 ID
        if completed_ids:  # 有已完成题目
            print(f"断点续传: 已完成 {len(completed_ids)} 题，将跳过")  # 提示

    # 创建 Agent 实例
    print("\n初始化 Research Agent...")  # 初始化提示
    agent = ResearchAgent(verbose=True)  # 创建 Agent（详细日志）

    # 过滤未完成题目
    remaining = [q for q in questions if q.get("id") not in completed_ids]  # 未完成列表
    skipped = total - len(remaining)  # 跳过数量
    print(f"跳过已完成: {skipped} 题, 待处理: {len(remaining)} 题\n")  # 统计

    # 批量处理
    all_answers = load_answers(outfile)  # 加载已有答案为起点
    t_start = time.time()  # 总计时开始

    for i, q in enumerate(remaining):  # 遍历未完成题目
        ans = answer_single_question(agent, q, i + skipped, total)  # 回答单题
        all_answers[ans["id"]] = ans  # 更新答案字典
        completed_ids.add(ans["id"])  # 更新已完成集合

        # 每 5 题（或最后一题）保存一次
        if (i + 1) % 5 == 0 or i == len(remaining) - 1:  # 保存时机
            save_answers_jsonl(all_answers, outfile)  # 写入答案文件
            save_progress(completed_ids, PROGRESS_FILE)  # 写入进度文件
            elapsed = time.time() - t_start  # 已用时间
            pct = (i + 1 + skipped) / total * 100  # 进度百分比
            print(f"\n--- 进度: {i + 1 + skipped}/{total} ({pct:.1f}%), "
                  f"总耗时: {elapsed:.1f}s ---")  # 打印进度

    # 最终统计
    total_elapsed = time.time() - t_start  # 总耗时
    new_count = len(remaining)  # 本次处理数
    print("\n" + "=" * 60)  # 分隔线
    print("  批量生成完成!")  # 完成提示
    print("=" * 60)  # 分隔线
    print(f"  总题目: {total}  |  本次回答: {new_count}  |  累计: {len(all_answers)}")  # 统计
    print(f"  总耗时: {total_elapsed:.1f}s ({total_elapsed/60:.1f}min)")  # 时间
    if new_count > 0:  # 有处理题目
        avg_t = total_elapsed / new_count  # 平均耗时
        avg_turns = sum(a.get("turns", 0) for a in all_answers.values()) / max(len(all_answers), 1)  # 平均轮数
        print(f"  平均每题: {avg_t:.1f}s  |  平均轮数: {avg_turns:.1f}")  # 平均统计
    print(f"  输出文件: {outfile}")  # 输出路径
    print("=" * 60)  # 分隔线


# ============================================================
# 五、入口
# ============================================================
if __name__ == "__main__":  # 脚本直接运行入口
    main()  # 执行主函数
