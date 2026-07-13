"""
src/utils/metrics.py - 延迟与性能追踪模块
功能: 追踪管线各阶段的延迟，确保满足工单性能指标:
      - 整体延迟 ≤ 3s
      - TTS延迟 ≤ 1.7s
      - 音频处理延迟 ≤ 0.4s
      - 帧率 ≥ 20fps
工单编号: 人工智能NLP-Agent数字人项目-实时数字人交互任务
"""
import time
import threading
from collections import deque
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class StageMetrics:
    """单个管线阶段的延迟统计器。"""
    name: str
    latencies: deque = field(default_factory=lambda: deque(maxlen=100))
    total: float = 0.0
    count: int = 0

    def record(self, latency_s: float) -> None:
        """记录一次延迟采样(秒)。"""
        self.latencies.append(latency_s)
        self.total += latency_s
        self.count += 1

    @property
    def avg_ms(self) -> float:
        """平均延迟(毫秒)。"""
        if self.count == 0:
            return 0.0
        return (self.total / self.count) * 1000

    @property
    def last_ms(self) -> float:
        """最近一次延迟(毫秒)。"""
        if not self.latencies:
            return 0.0
        return self.latencies[-1] * 1000


class PipelineMetrics:
    """管线全链路性能追踪，对照工单SLA指标。"""

    def __init__(self):
        """初始化各阶段指标。"""
        self.stages = {
            "asr": StageMetrics("语音识别"),
            "llm_first": StageMetrics("LLM首Token"),
            "tts_first": StageMetrics("TTS首音频"),
            "audio_feat": StageMetrics("Mel特征"),
            "lipsync_infer": StageMetrics("唇形推理"),
            "frame_comp": StageMetrics("帧合成"),
            "total": StageMetrics("端到端"),
        }
        self._fps_deque = deque(maxlen=50)
        self._lock = threading.Lock()

    def record_stage(self, stage: str, latency_s: float) -> None:
        """记录某阶段延迟。"""
        with self._lock:
            if stage in self.stages:
                self.stages[stage].record(latency_s)

    def record_frame(self) -> None:
        """记录一帧的生成时间戳(用于FPS计算)。"""
        with self._lock:
            self._fps_deque.append(time.time())

    @property
    def fps(self) -> float:
        """当前实时帧率。"""
        with self._lock:
            if len(self._fps_deque) < 2:
                return 0.0
            dur = self._fps_deque[-1] - self._fps_deque[0]
            if dur <= 0:
                return 0.0
            return (len(self._fps_deque) - 1) / dur

    def check_sla(self) -> dict:
        """对照工单SLA检查各项指标。"""
        t = self.stages["total"].last_ms
        tts = self.stages["tts_first"].last_ms
        af = self.stages["audio_feat"].last_ms
        f = self.fps
        return {
            "total_ms": t, "total_ok": t <= 3000,
            "tts_ms": tts, "tts_ok": tts <= 1700,
            "audio_ms": af, "audio_ok": af <= 400,
            "fps": f, "fps_ok": f >= 20,
        }

    def summary(self) -> str:
        """生成人类可读的性能报告。"""
        s = self.check_sla()
        return (
            f"延迟: 总{s['total_ms']:.0f}ms[{'✓' if s['total_ok'] else '✗'}] "
            f"TTS{s['tts_ms']:.0f}ms[{'✓' if s['tts_ok'] else '✗'}] "
            f"音频{s['audio_ms']:.0f}ms[{'✓' if s['audio_ok'] else '✗'}] "
            f"FPS{s['fps']:.1f}[{'✓' if s['fps_ok'] else '✗'}]"
        )


_global_metrics = PipelineMetrics()


def get_metrics() -> PipelineMetrics:
    """获取全局性能追踪单例。"""
    return _global_metrics
