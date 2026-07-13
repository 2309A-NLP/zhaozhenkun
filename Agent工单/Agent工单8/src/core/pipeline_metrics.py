"""
src/core/pipeline_metrics.py - 管线性能埋点辅助函数
功能: 为主流程提供统一的阶段耗时记录入口，避免在主文件中散落重复打点代码。
说明: 这里只做最小可用埋点，不引入复杂分析器。
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""

import time
from typing import Optional

from src.utils.metrics import get_metrics


class StageTimer:
    """轻量阶段计时器，用于在主流程中记录关键阶段耗时。"""

    def __init__(self):
        self._marks = {}

    def mark(self, name: str) -> None:
        """记录某个阶段起点或关键事件时间戳。"""
        self._marks[name] = time.time()

    def elapsed_since(self, name: str) -> Optional[float]:
        """返回距某个标记点经过的秒数，不存在则返回 None。"""
        started_at = self._marks.get(name)
        if started_at is None:
            return None
        return time.time() - started_at


def record_stage_latency(stage: str, latency_s: Optional[float]) -> None:
    """安全记录阶段耗时，避免空值或异常打断主流程。"""
    if latency_s is None or latency_s < 0:
        return
    metrics = get_metrics()
    metrics.record_stage(stage, latency_s)


def record_frame_count(frame_count: int) -> None:
    """按生成帧数补记 FPS 样本，用于前端展示当前输出帧率。"""
    if frame_count <= 0:
        return
    metrics = get_metrics()
    for _ in range(frame_count):
        metrics.record_frame()
