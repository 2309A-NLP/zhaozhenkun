# -*- coding: utf-8 -*-   # 指定文件编码为UTF-8，支持中文等字符
"""
ADSD 多角色对话系统 — 项目入口（旧版）。

本文件是项目的旧版启动入口，提供命令行参数解析，
根据参数决定启动在线服务或运行离线任务。

用法:
  python main.py online          # 启动在线服务
  python main.py offline xxx     # 离线任务
"""
import sys   # 导入系统模块，用于读取命令行参数
from 研发 import runner as dev_runner   # 导入离线任务runner模块，作为dev_runner使用
from 研发.online_main import main as online_main   # 导入在线服务主入口函数


def print_usage():   # 定义函数：打印使用帮助信息
    """打印命令行使用帮助信息"""   # 函数文档字符串
    print("用法:")   # 打印用法标题
    print("  python main.py online")   # 打印在线服务启动命令
    print("  python main.py offline processor")   # 打印离线数据处理命令
    print("  python main.py offline index")   # 打印离线索引构建命令
    print("  python main.py offline check")   # 打印服务检查命令
    print("  python main.py offline analyze")   # 打印数据分析命令
    print("  python main.py offline teacher-json")   # 打印知识库生成命令
    print("  python main.py offline pdf")   # 打印PDF导入命令


def main():   # 定义主函数：程序入口
    """程序主入口函数，解析命令行参数并分派任务"""   # 函数文档字符串
    args = sys.argv[1:]   # 获取命令行参数列表（去掉脚本名称本身）
    if not args:   # 如果没有传入任何参数
        print("未传入参数，默认启动在线服务...")   # 打印提示信息
        online_main()   # 默认启动在线服务
        return   # 结束执行
    mode = args[0].lower()   # 获取第一个参数作为运行模式，并转为小写
    if mode == "online":   # 如果模式是"online"（在线服务）
        online_main()   # 启动在线服务
        return   # 结束执行
    if mode != "offline":   # 如果模式既不是"online"也不是"offline"
        print_usage()   # 打印使用帮助
        return   # 结束执行
    if len(args) < 2:   # 如果是offline模式但没有指定子任务
        print_usage()   # 打印使用帮助
        return   # 结束执行
    task = args[1].lower()   # 获取第二个参数作为子任务名称，并转为小写
    if task == "processor":   # 子任务：运行数据处理器
        dev_runner.run_specialized_processor()   # 调用runner中的数据处理函数
    elif task == "index":   # 子任务：构建向量索引
        dev_runner.run_vector_index_creator()   # 调用runner中的索引创建函数
    elif task == "check":   # 子任务：检查服务端口
        dev_runner.run_check_port()   # 调用runner中的端口检查函数
    elif task == "analyze":   # 子任务：分析处理结果
        dev_runner.run_analyze_processed_data()   # 调用runner中的数据分析函数
    elif task == "teacher-json":   # 子任务：生成语文老师知识库
        script_path = dev_runner.build_chinese_teacher_knowledge()   # 获取JS脚本路径
        print(f"请运行 Node 脚本: {script_path}")   # 提示用户手动运行Node脚本
    elif task == "pdf":   # 子任务：导入PDF到Milvus
        dev_runner.run_pdf_to_milvus(args[2:])   # 调用runner中的PDF导入函数，传递额外参数
    else:   # 子任务名称不匹配任何已知任务
        print_usage()   # 打印使用帮助


if __name__ == "__main__":   # 判断是否以主程序方式运行（而非被导入）
    main()   # 调用主函数，启动程序
