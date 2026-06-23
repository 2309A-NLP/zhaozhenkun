# -*- coding: utf-8 -*-
"""
主入口模块 — 依次调用全部模块，完成跨模态检索优化全流程。

功能说明：
1. 加载配置（config.py）
2. 解析PDF并构建知识库（pdf_parser.py）
3. 加载BGE-M3嵌入模型（embedder.py）
4. 构建向量索引（retriever.py）
5. 执行6个测试问题的查询分析（query_analyzer.py）
6. 执行混合检索和RRF融合（retriever.py）
7. 执行跨模态重排（reranker.py）
8. 调用MiMo API生成答案（qa_generator.py）
9. 评估结果并生成报告（evaluator.py）
"""
import logging
import sys  # 导入sys模块，用于命令行参数
import os  # 导入os模块

logger = logging.getLogger(__name__)
logger.info("run 模块加载")


# ======================== 修复模块搜索路径 ========================
_CUR_DIR = os.path.dirname(os.path.abspath(__file__))              # 研发/
_PROJECT_ROOT = os.path.dirname(_CUR_DIR)                          # 项目根
_TEST_DIR = os.path.join(_PROJECT_ROOT, "测试")                    # 测试/
sys.path.insert(0, _CUR_DIR)   # 研发/（同级模块）
sys.path.insert(0, _TEST_DIR)  # 测试/（evaluator模块）

def print_banner():
    """打印项目启动横幅"""
    print("╔══════════════════════════════════════════════╗")
    print("║    跨模态检索优化系统 (Cross-Modal RAG)       ║")
    print("║     工单15 - 优化技术图纸与文本检索           ║")
    print("╚══════════════════════════════════════════════╝")
    print()

def step_pipeline():
    """
    执行完整流水线：解析→嵌入→检索→问答→评估。

    该函数依次调用项目的所有模块，是项目的核心编排逻辑。
    """
    print_banner()  # 打印横幅

    # ==================== Step 1: 加载配置 ====================
    print("=" * 50)  # 打印分隔线
    print("📋 [Step 1/6] 加载配置...")  # 标记步骤
    import config  # 导入配置模块
    print(f"  PDF文件: {config.PDF_PATH}")  # 打印PDF路径
    print(f"  BGE模型: {config.BGE_M3_PATH}")  # 打印模型路径
    print(f"  MiMo API: {config.MIMO_BASE_URL}")  # 打印API地址
    print(f"  输出目录: {config.OUTPUT_DIR}")  # 打印输出目录
    # 确保输出目录存在
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)

    # ==================== Step 2: 解析PDF ====================
    print("\n" + "=" * 50)  # 打印分隔线
    print("📄 [Step 2/6] 解析PDF文档...")  # 标记步骤
    from pdf_parser import parse_pdf, build_knowledge_base  # 导入PDF解析模块
    pages = parse_pdf(config.PDF_PATH, project_root=str(config.BASE_DIR))  # 解析PDF (OCR+补充)
    knowledge_base = build_knowledge_base(pages, config.OUTPUT_DIR)  # 构建知识库
    print(f"  ✅ 知识库条目数: {len(knowledge_base)}")  # 打印知识库大小

    # ==================== Step 3: 加载BGE模型 ====================
    print("\n" + "=" * 50)  # 打印分隔线
    print("🧠 [Step 3/6] 加载BGE-M3嵌入模型...")  # 标记步骤
    from embedder import load_bge_model  # 导入嵌入模块
    bge_model = load_bge_model(config.BGE_M3_PATH, device="cuda")  # 加载模型
    if bge_model is None:  # 如果加载失败
        print("  ⚠️ GPU加载失败，尝试CPU模式...")  # 提示降级
        bge_model = load_bge_model(config.BGE_M3_PATH, device="cpu")  # CPU降级
    if bge_model is None:  # 如果CPU也失败
        print("  ⚠️ 模型加载失败，将使用随机向量降级模式")  # 提示降级

    # ==================== Step 4: 构建检索索引 ====================
    print("\n" + "=" * 50)  # 打印分隔线
    print("🔍 [Step 4/6] 构建检索索引...")  # 标记步骤
    from retriever import build_vector_index  # 导入检索模块
    kb_texts = build_vector_index(knowledge_base)  # 构建索引
    print(f"  ✅ 索引构建完成，共 {len(kb_texts)} 个文本块")  # 打印索引信息

    # ==================== Step 5: 单问题测试 ====================
    print("\n" + "=" * 50)  # 打印分隔线
    print("🔬 [Step 5/6] 单问题快速测试...")  # 标记步骤
    # 选择第3个问题（图文混合）做快速验证
    test_q = config.TEST_QUESTIONS[2]  # "图3中编号13相对于编号12"
    print(f"  测试问题: {test_q['question'][:50]}...")  # 打印测试问题

    from query_analyzer import analyze_query  # 导入查询分析
    analysis = analyze_query(test_q["question"])  # 分析查询
    print(f"  查询类型: {analysis['query_type']}")  # 打印查询类型
    print(f"  增强查询: {analysis['enhanced_query'][:80]}...")  # 打印增强查询

    # ==================== Step 6: 完整评估 ====================
    print("\n" + "=" * 50)  # 打印分隔线
    print("📊 [Step 6/6] 执行6个问题完整评估...")  # 标记步骤
    from evaluator import run_evaluation  # 导入评估模块

    report = run_evaluation(config, bge_model, knowledge_base)  # 执行评估

    # ==================== 打印最终结果 ====================
    print("\n" + "=" * 60)  # 打印分隔线
    print("🎯 评估完成！最终结果:")  # 打印最终结果
    print(f"  总题数: {report['total_questions']}")  # 打印总题数
    print(f"  正确数: {report['correct_count']}")  # 打印正确数
    print(f"  准确率: {report['accuracy']}%")  # 打印准确率
    print(f"  报告已保存到: {config.OUTPUT_DIR}/eval_report.json")  # 打印报告路径
    print("=" * 60)  # 打印分隔线

    # 返回是否达标（工单要求80%以上）
    passed = report["accuracy"] >= 80  # 判断是否达标
    if passed:  # 如果达标
        print("✅ 达标！准确率 ≥ 80%，满足工单验收标准")  # 打印达标
    else:  # 如果不达标
        print("⚠️ 未达标，准确率 < 80%，建议优化检索策略")  # 打印未达标

    return report  # 返回评估报告

def main():
    """
    主函数：处理命令行参数，启动流水线或帮助信息。
    支持 --web 启动交互式对话（预留），--pipeline 执行完整流程。
    """
    args = sys.argv[1:]  # 获取命令行参数

    if "--help" in args or "-h" in args:  # 如果请求帮助
        print("用法: python run.py [--pipeline|--help]")  # 打印用法
        print("  --pipeline  执行完整评估流水线（默认）")  # 说明pipeline模式
        print("  --help      显示帮助信息")  # 说明帮助
        return

    # 默认执行完整流水线
    print("启动跨模态检索优化评估流水线...\n")  # 打印启动提示
    step_pipeline()  # 执行流水线

if __name__ == "__main__":  # 如果直接运行此脚本
    main()  # 调用主函数
