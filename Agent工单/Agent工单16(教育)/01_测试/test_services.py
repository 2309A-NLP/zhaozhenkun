# -*- coding: utf-8 -*-  # 指定源码使用 UTF-8 编码。
"""test_services.py - 教育 Agent 业务服务测试模块。"""  # 说明当前文件职责。

import sys  # 导入解释器路径工具。
from pathlib import Path  # 导入路径处理工具。


ROOT = Path(__file__).resolve().parents[1] / "03_研发"  # 定位研发源码目录。
sys.path.insert(0, str(ROOT))  # 将研发目录加入模块搜索路径。

from services.agent_orchestrator import AgentOrchestrator  # 导入主业务编排器。


def test_lesson_scene_returns_summary(isolated_settings):  # 验证智能备课场景能返回结果摘要。
    orchestrator = AgentOrchestrator(isolated_settings)  # 使用隔离配置创建编排器。
    result = orchestrator.execute_scene("lesson", {  # 执行智能备课场景。
        "course": "高等数学",  # 传入课程名称。
        "topic": "函数与导数基础",  # 传入课程主题。
        "goal": "生成可授课方案",  # 传入教学目标。
        "audience": "高职学生",  # 传入目标学生群体。
        "message": "请加入板书设计和课堂小测。",  # 传入文本补充要求。
        "model_provider": "qwen",  # 传入千问文本模型选择。
    })  # 完成智能备课调用。
    assert result["scene"] == "lesson"  # 断言场景标识正确。
    assert result["summary"]  # 断言返回内容不为空。
    assert "板书设计" in result["summary"]  # 断言文本补充要求已进入生成结果。
    assert result["model_provider"] == "qwen"  # 断言返回结果包含当前模型服务商。
    assert result["input_mode"] == "text"  # 断言纯文本请求走文本模式。


def test_personalization_scene_returns_profile(isolated_settings):  # 验证个性化学习场景能返回学生画像。
    orchestrator = AgentOrchestrator(isolated_settings)  # 使用隔离配置创建编排器。
    result = orchestrator.execute_scene("personalization", {  # 执行个性化学习场景。
        "course": "高等数学",  # 传入课程名称。
        "focus": "导数易错点纠偏",  # 传入学习聚焦主题。
        "student_id": "STU001",  # 传入目标学生编号。
    })  # 完成个性化学习调用。
    assert result["scene"] == "personalization"  # 断言场景标识正确。
    assert result["profile"]["name"] == "李晓彤"  # 断言返回正确的学生画像。


def test_evaluation_scene_reads_message_field(isolated_settings):  # 验证教学评估场景支持直接读取文本输入内容。
    orchestrator = AgentOrchestrator(isolated_settings)  # 使用隔离配置创建编排器。
    result = orchestrator.execute_scene("evaluation", {  # 执行教学评估场景。
        "task_name": "单元作业一",  # 传入作业名称。
        "message": "学生答案：函数在该点不可导，因为左右导数不相等。",  # 传入纯文本作答内容。
        "model_provider": "deepseek",  # 传入当前模型服务商。
    })  # 完成教学评估调用。
    assert result["scene"] == "evaluation"  # 断言场景标识正确。
    assert "学生答案" in result["feedback"]  # 断言评估结果已读取 message 字段内容。
    assert result["input_mode"] == "text"  # 断言评估场景支持纯文本交互。
