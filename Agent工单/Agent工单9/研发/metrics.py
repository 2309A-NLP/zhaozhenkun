# -*- coding: utf-8 -*-
"""
metrics.py — 语音管线性能监控 (SLA 追踪)
--------------------------------------------------------------
功能: 实时追踪语音管线各阶段延迟，确保满足工单性能指标:
        - 端到端延迟 ≤ 3.0s
        - ASR 延迟 ≤ 0.5s
        - TTS 延迟 ≤ 1.7s
        - Agent 意图识别 ≤ 0.5s
        - Agent 工具调用 ≤ 1.0s

对照《08-实时数字人交互任务工单》验收标准。

工单编号: 人工智能NLP-Agent数字人项目-数字人与智能体的集成任务
所属目录: 研发
"""
import threading                     # 线程安全（多请求并发记录）
from collections import deque        # 定长队列（滑动窗口统计）
from dataclasses import dataclass, field  # 数据类（简洁定义）
import logging                       # 日志

logger = logging.getLogger("metrics")


@dataclass
class StageMetrics:
    """单个管线阶段的延迟统计器。

    维护最近 100 次采样的滑动窗口，提供 avg / last / p95 三种统计指标。
    """
    name: str                                  # 阶段名称（如 "asr"、"tts"）
    latencies: deque = field(                   # 最近 100 次延迟采样（秒）
        default_factory=lambda: deque(maxlen=100)
    )
    total: float = 0.0                          # 累计延迟（秒），用于计算均值
    count: int = 0                              # 累计采样次数

    def record(self, latency_s: float) -> None:
        """记录一次延迟采样。

        参数:
            latency_s: 该阶段的单次延迟（秒）
        """
        self.latencies.append(latency_s)         # 加入滑动窗口
        self.total += latency_s                  # 累加
        self.count += 1                          # 计数

    @property
    def avg_ms(self) -> float:
        """平均延迟（毫秒）。"""
        if self.count == 0:
            return 0.0
        return (self.total / self.count) * 1000

    @property
    def last_ms(self) -> float:
        """最近一次延迟（毫秒）。"""
        if not self.latencies:
            return 0.0
        return self.latencies[-1] * 1000

    @property
    def p95_ms(self) -> float:
        """P95 延迟（毫秒）—— 95% 的请求在此延迟以内。"""
        if not self.latencies:
            return 0.0
        sorted_lat = sorted(self.latencies)       # 升序排列
        idx = int(len(sorted_lat) * 0.95)         # 95% 分位索引
        return sorted_lat[min(idx, len(sorted_lat) - 1)] * 1000


class PipelineMetrics:
    """语音管线全链路性能追踪，对照工单 SLA 指标。

    维护 6 个阶段: asr / agent_intent / agent_tool / tts / dh_video / total。
    提供 SLA 合规检查和人类可读的性能摘要。
    """

    def __init__(self):
        """初始化各阶段指标 + SLA 阈值。"""
        self.stages = {
            "asr": StageMetrics("语音识别(ASR)"),               # FunASR
            "agent_intent": StageMetrics("Agent意图识别"),      # DeepSeek 意图分类
            "agent_tool": StageMetrics("Agent工具调用"),         # 工具执行
            "tts": StageMetrics("语音合成(TTS)"),               # GPT-SoVITS/EdgeTTS
            "dh_video": StageMetrics("数字人视频生成"),          # SadTalker/占位
            "total": StageMetrics("端到端总延迟"),               # 全链路
        }
        self._lock = threading.Lock()                            # 线程安全锁
        # SLA 阈值（毫秒）— 对照工单验收标准
        self.sla_thresholds = {
            "total": 3000,           # 端到端 ≤ 3.0s
            "asr": 500,              # ASR ≤ 0.5s
            "tts": 1700,             # TTS ≤ 1.7s
            "agent_intent": 500,     # 意图识别 ≤ 0.5s
            "agent_tool": 1000,      # 工具调用 ≤ 1.0s
        }

    def record_stage(self, stage: str, latency_s: float) -> None:
        """记录某阶段的单次延迟。

        参数:
            stage: 阶段名（必须是 stages 中的 key）
            latency_s: 延迟（秒）
        """
        with self._lock:                                     # 线程安全写入
            if stage in self.stages:
                self.stages[stage].record(latency_s)

    def check_sla(self) -> dict:
        """对照工单 SLA 检查各项指标。

        返回:
            dict: {阶段名: {"last_ms": float, "avg_ms": float,
                            "threshold_ms": int, "ok": bool}}
        """
        with self._lock:
            result = {}
            for name, threshold in self.sla_thresholds.items():
                if name in self.stages:
                    last = self.stages[name].last_ms          # 最近一次
                    avg = self.stages[name].avg_ms            # 平均
                    result[name] = {
                        "last_ms": round(last, 1),
                        "avg_ms": round(avg, 1),
                        "threshold_ms": threshold,
                        "ok": last <= threshold if last > 0 else True,  # 无数据=合规
                    }
            return result

    def summary(self) -> str:
        """生成人类可读的性能摘要（单行）。"""
        sla = self.check_sla()
        all_ok = all(v["ok"] for v in sla.values())           # 全部达标？
        parts = []
        for name, info in sla.items():
            icon = "✓" if info["ok"] else "✗"                 # 达标/超标图标
            parts.append(f"{name}={info['last_ms']:.0f}ms{icon}")
        return f"SLA {'✓' if all_ok else '✗'} | " + " ".join(parts)

    @property
    def total_last_ms(self) -> float:
        """最近一次端到端延迟（毫秒）。"""
        return self.stages["total"].last_ms

    @property
    def total_avg_ms(self) -> float:
        """平均端到端延迟（毫秒）。"""
        return self.stages["total"].avg_ms


# ============================================================
# 全局单例 — 整个进程共享
# ============================================================
_global_metrics = PipelineMetrics()


def get_metrics() -> PipelineMetrics:
    """获取全局性能追踪单例。

    返回:
        PipelineMetrics 实例（全局唯一）
    """
    return _global_metrics


# ============================================================
# 自测
# ============================================================
if __name__ == "__main__":
    m = get_metrics()
    # 模拟各阶段延迟记录
    m.record_stage("asr", 0.2)
    m.record_stage("agent_intent", 0.3)
    m.record_stage("agent_tool", 0.5)
    m.record_stage("tts", 0.8)
    m.record_stage("total", 2.0)
    print(m.summary())
    import json
    print(json.dumps(m.check_sla(), indent=2, ensure_ascii=False))
