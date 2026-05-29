"""
app_monitor — ADSD 项目在线模块系统监控工具。

功能说明：
- QPSMonitor 类：记录和统计 HTTP 请求的 QPS（每秒查询数）、成功率、响应时间等指标
- percentile 函数：计算一组数值的百分位数（支持线性插值算法）
- choose_port 函数：自动检测并选择一个可用的端口号
"""
# -*- coding: utf-8 -*-
# 指定文件编码为UTF-8，确保中文字符能正确处理

import math
# 导入math模块，用于数学运算（如floor/ceil取整）
import socket
# 导入socket模块，用于网络通信和端口检测
import threading
# 导入threading模块，用于多线程安全操作
import time
# 导入time模块，用于获取时间戳
from collections import deque
# 从collections导入deque（双端队列），用于高效地添加和删除元素

class QPSMonitor:
    # 定义QPS监控器类

    """
    QPS（每秒查询数）监控器
    用于记录和统计HTTP请求的QPS、成功率、响应时间等指标
    """

    def __init__(self):
        # 定义类的构造方法（初始化方法）

        """
        初始化QPS监控器
        """
        self.started_at = time.time()
        # 记录监控器启动时的时间戳（秒），用于计算运行时长
        self.request_timestamps = deque()
        # 创建双端队列，存储所有请求的时间戳（用于QPS计算，会定期清理过期数据）
        self.timeline = deque(maxlen=900)
        # 创建固定长度的双端队列（最多900条），存储最近每个请求的详细信息
        self.total_requests = 0
        # 总请求数计数器
        self.success_requests = 0
        # 成功请求数计数器
        self.error_requests = 0
        # 失败请求数计数器
        self.lock = threading.RLock()
        # 创建可重入锁（RLock），保证多线程环境下对共享数据的安全访问

    def record(self, timestamp, duration_ms, success):
        # 定义方法：记录一个请求的详细信息

        """
        记录一个请求的详细信息

        参数:
            timestamp: 请求发生的时间戳（秒）
            duration_ms: 请求处理耗时（毫秒）
            success: 请求是否成功（True/False）
        """
        with self.lock:
            # 使用锁保护共享数据，确保线程安全
            self.total_requests += 1
            # 总请求数加1
            if success:
                # 如果请求成功
                self.success_requests += 1
                # 成功请求数加1
            else:
                # 如果请求失败
                self.error_requests += 1
                # 失败请求数加1

            self.request_timestamps.append(timestamp)
            # 将请求时间戳添加到队列尾部（用于计算QPS）

            self.timeline.append(
                # 将请求详细信息添加到时间线队列（自动保留最近900条记录）
                {
                    "timestamp": timestamp,
                    # 请求时间戳
                    "duration_ms": round(duration_ms, 2),
                    # 请求耗时，保留2位小数
                    "success": success,
                    # 是否成功
                }
            )

            self._trim_locked(timestamp)
            # 清理超过15分钟的旧时间戳（在锁内调用，保证安全）

    def _trim_locked(self, now_ts):
        # 定义私有方法：删除超过15分钟的旧请求时间戳

        """
        删除超过15分钟的旧请求时间戳（必须在锁内调用）

        参数:
            now_ts: 当前时间戳（秒）
        """
        cutoff = now_ts - 15 * 60
        # 计算15分钟前的时间点（秒）
        while self.request_timestamps and self.request_timestamps[0] < cutoff:
            # 循环：当队列不为空且队列头部的时间戳早于cutoff
            self.request_timestamps.popleft()
            # 从队列左侧（头部）弹出最早的时间戳

    def _count_recent_locked(self, now_ts, seconds):
        # 定义私有方法：统计最近指定秒数内的请求数量

        """
        统计最近指定秒数内的请求数量（必须在锁内调用）

        参数:
            now_ts: 当前时间戳（秒）
            seconds: 统计的时间窗口（秒）

        返回:
            int: 时间窗口内的请求数
        """
        return sum(1 for ts in self.request_timestamps if ts >= now_ts - seconds)
        # 遍历队列，统计时间戳大于等于（当前时间 - 窗口时长）的请求数量

    def snapshot(self):
        # 定义方法：获取当前QPS监控数据的快照

        """
        获取当前QPS监控数据的快照

        返回:
            dict: 包含所有QPS指标和统计数据的字典
        """
        now_ts = time.time()
        # 获取当前时间戳

        with self.lock:
            # 加锁保证线程安全
            self._trim_locked(now_ts)
            # 先清理过期数据

            current_qps = self._count_recent_locked(now_ts, 1)
            # 计算当前QPS（最近1秒内的请求数）
            qps_1min = round(self._count_recent_locked(now_ts, 60) / 60, 2)
            # 计算最近1分钟的平均QPS
            qps_5min = round(self._count_recent_locked(now_ts, 300) / 300, 2)
            # 计算最近5分钟的平均QPS
            qps_15min = round(self._count_recent_locked(now_ts, 900) / 900, 2)
            # 计算最近15分钟的平均QPS

            uptime_seconds = max(now_ts - self.started_at, 0.001)
            # 计算运行时长（秒），避免除零错误

            avg_qps = round(self.total_requests / uptime_seconds, 2)
            # 计算从启动到现在的平均QPS（总请求数/运行时长）

            success_rate = round((self.success_requests / self.total_requests) * 100,
                                 2) if self.total_requests else 100.0
            # 计算成功率（百分比），如果无请求则视为100%

            recent = list(self.timeline)[-60:]
            # 获取最近60条详细记录（用于图表展示）

        return {
            # 返回所有指标数据的字典
            "current_qps": current_qps,
            # 当前QPS
            "qps_1min": qps_1min,
            # 1分钟平均QPS
            "qps_5min": qps_5min,
            # 5分钟平均QPS
            "qps_15min": qps_15min,
            # 15分钟平均QPS
            "total_requests": self.total_requests,
            # 总请求数
            "success_requests": self.success_requests,
            # 成功请求数
            "error_requests": self.error_requests,
            # 失败请求数
            "success_rate": success_rate,
            # 成功率（%）
            "avg_qps": avg_qps,
            # 平均QPS（从启动至今）
            "uptime_seconds": round(uptime_seconds, 2),
            # 运行时长（秒）
            "recent": recent,
            # 最近60条请求详情
        }


def percentile(values, ratio):
    # 定义函数：计算一组数值的百分位数

    """
    计算一组数值的百分位数（支持线性插值）

    参数:
        values: 数值列表
        ratio: 百分位（0-1之间），例如0.5表示中位数，0.99表示99分位

    返回:
        float: 计算出的百分位数，四舍五入保留2位小数
    """
    if not values:
        # 如果列表为空
        return 0.0
        # 返回0

    sorted_values = sorted(values)
    # 对数值进行升序排序

    if len(sorted_values) == 1:
        # 如果只有一个元素
        return round(float(sorted_values[0]), 2)
        # 直接返回该元素（保留2位小数）

    position = ratio * (len(sorted_values) - 1)
    # 计算百分位在排序后列表中的精确位置
    # 使用线性插值算法：位置 = 比例 * (元素个数 - 1)
    lower = math.floor(position)
    # 获取下界索引（向下取整）
    upper = math.ceil(position)
    # 获取上界索引（向上取整）

    if lower == upper:
        # 如果位置刚好是整数
        return round(float(sorted_values[lower]), 2)
        # 直接返回该位置的数值

    lower_value = sorted_values[lower]
    # 获取下界数值
    upper_value = sorted_values[upper]
    # 获取上界数值
    interpolated = lower_value + (upper_value - lower_value) * (position - lower)
    # 在两个值之间进行线性插值计算

    return round(float(interpolated), 2)
    # 返回插值结果，保留2位小数


def choose_port(preferred_port, max_tries=20):
    # 定义函数：自动选择一个可用的端口号

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
    for port in range(preferred_port, preferred_port + max_tries + 1):
        # 从首选端口开始，依次向上尝试最多max_tries个端口
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            # 创建一个TCP socket对象（使用with自动关闭）
            sock.settimeout(0.3)
            # 设置连接超时时间为0.3秒
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                # connect_ex()尝试连接指定地址和端口
                # 返回0表示连接成功（说明端口已被占用）
                continue
                # 端口被占用，继续尝试下一个端口
            return port
            # 连接失败（connect_ex返回非0），说明端口可用，返回此端口号

    raise RuntimeError(f"未找到可用端口，起始端口: {preferred_port}")
    # 尝试完所有端口后仍未找到可用端口，抛出运行时异常
