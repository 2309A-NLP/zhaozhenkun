# -*- coding: utf-8 -*-
# 工单编号：人工智能NLP-Agent数字人项目-17-教育Agent任务工单-教学场景功能分析及智能备课
# 模块：性能监控优化 - API响应时间监控、限流控制、日志优化
# 创建时间：2025年6月
# 作者：Agent智能备课系统开发组

import time  # 时间函数
import functools  # 函数工具（wraps）
import logging  # 日志系统
import os  # 文件系统
from typing import Dict, List, Optional, Callable  # 类型提示
from datetime import datetime  # 时间处理
from collections import defaultdict, deque  # 默认字典和双端队列
from contextlib import contextmanager  # 上下文管理器
import threading  # 线程支持


# ==================== 日志优化配置 ====================
def setup_logging(log_level: str = "INFO", log_dir: str = "./logs") -> logging.Logger:
    """配置日志系统 - 设置格式化日志输出，同时写入文件和控制台"""
    os.makedirs(log_dir, exist_ok=True)  # 确保日志目录存在
    logger = logging.getLogger("edu_agent_lesson_prep")  # 创建日志器
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))  # 设置日志级别
    # 避免重复添加Handler
    if logger.handlers:  # 已有处理器
        return logger  # 直接返回
    # 日志格式：时间 - 名称 - 级别 - 文件:行号 - 消息
    formatter = logging.Formatter(  # 创建格式化器
        "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",  # 时间格式
    )
    # 文件处理器
    file_handler = logging.FileHandler(  # 创建文件处理器
        os.path.join(log_dir, f"app_{datetime.now().strftime('%Y%m%d')}.log"),  # 按日期分文件
        encoding="utf-8",  # UTF-8编码
    )
    file_handler.setFormatter(formatter)  # 设置格式
    file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别
    logger.addHandler(file_handler)  # 添加处理器
    # 控制台处理器
    console_handler = logging.StreamHandler()  # 创建控制台处理器
    console_handler.setFormatter(formatter)  # 设置格式
    console_handler.setLevel(logging.INFO)  # 控制台记录INFO及以上
    logger.addHandler(console_handler)  # 添加处理器
    return logger  # 返回日志器


# 获取全局日志器
logger = setup_logging()  # 初始化日志系统


# ==================== 性能计时上下文管理器 ====================
@contextmanager
def performance_timer(operation_name: str, log_result: bool = True):
    """性能计时器 - 上下文管理器方式记录操作耗时"""
    start_time = time.perf_counter()  # 高精度开始计时
    try:
        yield  # 执行被包装的代码块
    finally:
        elapsed_ms = (time.perf_counter() - start_time) * 1000  # 计算耗时（毫秒）
        if log_result:  # 需要记录日志
            logger.info(f"性能计时 [{operation_name}]: {elapsed_ms:.2f}ms")  # 写入日志


def timed(operation_name: Optional[str] = None):
    """性能计时装饰器 - 自动记录函数执行时间"""
    def decorator(func: Callable) -> Callable:  # 装饰器函数
        op_name = operation_name or func.__name__  # 操作名（默认用函数名）
        @functools.wraps(func)  # 保持原函数元信息
        def wrapper(*args, **kwargs):  # 包装函数
            start = time.perf_counter()  # 开始计时
            result = func(*args, **kwargs)  # 执行原函数
            elapsed = (time.perf_counter() - start) * 1000  # 计算耗时
            logger.info(f"⏱ [{op_name}] 耗时: {elapsed:.2f}ms")  # 记录耗时
            return result  # 返回结果
        @functools.wraps(func)  # 保持原函数元信息
        async def async_wrapper(*args, **kwargs):  # 异步函数包装
            start = time.perf_counter()  # 开始计时
            result = await func(*args, **kwargs)  # 执行异步函数
            elapsed = (time.perf_counter() - start) * 1000  # 计算耗时
            logger.info(f"⏱ [{op_name}] 耗时: {elapsed:.2f}ms")  # 记录耗时
            return result  # 返回结果
        # 根据原函数是否为协程选择包装器
        import asyncio  # asyncio模块
        if asyncio.iscoroutinefunction(func):  # 是异步函数
            return async_wrapper  # 返回异步包装器
        return wrapper  # 返回同步包装器
    return decorator  # 返回装饰器


# ==================== 请求速率限制器 ====================
class RateLimiter:
    """速率限制器 - 基于滑动窗口的API请求频率控制"""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        """初始化限流器 - 设置在时间窗口内的最大请求数"""
        self.max_requests = max_requests  # 窗口内最大请求数
        self.window_seconds = window_seconds  # 时间窗口（秒）
        self._requests: Dict[str, deque] = defaultdict(  # 每个用户的请求时间戳队列
            lambda: deque(maxlen=max_requests * 2))  # 双端队列，容量为2倍最大请求
        self._lock = threading.RLock()  # 线程锁

    def is_allowed(self, user_id: str) -> bool:
        """检查是否允许请求 - 判断当前用户是否超出速率限制"""
        with self._lock:  # 线程安全
            now = time.time()  # 当前时间戳
            window_start = now - self.window_seconds  # 窗口起始时间
            user_requests = self._requests[user_id]  # 获取用户的请求记录
            # 清理窗口外的过期记录
            while user_requests and user_requests[0] < window_start:  # 队列头在窗口外
                user_requests.popleft()  # 移出过期记录
            # 判断是否超限
            if len(user_requests) >= self.max_requests:  # 请求数已达上限
                return False  # 拒绝请求
            user_requests.append(now)  # 记录本次请求时间
            return True  # 允许请求

    def get_remaining(self, user_id: str) -> int:
        """获取剩余可用请求数 - 返回当前窗口内还可发送的请求数"""
        with self._lock:  # 线程安全
            now = time.time()  # 当前时间
            window_start = now - self.window_seconds  # 窗口起点
            user_requests = self._requests[user_id]  # 获取请求记录
            # 清理过期记录
            while user_requests and user_requests[0] < window_start:  # 移出过期
                user_requests.popleft()  # 出队
            current_count = len(user_requests)  # 当前请求数
            return max(0, self.max_requests - current_count)  # 剩余可用数

    def reset(self, user_id: str) -> None:
        """重置用户限流计数 - 清空指定用户的请求记录"""
        with self._lock:  # 线程安全
            self._requests[user_id].clear()  # 清空请求队列


# ==================== API调用性能追踪 ====================
class APIMetricsTracker:
    """API调用指标追踪器 - 收集和分析API调用性能数据"""

    def __init__(self):
        """初始化追踪器 - 创建指标存储结构"""
        self._metrics: Dict[str, List[float]] = defaultdict(list)  # 操作耗时列表
        self._error_counts: Dict[str, int] = defaultdict(int)  # 错误计数
        self._call_counts: Dict[str, int] = defaultdict(int)  # 调用计数
        self._lock = threading.RLock()  # 线程锁

    def record_call(self, operation: str, elapsed_ms: float,
                    is_error: bool = False) -> None:
        """记录API调用 - 存储调用耗时和错误信息"""
        with self._lock:  # 线程安全
            self._metrics[operation].append(elapsed_ms)  # 记录耗时
            self._call_counts[operation] += 1  # 调用计数+1
            if is_error:  # 有错误
                self._error_counts[operation] += 1  # 错误计数+1
            # 限制存储指标数量，只保留最近1000条
            if len(self._metrics[operation]) > 1000:  # 超过限制
                self._metrics[operation] = self._metrics[operation][-1000:]  # 保留最新

    def get_operation_stats(self, operation: str) -> Dict:
        """获取操作统计 - 计算平均耗时、P95等指标"""
        with self._lock:  # 线程安全
            times = self._metrics.get(operation, [])  # 获取耗时列表
            if not times:  # 无数据
                return {"operation": operation, "call_count": 0}  # 空统计
            sorted_times = sorted(times)  # 排序耗时
            n = len(sorted_times)  # 样本数
            return {  # 统计指标
                "operation": operation,  # 操作名
                "call_count": self._call_counts.get(operation, 0),  # 总调用数
                "error_count": self._error_counts.get(operation, 0),  # 错误数
                "error_rate": round(self._error_counts.get(operation, 0) / max(self._call_counts.get(operation, 1), 1), 4),  # 错误率
                "avg_ms": round(sum(times) / n, 2),  # 平均耗时
                "min_ms": round(sorted_times[0], 2),  # 最小耗时
                "max_ms": round(sorted_times[-1], 2),  # 最大耗时
                "p50_ms": round(sorted_times[n // 2], 2),  # P50中位数
                "p95_ms": round(sorted_times[int(n * 0.95)], 2) if n >= 20 else round(sorted_times[-1], 2),  # P95
                "p99_ms": round(sorted_times[int(n * 0.99)], 2) if n >= 100 else round(sorted_times[-1], 2),  # P99
            }

    def get_all_stats(self) -> List[Dict]:
        """获取所有操作统计 - 返回所有追踪操作的性能指标"""
        stats_list = []  # 统计列表
        for operation in self._metrics.keys():  # 遍历所有操作
            stats = self.get_operation_stats(operation)  # 获取统计数据
            stats_list.append(stats)  # 添加到列表
        # 按调用次数降序排列
        stats_list.sort(key=lambda x: x.get("call_count", 0), reverse=True)  # 按调用数排序
        return stats_list  # 返回排序列表

    def generate_report(self) -> str:
        """生成性能报告 - 格式化的性能统计文本报告"""
        stats = self.get_all_stats()  # 获取所有统计
        lines = ["=" * 70, "  API性能统计报告",
                 f"  生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                 "=" * 70, ""]
        for s in stats:  # 遍历每个操作
            lines.append(f"  [{s['operation']}]")  # 操作名
            lines.append(f"    调用: {s['call_count']}次 | 错误率: {s['error_rate']*100:.1f}%")  # 调用统计
            lines.append(f"    耗时: 平均{s['avg_ms']}ms | P50={s['p50_ms']}ms | P95={s['p95_ms']}ms")  # 耗时统计
            lines.append("")  # 空行
        return "\n".join(lines)  # 拼接报告

    def print_report(self) -> None:
        """打印性能报告到控制台"""
        print(self.generate_report())  # 输出报告


# ==================== 全局性能工具实例 ====================
rate_limiter = RateLimiter(max_requests=120, window_seconds=60)  # 每分钟120次请求
metrics_tracker = APIMetricsTracker()  # API性能追踪器实例
