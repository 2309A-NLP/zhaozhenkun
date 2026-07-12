# -*- coding: utf-8 -*-  # 指定源码使用 UTF-8 编码。
"""conftest.py - 教育 Agent 测试共享夹具模块。"""  # 说明当前文件职责。

import shutil  # 导入文件复制工具。
import sys  # 导入解释器路径工具。
from pathlib import Path  # 导入路径处理工具。

import pytest  # 导入 pytest 测试框架。


ROOT = Path(__file__).resolve().parents[1] / "03_研发"  # 定位研发源码目录。
sys.path.insert(0, str(ROOT))  # 将研发目录加入模块搜索路径。

from config import load_settings  # 导入配置加载函数。


@pytest.fixture  # 将函数声明为 pytest 夹具。
def isolated_settings(tmp_path):  # 为每个测试构建隔离的数据配置。
    settings = load_settings()  # 读取项目默认配置。
    source_dir = ROOT / "data"  # 定位演示数据源目录。
    data_dir = tmp_path / "data"  # 创建临时数据目录路径。
    upload_dir = tmp_path / "uploads"  # 创建临时上传目录路径。
    data_dir.mkdir(parents=True, exist_ok=True)  # 确保临时数据目录存在。
    upload_dir.mkdir(parents=True, exist_ok=True)  # 确保临时上传目录存在。
    for name in ["courses.json", "knowledge_base.json", "students.json"]:  # 遍历需要复制的静态演示数据文件。
        shutil.copy2(source_dir / name, data_dir / name)  # 将静态演示数据复制到临时目录。
    (data_dir / "sessions.json").write_text("{}\n", encoding="utf-8")  # 初始化空会话数据文件。
    (data_dir / "artifacts.json").write_text("[]\n", encoding="utf-8")  # 初始化空产出记录文件。
    settings["DATA_DIR"] = str(data_dir)  # 覆盖数据目录配置。
    settings["UPLOAD_DIR"] = str(upload_dir)  # 覆盖上传目录配置。
    settings["COURSES_PATH"] = str(data_dir / "courses.json")  # 覆盖课程数据路径。
    settings["KNOWLEDGE_PATH"] = str(data_dir / "knowledge_base.json")  # 覆盖知识库数据路径。
    settings["STUDENTS_PATH"] = str(data_dir / "students.json")  # 覆盖学生数据路径。
    settings["SESSIONS_PATH"] = str(data_dir / "sessions.json")  # 覆盖会话数据路径。
    settings["ARTIFACTS_PATH"] = str(data_dir / "artifacts.json")  # 覆盖产出记录路径。
    return settings  # 返回隔离后的测试配置字典。
