# -*- coding: utf-8 -*-   # 指定文件编码为UTF-8，支持中文等字符
"""
离线任务统一入口。

该模块提供离线处理各子任务的调度入口函数，
通过runpy.run_path动态运行各子模块脚本。
每个函数对应一个离线任务，可在外部统一调用。
"""

from pathlib import Path   # 导入Path类，用于跨平台路径操作
import runpy   # 导入runpy模块，用于以脚本方式运行Python文件
import sys   # 导入sys模块，用于访问和修改命令行参数


PROJECT_ROOT = Path(__file__).resolve().parent.parent   # 获取项目根目录：当前文件所在目录的父目录


def run_specialized_processor():   # 定义函数：运行专门数据处理器
    runpy.run_path(str(PROJECT_ROOT / "development" / "specialized_data_processor.py"), run_name="__main__")
    # 以__main__方式运行specialized_data_processor.py脚本，触发其主流程


def run_analyze_processed_data():   # 定义函数：分析处理后的数据
    runpy.run_path(str(PROJECT_ROOT / "development" / "analyze_processed_data.py"), run_name="__main__")
    # 以__main__方式运行analyze_processed_data.py脚本，触发数据分析


def run_check_port():   # 定义函数：检查服务端口状态
    runpy.run_path(str(PROJECT_ROOT / "testing" / "check_port.py"), run_name="__main__")
    # 以__main__方式运行check_port.py脚本，检查各服务是否正常运行


def run_vector_index_creator():   # 定义函数：运行向量索引创建器
    runpy.run_path(str(PROJECT_ROOT / "development" / "vector_index_creator.py"), run_name="__main__")
    # 以__main__方式运行vector_index_creator.py脚本，构建向量索引


def build_chinese_teacher_knowledge():   # 定义函数：构建语文教师知识库
    script = PROJECT_ROOT / "development" / "scripts" / "build_chinese_teacher_knowledge.js"   # 定位JS脚本路径
    return script   # 返回JS脚本路径供外部使用


def run_pdf_to_milvus(args=None):   # 定义函数：PDF转Milvus向量库（支持传参）
    script_path = str(PROJECT_ROOT / "development" / "pdf_to_milvus.py")   # 获取PDF处理脚本的路径
    previous_argv = sys.argv[:]   # 备份当前命令行参数列表
    try:   # 开始异常处理块
        sys.argv = [script_path, *(args or [])]   # 临时替换命令行参数：脚本路径+传入参数
        runpy.run_path(script_path, run_name="__main__")   # 以__main__方式运行pdf_to_milvus.py
    finally:   # 无论是否发生异常都执行
        sys.argv = previous_argv   # 恢复原有的命令行参数列表
