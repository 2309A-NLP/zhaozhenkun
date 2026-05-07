# -*- coding: utf-8 -*-
import math
import socket
import threading
import time
from collections import deque


class QPSMonitor:
    """
    QPS（每秒查询数）监控器
    用于记录和统计HTTP请求的QPS、成功率、响应时间等指标
    """

    def __init__(self):
        """
        初始化QPS监控器
        """
        self.started_at = time.time()  # 监控器启动时间戳（秒）
        self.request_timestamps = deque()  # 双端队列，存储所有请求的时间戳（用于QPS计算）
        self.timeline = deque(maxlen=900)  # 固定长度队列（最多900条），存储最近15分钟每个请求的详细信息
        self.total_requests = 0  # 总请求数
        self.success_requests = 0  # 成功请求数
        self.error_requests = 0  # 失败请求数
        self.lock = threading.RLock()  # 可重入锁，保证多线程安全

    def record(self, timestamp, duration_ms, success):
        """
        记录一个请求的详细信息

        参数:
            timestamp: 请求发生的时间戳（秒）
            duration_ms: 请求处理耗时（毫秒）
            success: 请求是否成功（True/False）
        """
        with self.lock:  # 加锁保证线程安全
            # 更新计数器
            self.total_requests += 1
            if success:
                self.success_requests += 1
            else:
                self.error_requests += 1

            # 存储时间戳用于QPS计算
            self.request_timestamps.append(timestamp)

            # 存储详细记录到时间线（自动保留最近900条）
            self.timeline.append(
                {
                    "timestamp": timestamp,
                    "duration_ms": round(duration_ms, 2),
                    "success": success,
                }
            )

            # 清理超过15分钟的旧时间戳
            self._trim_locked(timestamp)

    def _trim_locked(self, now_ts):
        """
        删除超过15分钟的旧请求时间戳（必须在锁内调用）

        参数:
            now_ts: 当前时间戳（秒）
        """
        cutoff = now_ts - 15 * 60  # 15分钟前的时间点（秒）
        # 循环删除队列头部所有早于cutoff的时间戳
        while self.request_timestamps and self.request_timestamps[0] < cutoff:
            self.request_timestamps.popleft()

    def _count_recent_locked(self, now_ts, seconds):
        """
        统计最近指定秒数内的请求数量（必须在锁内调用）

        参数:
            now_ts: 当前时间戳（秒）
            seconds: 统计的时间窗口（秒）

        返回:
            int: 时间窗口内的请求数
        """
        return sum(1 for ts in self.request_timestamps if ts >= now_ts - seconds)

    def snapshot(self):
        """
        获取当前QPS监控数据的快照

        返回:
            dict: 包含所有QPS指标和统计数据的字典
        """
        now_ts = time.time()  # 当前时间戳

        with self.lock:  # 加锁保证线程安全
            # 清理过期数据
            self._trim_locked(now_ts)

            # 计算各时间窗口的QPS（每秒请求数）
            current_qps = self._count_recent_locked(now_ts, 1)  # 当前QPS（最近1秒）
            qps_1min = round(self._count_recent_locked(now_ts, 60) / 60, 2)  # 平均QPS（最近1分钟）
            qps_5min = round(self._count_recent_locked(now_ts, 300) / 300, 2)  # 平均QPS（最近5分钟）
            qps_15min = round(self._count_recent_locked(now_ts, 900) / 900, 2)  # 平均QPS（最近15分钟）

            # 计算运行时长
            uptime_seconds = max(now_ts - self.started_at, 0.001)

            # 计算平均QPS（从启动到现在的总平均值）
            avg_qps = round(self.total_requests / uptime_seconds, 2)

            # 计算成功率（百分比）
            success_rate = round((self.success_requests / self.total_requests) * 100,
                                 2) if self.total_requests else 100.0

            # 获取最近60条详细记录（用于图表展示）
            recent = list(self.timeline)[-60:]

        # 返回所有指标数据的字典
        return {
            "current_qps": current_qps,  # 当前QPS
            "qps_1min": qps_1min,  # 1分钟平均QPS
            "qps_5min": qps_5min,  # 5分钟平均QPS
            "qps_15min": qps_15min,  # 15分钟平均QPS
            "total_requests": self.total_requests,  # 总请求数
            "success_requests": self.success_requests,  # 成功请求数
            "error_requests": self.error_requests,  # 失败请求数
            "success_rate": success_rate,  # 成功率（%）
            "avg_qps": avg_qps,  # 平均QPS（从启动至今）
            "uptime_seconds": round(uptime_seconds, 2),  # 运行时长（秒）
            "recent": recent,  # 最近60条请求详情
        }


def percentile(values, ratio):
    """
    计算一组数值的百分位数（支持线性插值）

    参数:
        values: 数值列表
        ratio: 百分位（0-1之间），例如0.5表示中位数，0.99表示99分位

    返回:
        float: 计算出的百分位数，四舍五入保留2位小数
    """
    if not values:  # 空列表返回0
        return 0.0

    # 排序
    sorted_values = sorted(values)

    # 只有一个元素时直接返回
    if len(sorted_values) == 1:
        return round(float(sorted_values[0]), 2)

    # 计算百分位位置（使用线性插值算法）
    position = ratio * (len(sorted_values) - 1)
    lower = math.floor(position)  # 下界索引
    upper = math.ceil(position)  # 上界索引

    # 如果刚好是整数位置，直接返回
    if lower == upper:
        return round(float(sorted_values[lower]), 2)

    # 否则在两个值之间线性插值
    lower_value = sorted_values[lower]
    upper_value = sorted_values[upper]
    interpolated = lower_value + (upper_value - lower_value) * (position - lower)

    return round(float(interpolated), 2)


def choose_port(preferred_port, max_tries=20):
    """
    自动选择一个可用的端口号

    参数:
        preferred_port: 首选端口号
        max_tries: 最多尝试的次数（从preferred_port开始递增尝试）

    返回:
        int: 找到的第一个可用端口号

    异常:
        RuntimeError: 在指定范围内找不到可用端口时抛出
    """
    # 从首选端口开始，依次向上尝试最多max_tries个端口
    for port in range(preferred_port, preferred_port + max_tries + 1):
        # 创建socket并检查端口是否被占用
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.3)  # 设置超时时间0.3秒
            # connect_ex()返回0表示连接成功（端口已被占用），非0表示可用
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                continue  # 端口被占用，尝试下一个
            return port  # 端口可用，返回

    # 尝试完所有端口都没找到可用的
    raise RuntimeError(f"未找到可用端口，起始端口: {preferred_port}")