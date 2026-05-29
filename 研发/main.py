# -*- coding: utf-8 -*-
"""
ADSD（AI-Driven Student Development / 自适应学习系统）项目主入口模块。

本模块是项目的总启动入口，负责解析命令行参数并根据参数决定启动模式：
  - online 模式：启动在线推理/问答服务，供用户实时使用
  - offline 模式：运行离线任务，包括数据预处理、向量索引构建、
    服务健康检查、结果分析、知识库构建、PDF 导入等

用法示例：
1. 启动在线服务:
   python main.py online
2. 运行离线数据预处理:
   python main.py offline processor
3. 运行离线向量索引构建:
   python main.py offline index
4. 检查依赖服务:
   python main.py offline check
5. 分析处理结果:
   python main.py offline analyze
"""

import sys  # 导入系统模块，用于读取命令行参数
from pathlib import Path  # 导入 Path 类（虽未在本文件中直接使用，供模块统一引用）

# 导入离线任务的 runner 模块，封装了各种离线处理逻辑
from 研发 import runner as offline_runner
# 导入在线服务的主入口函数
from 研发.online_main import main as online_main


def print_usage() -> None:
    """打印命令行使用帮助信息，列出所有支持的模式和子任务。"""
    print("用法:")
    print("  python main.py online")               # 在线服务模式
    print("  python main.py offline processor")     # 离线数据预处理
    print("  python main.py offline index")         # 离线向量索引构建
    print("  python main.py offline check")         # 检查依赖服务状态
    print("  python main.py offline analyze")       # 分析已处理的数据
    print("  python main.py offline teacher-json")  # 生成语文老师知识库 JSON
    print("  python main.py offline pdf")           # 导入 PDF 数据到 Milvus


def main() -> None:
    """程序主入口函数。解析 sys.argv，根据第一参数选择 online/offline 模式并分派任务。"""
    args = sys.argv[1:]          # 获取命令行参数列表（去掉脚本名称本身）
    if not args:                 # 如果没有任何参数，默认启动在线服务
        print("未传入参数，默认启动在线服务...")
        online_main()            # 调用在线服务主函数
        return                   # 结束执行

    mode = args[0].lower()       # 获取第一个参数作为运行模式，并转为小写

    if mode == "online":         # online 模式：启动在线问答服务
        online_main()            # 调用在线服务主函数
        return                   # 结束执行

    if mode != "offline":        # 如果不是 online 也不是 offline，说明参数非法
        print_usage()            # 打印使用帮助
        return                   # 结束执行

    # 以下为 offline 模式逻辑
    if len(args) < 2:            # offline 模式下至少需要第二个参数指定子任务
        print_usage()            # 缺少子任务参数，打印帮助信息
        return                   # 结束执行

    task = args[1].lower()       # 获取第二个参数作为子任务名称，并转为小写

    if task == "processor":      # 子任务：运行数据处理器，对原始数据进行清洗、转换
        offline_runner.run_specialized_processor()
        return

    if task == "index":          # 子任务：构建向量索引，为后续语义检索做准备
        offline_runner.run_vector_index_creator()
        return

    if task == "check":          # 子任务：检查 Milvus 等依赖服务的端口是否可连接
        offline_runner.run_check_port()
        return

    if task == "analyze":        # 子任务：分析已处理数据的统计信息和分布情况
        offline_runner.run_analyze_processed_data()
        return

    if task == "teacher-json":   # 子任务：构建语文老师知识库的 JSON 数据文件
        script_path = offline_runner.build_chinese_teacher_knowledge()  # 获取生成的脚本路径
        print(f"请运行 Node 脚本生成语文老师知识库: {script_path}")       # 提示用户执行 Node 脚本
        return

    if task == "pdf":            # 子任务：将 PDF 文档解析后导入 Milvus 向量数据库
        offline_runner.run_pdf_to_milvus(args[2:])  # 传递 PDF 文件路径等额外参数
        return

    # 如果子任务名称不匹配任何已知任务，打印帮助信息
    print_usage()


if __name__ == "__main__":       # 判断是否以主程序方式运行（而非被导入）
    main()                       # 调用主函数，启动程序
