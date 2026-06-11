"""
system_monitor.py - RAG工单13 系统资源监控模块
需求: 工单第4类"监控与告警" — 可视化各组件KPI：延迟、吞吐量、错误率、资源利用率(CPU/内存/GPU)
功能: 1.CPU利用率 2.内存使用 3.请求统计 4.告警阈值检测 5.仪表盘JSON输出
"""
import logging
import os
import time
import threading
import json
import 研发.config as config

logger = logging.getLogger(__name__)



class SystemMonitor:
    """系统资源监控器 — 需求：监控CPU、内存、GPU利用率和请求指标"""

    def __init__(self):
        self._lock = threading.Lock()
        self.reset()

    def reset(self):
        """重置所有统计"""
        self.start_time = time.time()
        self.total_requests = 0
        self.success_requests = 0
        self.failed_requests = 0
        self.latencies = []  # 最近100条延迟记录
        self._cpu_samples = []
        self._mem_samples = []

    def record_request(self, success: bool, latency_seconds: float):
        """需求：记录每个请求的成功/失败和延迟"""
        with self._lock:
            self.total_requests += 1
            if success:
                self.success_requests += 1
            else:
                self.failed_requests += 1
            self.latencies.append(latency_seconds)
            if len(self.latencies) > 100:
                self.latencies.pop(0)

    def _get_cpu_percent(self) -> float:
        """获取当前CPU使用率（跨平台）"""
        try:
            import psutil
            return psutil.cpu_percent(interval=0.1)
        except ImportError:
            # 降级方案：读取/proc/stat
            try:
                with open("/proc/stat", "r") as f:
                    line = f.readline()
                parts = line.split()
                if len(parts) >= 5:
                    total = sum(int(x) for x in parts[1:])
                    idle = int(parts[4])
                    return round((1 - idle / total) * 100, 1) if total > 0 else 0.0
            except Exception:
                pass
        return -1.0

    def _get_memory_mb(self) -> dict:
        """获取内存使用情况"""
        try:
            import psutil
            mem = psutil.virtual_memory()
            return {"total_mb": round(mem.total / 1024**2, 1),
                    "used_mb": round(mem.used / 1024**2, 1),
                    "available_mb": round(mem.available / 1024**2, 1),
                    "percent": mem.percent}
        except ImportError:
            try:
                with open("/proc/meminfo", "r") as f:
                    lines = f.readlines()
                total = int(lines[0].split()[1]) // 1024
                avail = int(lines[2].split()[1]) // 1024
                return {"total_mb": total, "used_mb": total - avail,
                        "available_mb": avail,
                        "percent": round((total - avail) / total * 100, 1) if total > 0 else 0}
            except Exception:
                pass
        return {"total_mb": -1, "used_mb": -1, "available_mb": -1, "percent": -1.0}

    def _get_gpu_info(self) -> dict:
        """需求：GPU利用率监控（RTX5060）"""
        try:
            import torch
            if torch.cuda.is_available():
                allocated = torch.cuda.memory_allocated() / 1024**3
                reserved = torch.cuda.memory_reserved() / 1024**3
                return {"available": True,
                        "device": torch.cuda.get_device_name(0),
                        "memory_allocated_gb": round(allocated, 2),
                        "memory_reserved_gb": round(reserved, 2)}
        except Exception:
            pass
        try:
            # 尝试 nvidia-smi
            import subprocess
            result = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total",
                                     "--format=csv,noheader,nounits"],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                parts = result.stdout.strip().split(",")
                if len(parts) >= 3:
                    return {"available": True,
                            "utilization_pct": float(parts[0].strip()),
                            "memory_used_mb": float(parts[1].strip()),
                            "memory_total_mb": float(parts[2].strip())}
        except Exception:
            pass
        return {"available": False}

    def snapshot(self) -> dict:
        """需求：采集所有监控指标的快照 — 供仪表盘使用"""
        uptime = time.time() - self.start_time
        with self._lock:
            latencies = list(self.latencies)
            total = self.total_requests
            success = self.success_requests
            failed = self.failed_requests

        # 延迟统计
        latency_stats = {}
        if latencies:
            sorted_lat = sorted(latencies)
            n = len(sorted_lat)
            latency_stats = {
                "avg": round(sum(sorted_lat) / n, 3),
                "min": round(min(sorted_lat), 3),
                "max": round(max(sorted_lat), 3),
                "p50": round(sorted_lat[n // 2], 3),
                "p95": round(sorted_lat[int(n * 0.95)], 3) if n >= 2 else round(max(sorted_lat), 3),
                "p99": round(sorted_lat[int(n * 0.99)], 3) if n >= 2 else round(max(sorted_lat), 3),
            }

        # 吞吐量
        throughput = round(total / uptime, 2) if uptime > 0 else 0.0

        # 错误率
        error_rate = round(failed / total * 100, 1) if total > 0 else 0.0

        # 告警检查
        alerts = []
        if latency_stats.get("p95", 0) > 3.0:
            alerts.append({"level": "warning", "metric": "P95延迟",
                           "value": f"{latency_stats['p95']}s", "threshold": "3s",
                           "message": "P95延迟超过3秒验收标准"})
        if error_rate > 10:
            alerts.append({"level": "critical", "metric": "错误率",
                           "value": f"{error_rate}%", "threshold": "10%",
                           "message": "错误率超过10%，请检查API连接"})

        return {
            "uptime_seconds": round(uptime, 1),
            "requests": {"total": total, "success": success, "failed": failed,
                         "success_rate_pct": round(100 - error_rate, 1)},
            "error_rate_pct": error_rate,
            "throughput_qps": throughput,
            "latency_stats": latency_stats,
            "cpu_percent": self._get_cpu_percent(),
            "memory": self._get_memory_mb(),
            "gpu": self._get_gpu_info(),
            "alerts": alerts
        }

    def print_snapshot(self):
        """需求：打印监控快报到控制台"""
        s = self.snapshot()
        print(f"\n{'='*50}")
        print(f"📊 系统监控快报 (运行 {s['uptime_seconds']:.0f}s)")
        print(f"{'='*50}")
        print(f"  请求: {s['requests']['total']}次 (成功{s['requests']['success_rate_pct']}%)")
        print(f"  吞吐: {s['throughput_qps']} QPS  |  错误率: {s['error_rate_pct']}%")
        if s['latency_stats']:
            print(f"  延迟: avg={s['latency_stats']['avg']}s  P95={s['latency_stats']['p95']}s")
        print(f"  CPU: {s['cpu_percent']}%  |  内存: {s['memory']['percent']}%")
        if s['gpu'].get('available'):
            g = s['gpu']
            print(f"  GPU: {g.get('device','')}  显存: {g.get('memory_allocated_gb','?')}GB")
        if s['alerts']:
            print(f"  🚨 告警: {len(s['alerts'])}条")
            for a in s['alerts']:
                print(f"     [{a['level']}] {a['metric']}: {a['message']}")
        print(f"{'='*50}")


# 全局监控器单例
_monitor = None


def get_monitor() -> SystemMonitor:
    """获取全局监控器单例"""
    global _monitor
    if _monitor is None:
        _monitor = SystemMonitor()
    return _monitor


def save_monitoring_snapshot(output_dir=None):
    """需求：保存监控快照为JSON（供外部仪表盘消费）"""
    if output_dir is None:
        output_dir = config.OUTPUT_DIR
    m = get_monitor()
    snapshot = m.snapshot()
    path = os.path.join(output_dir, "monitoring_snapshot.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    print(f"💾 监控快照: {path}")
    return path

