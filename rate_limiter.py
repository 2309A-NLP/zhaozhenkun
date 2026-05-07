# -*- coding: utf-8 -*-
import time  # 导入时间模块，用于获取当前时间和计算时间差
import threading  # 导入线程模块，用于实现线程安全的锁机制
from collections import deque  # 导入双端队列模块，用于高效地存储和移除时间戳记录


class RateLimiter:
    """速率限制器 - 限制API调用频率"""  # 类的文档字符串，说明该类用于控制API调用频率

    def __init__(self, max_calls_per_minute: int = 30):
        """初始化速率限制器，设置每分钟最大调用次数"""
        self.max_calls = max_calls_per_minute  # 每分钟允许的最大调用次数，默认30次
        self.calls = deque()  # 双端队列，用于存储每次API调用的时间戳
        self.lock = threading.Lock()  # 线程锁，用于确保多线程环境下的数据安全

    def wait_if_needed(self) -> None:
        """检查当前调用频率，如果超过限制则等待直到可以继续调用"""
        with self.lock:  # 使用上下文管理器获取线程锁，保证操作原子性
            now = time.time()  # 获取当前时间戳（秒为单位）
            # 移除队列中超过60秒的旧时间戳（因为只关心最近1分钟内的调用）
            while self.calls and self.calls[0] < now - 60:  # 当队列不为空且最早的调用时间在60秒之前
                self.calls.popleft()  # 从队列左侧移除过期的时间戳
            # 检查当前1分钟内的调用次数是否已达到上限
            if len(self.calls) >= self.max_calls:  # 如果队列长度（即最近1分钟调用次数）已达到上限
                # 计算需要等待的时间：60秒减去从最早调用到现在的时间差
                wait = 60 - (now - self.calls[0])  # 计算还需等待的秒数
                if wait > 0:  # 确保等待时间为正数
                    time.sleep(wait)  # 阻塞当前线程，等待指定秒数
            # 将当前调用时间戳添加到队列右侧，记录本次调用
            self.calls.append(time.time())  # 记录本次调用的时间戳