# -*- coding: utf-8 -*-
"""
ADSD 多角色对话系统 — 项目入口。

用法:
  python main.py online          # 启动在线服务
  python main.py offline xxx     # 离线任务
"""
import sys
from 研发 import runner as dev_runner
from 研发.online_main import main as online_main


def print_usage():
    print("用法:")
    print("  python main.py online")
    print("  python main.py offline processor")
    print("  python main.py offline index")
    print("  python main.py offline check")
    print("  python main.py offline analyze")
    print("  python main.py offline teacher-json")
    print("  python main.py offline pdf")


def main():
    args = sys.argv[1:]
    if not args:
        print("未传入参数，默认启动在线服务...")
        online_main()
        return
    mode = args[0].lower()
    if mode == "online":
        online_main()
        return
    if mode != "offline":
        print_usage()
        return
    if len(args) < 2:
        print_usage()
        return
    task = args[1].lower()
    if task == "processor":
        dev_runner.run_specialized_processor()
    elif task == "index":
        dev_runner.run_vector_index_creator()
    elif task == "check":
        dev_runner.run_check_port()
    elif task == "analyze":
        dev_runner.run_analyze_processed_data()
    elif task == "teacher-json":
        script_path = dev_runner.build_chinese_teacher_knowledge()
        print(f"请运行 Node 脚本: {script_path}")
    elif task == "pdf":
        dev_runner.run_pdf_to_milvus(args[2:])
    else:
        print_usage()


if __name__ == "__main__":
    main()
