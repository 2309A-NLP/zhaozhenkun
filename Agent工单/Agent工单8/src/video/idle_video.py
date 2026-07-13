"""
src/video/idle_video.py - 空闲视频编排模块
功能: 在数字人不说话时播放自定义空闲视频。
      实现说话↔空闲的平滑过渡(交叉淡入淡出)。
      对应工单需求: "在数字人不说话时，可以播放自定义视频，如背景动画等"
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)


class IdleVideoPlayer:
    """
    空闲视频循环播放器。
    预加载视频帧到内存，在数字人静音时无缝循环播放。
    """

    def __init__(self, video_path: str = None,
                 width: int = 1280, height: int = 720):
        self.video_path = video_path
        self.width = width
        self.height = height
        self._frames = []
        self._idx = 0
        self._loaded = False

    def load(self) -> bool:
        """预加载空闲视频所有帧到内存。"""
        if self.video_path is None:
            self._frames = [np.zeros((self.height, self.width, 3), dtype=np.uint8)]
            self._loaded = True
            return True
        try:
            cap = cv2.VideoCapture(self.video_path)
            if not cap.isOpened():
                logger.warning(f"无法打开空闲视频: {self.video_path}")
                return False
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                self._frames.append(cv2.resize(frame, (self.width, self.height)))
            cap.release()
            self._loaded = True
            logger.info(f"空闲视频加载: {len(self._frames)}帧")
            return True
        except Exception as e:
            logger.error(f"加载空闲视频失败: {e}")
            return False

    def get_frame(self) -> np.ndarray:
        """获取当前帧并推进索引(循环播放)。"""
        if not self._loaded or not self._frames:
            return np.zeros((self.height, self.width, 3), dtype=np.uint8)
        frame = self._frames[self._idx].copy()
        self._idx = (self._idx + 1) % len(self._frames)
        return frame


class TransitionManager:
    """
    说话↔空闲过渡管理器。
    通过alpha交叉淡入淡出实现平滑切换，避免突变。
    """

    def __init__(self, crossfade_frames: int = 12):
        """
        初始化过渡器。
        参数: crossfade_frames - 过渡帧数(12帧@25fps ≈ 0.5秒)
        """
        self.crossfade = crossfade_frames
        self._in_transit = False
        self._progress = 0
        self._to_idle = True

    def start(self, to_idle: bool) -> None:
        """开始过渡。to_idle=True表示说话→空闲，False表示空闲→说话。"""
        self._in_transit = True
        self._progress = 0
        self._to_idle = to_idle

    def blend(self, talking: np.ndarray, idle: np.ndarray) -> np.ndarray:
        """混合当前帧，返回过渡后的帧。"""
        if not self._in_transit:
            return talking
        t = self._progress / self.crossfade
        alpha = (1.0 - t) if self._to_idle else t
        alpha = np.clip(alpha, 0.0, 1.0)
        self._progress += 1
        if self._progress >= self.crossfade:
            self._in_transit = False
        return cv2.addWeighted(talking, alpha, idle, 1.0 - alpha, 0)
