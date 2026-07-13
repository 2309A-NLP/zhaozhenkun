"""
src/core/idle_output.py - 空闲画面输出辅助
功能: 为浏览器视频流提供空闲帧与默认空帧兜底，避免主流程内到处写回退判断。
说明: 本模块只负责取帧与兜底，不负责复杂状态机和跨通道过渡。
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""

import logging

import numpy as np

logger = logging.getLogger(__name__)


def build_empty_frame(height: int, width: int) -> np.ndarray:
    """构造一个黑色空帧，作为最终兜底输出。"""
    return np.zeros((height, width, 3), dtype=np.uint8)


def resolve_idle_frame(pipeline, height: int, width: int) -> np.ndarray:
    """优先返回空闲视频帧，失败时返回黑色空帧。"""
    empty_frame = build_empty_frame(height, width)
    if pipeline is None:
        return empty_frame

    idle_player = getattr(pipeline, "idle_player", None)
    if idle_player is None:
        return empty_frame

    try:
        frame = idle_player.get_frame()
        if frame is None or frame.size == 0:
            return empty_frame
        return frame
    except Exception as error:
        logger.warning(f"读取空闲帧失败: {error}")
        return empty_frame
