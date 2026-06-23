# -*- coding: utf-8 -*-
"""
评估模块 — 对6个测试问题进行系统化测试并生成报告。

功能说明：
- 加载6个工单指定的测试问题
- 对每个问题执行完整流程：查询分析→检索→重排→问答
- 记录每个步骤的结果（检索结果、答案、匹配情况）
- 统计整体准确率
- 生成带详细日志的评估报告
"""
import logging
import json  # 导入json模块
from datetime import datetime  # 导入datetime，用于时间戳
from pathlib import Path  # 导入Path类

logger = logging.getLogger(__name__)
logger.info("evaluator 模块加载")


def run_evaluation(config, bge_model, knowledge_base):
    """
    执行6个测试问题的完整评估流程。

    参数:
        config: 配置模块引用
        bge_model: BGE-M3模型实例
        knowledge_base: 知识库列表

    返回:
        评估结果字典（含每题的详情和总体统计）
    """
    # 延迟导入（避免循环依赖）
    from query_analyzer import analyze_query, print_analysis  # 查询分析
    from retriever import retrieve_text, retrieve_image_enhanced, rrf_fusion  # 检索
    from reranker import rerank  # 重排
    from qa_generator import generate_answer, evaluate_answer  # 问答

    print("\n" + "=" * 60)  # 打印分隔线
    print("🧪 开始6个测试问题评估")  # 打印评估标题
    print("=" * 60)

    # 获取配置中的测试问题
    test_questions = config.TEST_QUESTIONS
    # 提取知识库文本
    kb_texts = [item["content"] for item in knowledge_base]

    # 初始化结果记录
    results = []  # 每题的结果
    correct_count = 0  # 正确答案计数

    # 遍历每个测试问题
    for idx, q_item in enumerate(test_questions):
        question = q_item["question"]  # 问题文本
        expected = q_item["answer"]  # 标准答案
        q_type = q_item["type"]  # 问题类型

        print(f"\n{'─' * 50}")  # 打印分隔线
        print(f"📝 问题{idx+1}: {question[:60]}...")  # 打印问题
        print(f"   标准答案: {expected}")  # 打印标准答案
        print(f"   类型: {q_type}")  # 打印问题类型

        # ===== Step 1: 查询分析 =====
        print("\n  [Step 1/4] 查询理解...")  # 标记步骤
        analysis = analyze_query(question)  # 分析查询
        print_analysis(analysis)  # 打印分析结果

        # ===== Step 2: 混合检索 =====
        print("\n  [Step 2/4] 混合检索...")  # 标记步骤
        # 2a: 文本检索（使用原始问题）
        text_results = retrieve_text(
            bge_model, question, kb_texts, knowledge_base,
            top_k=config.RETRIEVE_TOP_K
        )
        print(f"    📝 文本检索完成，Top-1: {text_results[0]['id']}")

        # 2b: 图像增强检索（使用增强查询）
        enhanced_query = analysis["enhanced_query"]  # 获取增强查询
        image_results = retrieve_image_enhanced(
            bge_model, enhanced_query, kb_texts, knowledge_base,
            top_k=config.RETRIEVE_TOP_K
        )
        print(f"    📷 图像增强检索完成，Top-1: {image_results[0]['id']}")

        # 2c: RRF融合
        fused = rrf_fusion(
            text_results, image_results,
            k=config.RRF_K, top_k=config.RETRIEVE_TOP_K
        )
        print(f"    🔗 RRF融合完成，共 {len(fused)} 个结果")

        # ===== Step 3: 跨模态重排 =====
        print("\n  [Step 3/4] 跨模态重排...")  # 标记步骤
        reranked = rerank(q_type, fused, query_analysis=analysis)

        # 打印重排结果
        for item in reranked[:3]:  # 只显示前3个
            fig_mark = "📷" if item.get("has_figure") else "📝"
            print(f"    #{item['final_rank']} {fig_mark} {item['id']} "
                  f"(得分: {item['rerank_score']:.4f})")

        # ===== Step 4: 问答生成 =====
        print("\n  [Step 4/4] 生成答案...")  # 标记步骤
        # 取重排前5个作为上下文
        top_context = reranked[:config.RERANK_TOP_K]
        answer = generate_answer(question, top_context, q_type, config)
        print(f"    🤖 模型回答: {answer[:80]}...")  # 打印回答（截断）

        # 判断是否正确
        is_correct = evaluate_answer(answer, expected)
        if is_correct:  # 如果正确
            correct_count += 1  # 计数+1
            print(f"    ✅ 回答正确！匹配标准答案: {expected}")
        else:  # 如果错误
            print(f"    ❌ 回答不匹配。标准答案: {expected}")

        # 记录本题结果
        results.append({
            "question_num": idx + 1,  # 题号
            "question": question,  # 问题
            "type": q_type,  # 类型
            "expected_answer": expected,  # 标准答案
            "predicted_answer": answer,  # 模型回答
            "is_correct": is_correct,  # 是否正确
            "top_retrieved": [  # 检索到的Top结果
                {"id": r["id"], "page": r["page_num"],
                 "has_figure": r["has_figure"],
                 "score": round(r["rerank_score"], 4)}
                for r in reranked[:5]
            ],
        })

    # ===== 汇总统计 =====
    total = len(test_questions)  # 总题数
    accuracy = correct_count / total * 100  # 准确率百分比

    print(f"\n{'=' * 60}")  # 打印分隔线
    print(f"📊 评估结果汇总")  # 打印汇总标题
    print(f"  总题数: {total}")  # 打印总题数
    print(f"  正确: {correct_count}")  # 打印正确数
    print(f"  准确率: {accuracy:.1f}%")  # 打印准确率

    # ===== 保存报告 =====
    report = {  # 构建报告
        "test_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # 测试时间
        "total_questions": total,  # 总题数
        "correct_count": correct_count,  # 正确数
        "accuracy": round(accuracy, 1),  # 准确率
        "details": results,  # 每题详情
    }

    # 写入JSON文件
    report_path = Path(config.OUTPUT_DIR) / "eval_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n  📄 评估报告已保存: {report_path}")  # 打印保存提示
    return report  # 返回报告
