#!/usr/bin/env python3
"""
run.py - 医疗健康咨询 Agent 主入口
功能: 提供三种运行模式:
      1. build — 构建知识图谱（导入 medical.json → Neo4j）
      2. serve — 启动 FastAPI 服务
      3. test  — 运行验收测试（10+30 用例）
用法:
      python run.py build          # 构建知识图谱
      python run.py serve          # 启动 API 服务
      python run.py test           # 运行测试
工单编号: 人工智能NLP-Agent数字人项目-医疗智能体-健康咨询
"""
import sys  # 系统参数
import os  # 路径操作
import logging  # 日志

# 将 dev 目录加入 Python 路径（src/ 在 dev/src/ 下）
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _PROJECT_ROOT)
# 项目根目录（Agent工单12/），用于定位 test/、medical.json 等
_PROJECT_PARENT = os.path.dirname(_PROJECT_ROOT)
sys.path.insert(0, _PROJECT_PARENT)

from src.config import load_config  # 配置加载


def setup_logging():
    """初始化日志系统。"""
    logging.basicConfig(
        level=logging.INFO,  # 日志级别
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",  # 格式
        datefmt="%Y-%m-%d %H:%M:%S",  # 时间格式
    )


def cmd_build(config):
    """
    构建知识图谱命令。

    解析 medical.json → 创建 Neo4j 节点/关系 → 建立索引。

    参数:
        config: AppConfig 实例
    """
    from src.kg_importer import MedicalGraphBuilder  # 图谱构建器
    logger = logging.getLogger("build")
    logger.info("=" * 50)
    logger.info("  医疗知识图谱构建")
    logger.info("=" * 50)
    # 创建构建器并导入数据
    builder = MedicalGraphBuilder(config)
    count = builder.build_from_file(config.kg.data_file, clear_first=True)
    builder.close()
    logger.info(f"构建完成: {count} 种疾病已导入知识图谱")


def cmd_serve(config):
    """
    启动 API 服务命令。

    启动 FastAPI + uvicorn，监听 0.0.0.0:8003。

    参数:
        config: AppConfig 实例
    """
    from src.api import start_server  # API 启动函数
    start_server(config)


def cmd_test(config):
    """
    运行验收测试命令。

    执行 10 个核心用例 + 30+ 变体场景的自动化测试。
    输出每个用例的 Agent 推理过程和结果。

    参数:
        config: AppConfig 实例
    """
    from test.test_queries import run_all_tests  # 测试入口（test/在项目根目录）
    success = run_all_tests(config)  # 运行全部测试
    sys.exit(0 if success else 1)  # 测试失败返回非0


def main():
    """主函数: 解析命令行参数并分发到对应命令。"""
    import argparse

    # 命令行参数解析
    parser = argparse.ArgumentParser(
        description="医疗健康咨询 Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
命令说明:
  build   从 medical.json 构建 Neo4j 知识图谱
  serve   启动 HTTP API 服务 (端口 8003)
  test    运行验收测试 (10个核心用例 + 30+ 变体)
        """,
    )
    # 子命令
    parser.add_argument(
        "command",
        choices=["build", "serve", "test"],
        help="执行的命令",
    )
    # 可选参数
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="配置文件路径 (默认: config.yaml)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="API 服务端口 (覆盖配置文件)",
    )
    args = parser.parse_args()

    # 初始化日志
    setup_logging()
    # 加载配置（config.yaml 默认在 dev/ 目录下）
    config_path = args.config
    if not os.path.isabs(config_path):
        config_path = os.path.join(_PROJECT_ROOT, config_path)
    config = load_config(config_path)
    # 修复 medical.json 路径（相对于项目根目录）
    if not os.path.isabs(config.kg.data_file):
        # 先尝试项目根（Agent工单12/），再尝试当前目录（Docker中为 /app/）
        candidate = os.path.join(_PROJECT_PARENT, config.kg.data_file)
        if not os.path.exists(candidate):
            candidate = os.path.join(_PROJECT_ROOT, config.kg.data_file)
        config.kg.data_file = candidate
    # 命令行端口覆盖配置
    if args.port:
        config.server.port = args.port

    # 分发命令
    if args.command == "build":
        cmd_build(config)  # 构建知识图谱
    elif args.command == "serve":
        cmd_serve(config)  # 启动服务
    elif args.command == "test":
        cmd_test(config)  # 运行测试


if __name__ == "__main__":
    main()
