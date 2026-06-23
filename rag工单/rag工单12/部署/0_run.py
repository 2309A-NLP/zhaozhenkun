"""
LightRAG 金融文档智能问答系统 — 最终入口
调用方式：默认启动 Web 对话，传 --pipeline 运行评估流水线
这是项目的最终调用入口（0_run.py）
"""
import logging

logger = logging.getLogger(__name__)
import sys, os
# 将项目根目录加入路径，支持从任意子目录导入其他模块
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _sub in ["设计", "研发", "测试", "部署", "优化"]:
    _p = os.path.join(_root, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import sys        # 系统参数
import argparse   # 命令行参数解析


def main():
    """
    主分发函数：解析命令行参数，分发到 Web 对话或评估流水线
    用法：
        python 0_run.py                → 启动 Web 对话（默认）
        python 0_run.py --pipeline     → 运行全流程评估
        python 0_run.py --pipeline --test    → 测试模式（仅2题）
        python 0_run.py --pipeline --rebuild → 强制重建缓存
        python 0_run.py --port 8080    → 指定 Web 端口
    """
    # 定义命令行参数
    parser = argparse.ArgumentParser(
        description="LightRAG 金融文档智能问答系统 — 招股说明书知识图谱问答"
    )
    parser.add_argument(
        "--pipeline", action="store_true",
        help="运行评估流水线（解析→分块→编码→实体提取→构图→检索→问答→评估）"
    )
    parser.add_argument(
        "--test", action="store_true",
        help="流水线测试模式（仅前2题，需配合 --pipeline 使用）"
    )
    parser.add_argument(
        "--rebuild", action="store_true",
        help="强制重建缓存（需配合 --pipeline 使用）"
    )
    parser.add_argument(
        "--port", type=int, default=5000,
        help="Web 服务端口（默认 5000）"
    )

    args, _ = parser.parse_known_args()  # 解析已知参数，忽略未知参数

    if args.pipeline:
        # ======== 评估流水线模式 ========
        from run import main as pipeline_main  # 导入 run.py 的 main 函数

        print("=" * 50)
        print("📊 LightRAG 评估流水线")
        print(f"   模式: {'🧪 测试(2题)' if args.test else '📋 全量(16题)'}")
        print(f"   缓存: {'🔄 强制重建' if args.rebuild else '💾 使用缓存'}")
        print("=" * 50)

        # 调用全流程流水线
        result = pipeline_main(
            test_mode=args.test,
            rebuild=args.rebuild
        )

        # 打印流水线结果摘要
        print("\n" + "=" * 60)
        if result.get("success"):
            print(f"✅ 评估完成!")
            print(f"   RAG 综合得分:      {result['rag_overall']}/5")
            print(f"   LightRAG 综合得分: {result['lightrag_overall']}/5")
            print(f"   LightRAG 提升:     {result['improvement']:+.2f}")
            print(f"   评估报告: {result['eval_report']}")
            print(f"   图谱可视化: {result['graph_viz']}")
            print(f"   实体数: {result['entities']} | 关系数: {result['relations']}")
            print(f"   图谱节点: {result['graph_nodes']} | 图谱边: {result['graph_edges']}")
        print("=" * 60)

    else:
        # ======== Web 对话模式（默认） ========
        from web_app import run_server  # 导入 Web 模块



        print("=" * 50)
        print("📄 LightRAG 金融文档智能问答系统")
        print("=" * 50)
        print("  招股说明书知识图谱 · RAG / LightRAG 双模式")
        print("  🌐 默认启动 Web 对话界面")
        print(f"  🚀 浏览器访问: http://localhost:{args.port}")
        print("  📋 传 --pipeline 运行评估流水线")
        print("  📋 传 --pipeline --test 快速测试(2题)")
        print("=" * 50)
        run_server(port=args.port)  # 启动 Flask Web 服务


if __name__ == "__main__":
    """项目最终入口：python 0_run.py"""
    main()
