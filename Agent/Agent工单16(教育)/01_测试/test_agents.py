# -*- coding: utf-8 -*-  # 指定源码使用 UTF-8 编码。
"""test_agents.py - 教育 Agent 对话与约束测试模块。"""  # 说明当前文件职责。

import sys  # 导入解释器路径工具。
from pathlib import Path  # 导入路径处理工具。


ROOT = Path(__file__).resolve().parents[1] / "03_研发"  # 定位研发源码目录。
sys.path.insert(0, str(ROOT))  # 将研发目录加入模块搜索路径。

from services.agent_orchestrator import AgentOrchestrator  # 导入主业务编排器。


def test_tutor_scene_keeps_history(isolated_settings):  # 验证智能助教场景会保留多轮对话历史。
    orchestrator = AgentOrchestrator(isolated_settings)  # 使用隔离配置创建编排器。
    first = orchestrator.execute_scene("tutor", {  # 执行第一轮智能助教提问。
        "course": "Python程序设计",  # 传入课程名称。
        "message": "什么是 for 循环？",  # 传入第一轮问题。
        "session_id": "pytest-session",  # 传入固定测试会话编号。
    })  # 完成第一轮智能助教调用。
    second = orchestrator.execute_scene("tutor", {  # 执行第二轮智能助教提问。
        "course": "Python程序设计",  # 传入课程名称。
        "message": "那 while 和它有什么区别？",  # 传入第二轮问题。
        "session_id": "pytest-session",  # 继续使用相同会话编号。
    })  # 完成第二轮智能助教调用。
    assert first["scene"] == "tutor"  # 断言第一轮返回场景正确。
    assert len(second["history"]) >= 3  # 断言第二轮结果中保留了历史对话。


def test_python_file_line_limit():  # 验证研发目录下所有 Python 文件都不超过 300 行。
    python_files = list((Path(__file__).resolve().parents[1] / "03_研发").rglob("*.py"))  # 读取研发目录下全部 Python 文件。
    assert python_files  # 断言至少存在一个 Python 文件。
    for file_path in python_files:  # 遍历全部 Python 文件。
        line_count = len(file_path.read_text(encoding="utf-8").splitlines())  # 计算当前文件行数。
        assert line_count <= 300, f"{file_path} 超过 300 行: {line_count}"  # 断言当前文件行数符合约束。
