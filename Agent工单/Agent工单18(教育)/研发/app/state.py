# -*- coding: utf-8 -*-  # 工单18：指定源码编码为 UTF-8。
"""state.py - 工单18智能助教的轻量状态存储与原子写入模块。"""  # 工单18：声明当前文件功能。

from __future__ import annotations  # 工单18：启用延迟类型注解。

import json  # 工单18：导入 JSON 处理模块。
import threading  # 工单18：导入线程锁模块。
import uuid  # 工单18：导入唯一标识生成模块。

from app.config import STATE_FILE  # 工单18：导入状态文件路径配置。
from app.config import ensure_directories  # 工单18：导入目录初始化函数。
from app.config import now_text  # 工单18：导入当前时间文本函数。

_STATE_LOCK = threading.RLock()  # 工单18：创建支持重入的全局状态锁。


def _seed_users() -> list[dict]:  # 工单18：构造默认演示用户列表。
    return [  # 工单18：返回内置教师与学生账号。
        {"user_id": "teacher-001", "username": "teacher01", "password": "123456", "role": "teacher", "display_name": "王老师"},  # 工单18：定义教师演示账号。
        {"user_id": "student-001", "username": "student01", "password": "123456", "role": "student", "display_name": "李同学"},  # 工单18：定义学生演示账号。
    ]  # 工单18：结束演示用户列表。


def _seed_resources() -> list[dict]:  # 工单18：构造默认公共与私有知识资源。
    return [  # 工单18：返回初始化资源列表。
        {"resource_id": "res-public-001", "owner_id": "system", "owner_role": "system", "scope": "public", "title": "梯度下降核心讲义", "resource_type": "markdown", "file_name": "gradient_descent.md", "source_url": "", "tags": ["机器学习", "优化"], "media_kinds": ["text", "formula"], "content_text": "梯度下降用于沿损失函数负梯度方向迭代更新参数。公式：θ = θ - α∇J(θ)。常见误区是学习率过大导致震荡。", "chunks": [], "created_at": now_text()},  # 工单18：定义公共教材资源。
        {"resource_id": "res-public-002", "owner_id": "system", "owner_role": "system", "scope": "public", "title": "监督学习与无监督学习对比表", "resource_type": "table", "file_name": "compare.csv", "source_url": "", "tags": ["AI导论", "表格"], "media_kinds": ["text", "table"], "content_text": "| 类型 | 输入标签 | 典型任务 |\n| --- | --- | --- |\n| 监督学习 | 有 | 分类、回归 |\n| 无监督学习 | 无 | 聚类、降维 |", "chunks": [], "created_at": now_text()},  # 工单18：定义公共表格资源。
        {"resource_id": "res-private-001", "owner_id": "student-001", "owner_role": "student", "scope": "private", "title": "房价预测课堂笔记", "resource_type": "markdown", "file_name": "house_price_note.md", "source_url": "", "tags": ["案例", "回归"], "media_kinds": ["text"], "content_text": "老师用房价预测案例解释了梯度下降：先随机初始化权重，再根据误差不断调整，直到预测曲线逐渐贴近真实房价。", "chunks": [], "created_at": now_text()},  # 工单18：定义学生私有笔记资源。
        {"resource_id": "res-private-002", "owner_id": "teacher-001", "owner_role": "teacher", "scope": "private", "title": "高一集合教学设计草稿", "resource_type": "text", "file_name": "set_class_note.txt", "source_url": "", "tags": ["高中数学", "集合"], "media_kinds": ["text"], "content_text": "集合教学建议先用班级分组案例导入，再讲交集、并集、补集，最后通过维恩图完成巩固。", "chunks": [], "created_at": now_text()},  # 工单18：定义教师私有备课资源。
    ]  # 工单18：结束初始化资源列表。


def default_state() -> dict:  # 工单18：构造默认状态数据。
    return {"users": _seed_users(), "resources": _seed_resources(), "qa_logs": []}  # 工单18：返回默认状态对象。


def _write_state_unlocked(state: dict) -> None:  # 工单18：在锁内执行原子状态写入。
    temp_file = STATE_FILE.with_suffix(".tmp")  # 工单18：构造临时状态文件路径。
    temp_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")  # 工单18：先将状态写入临时文件。
    temp_file.replace(STATE_FILE)  # 工单18：用临时文件原子替换正式状态文件。


def ensure_state_file() -> None:  # 工单18：确保状态文件已创建。
    ensure_directories()  # 工单18：先确保目录存在。
    with _STATE_LOCK:  # 工单18：使用状态锁保护初始化过程。
        if not STATE_FILE.exists():  # 工单18：仅在状态文件不存在时初始化。
            _write_state_unlocked(default_state())  # 工单18：写入默认状态内容。


def load_state() -> dict:  # 工单18：加载当前状态数据。
    ensure_state_file()  # 工单18：先确保状态文件存在。
    with _STATE_LOCK:  # 工单18：在锁内读取状态文件避免与写入交叉。
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))  # 工单18：返回读取到的状态对象。


def save_state(state: dict) -> None:  # 工单18：保存状态数据到文件。
    ensure_state_file()  # 工单18：先确保状态文件存在。
    with _STATE_LOCK:  # 工单18：使用线程锁保护写入过程。
        _write_state_unlocked(state)  # 工单18：执行原子持久化写入。


def update_state(mutator) -> object:  # 工单18：在单次锁保护下完成状态更新。
    ensure_state_file()  # 工单18：先确保状态文件存在。
    with _STATE_LOCK:  # 工单18：在锁内执行读改写闭环。
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))  # 工单18：读取当前状态对象。
        result = mutator(state)  # 工单18：执行外部传入的状态变更逻辑。
        _write_state_unlocked(state)  # 工单18：原子写回最新状态内容。
        return result  # 工单18：返回状态变更函数的结果。


def new_id(prefix: str) -> str:  # 工单18：生成带前缀的唯一标识。
    return f"{prefix}-{uuid.uuid4().hex[:12]}"  # 工单18：返回截断后的唯一标识。
