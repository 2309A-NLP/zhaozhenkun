# -*- coding: utf-8 -*-
"""
ADSD 在线服务 - 负载均衡器模块
实现基于最小连接数算法的API端点负载均衡
主要功能：
1. 端点管理：管理多个API端点的配置和状态
2. 最小连接数调度：自动选择当前负载最小的端点
3. 统计追踪：记录每个端点的请求数、成功率、平均响应时间
4. 线程安全：使用锁机制保证并发安全
"""
# -*- coding: utf-8 -*-   # 指定文件编码为UTF-8，支持中文等字符
import threading           # 导入线程模块，用于实现线程安全的操作
from typing import List, Dict, Optional  # 导入类型提示相关类型
from dataclasses import dataclass        # 导入dataclass装饰器，用于简化类定义


@dataclass                 # 装饰器，自动为EndpointConfig类生成__init__等方法
class EndpointConfig:      # 定义端点配置类，存储单个API端点的配置和统计信息
    name: str              # 端点名称，用于唯一标识
    api_key: str           # API密钥，用于认证
    base_url: str          # 基础URL，API请求的地址
    model: str             # 模型名称，标识使用的AI模型
    weight: int = 1        # 权重，用于负载均衡（当前类未使用，预留）
    current_load: int = 0  # 当前负载，记录正在处理中的请求数
    total_requests: int = 0  # 总请求数，累计此端点收到的请求总数
    success_count: int = 0   # 成功次数，请求成功的数量
    fail_count: int = 0      # 失败次数，请求失败的数量
    avg_response_time: float = 0  # 平均响应时间(秒)，加权移动平均值


class WeightedRoundRobinBalancer:  # 定义加权轮询负载均衡器类（实际实现是最小负载算法）
    """加权轮询负载均衡器"""  # 类文档字符串，说明类的用途（注释与实际实现有差异）

    def __init__(self, endpoints: List[EndpointConfig]):  # 构造函数，接收端点配置列表
        self.lock = threading.Lock()  # 创建线程锁，保证多线程环境的线程安全
        self.endpoints = endpoints    # 存储端点配置列表
        self.index = 0                # 轮询索引（当前未使用，预留）

    def next(self) -> Optional[EndpointConfig]:  # 选择下一个可用的端点
        with self.lock:                           # 获取线程锁，保证操作的原子性
            if not self.endpoints:                # 如果没有可用端点
                return None                       # 返回None
            # 选择当前负载最小的端点（最小连接数算法，非加权轮询）
            selected = min(self.endpoints, key=lambda x: x.current_load)
            selected.current_load += 1  # 将选中端点的当前负载加1
            return selected              # 返回选中的端点配置

    def release(self, endpoint_name: str):  # 释放端点，减少其当前负载
        with self.lock:                       # 获取线程锁
            for ep in self.endpoints:         # 遍历所有端点
                if ep.name == endpoint_name:  # 找到匹配名称的端点
                    # 当前负载减1，最小值不低于0
                    ep.current_load = max(0, ep.current_load - 1)
                    break                     # 找到后立即退出循环

    def record_result(self, endpoint_name: str, success: bool, response_time: float):  # 记录请求结果并更新统计
        with self.lock:                       # 获取线程锁
            for ep in self.endpoints:         # 遍历所有端点
                if ep.name == endpoint_name:  # 找到匹配名称的端点
                    ep.total_requests += 1    # 总请求数加1
                    if success:               # 如果请求成功
                        ep.success_count += 1 # 成功计数加1
                    else:                     # 如果请求失败
                        ep.fail_count += 1    # 失败计数加1
                    # 更新平均响应时间（加权移动平均公式）
                    ep.avg_response_time = (ep.avg_response_time *
                                            (ep.total_requests - 1) + response_time) / ep.total_requests
                    break                     # 更新完成后退出循环

    def get_stats(self) -> List[Dict]:  # 获取所有端点的统计信息
        with self.lock:                  # 获取线程锁
            # 列表推导式，为每个端点生成统计字典
            return [{
                "name": ep.name,            # 端点名称
                "model": ep.model,          # 模型名称
                "weight": ep.weight,        # 权重值
                "current_load": ep.current_load,  # 当前负载（进行中的请求数）
                "total_requests": ep.total_requests,  # 总请求数
                "success_rate": round(ep.success_count / max(1, ep.total_requests) * 100, 2),  # 成功率(%)
                "avg_response_time": round(ep.avg_response_time, 2),  # 平均响应时间（保留2位小数）
                "status": "active"          # 状态（当前固定为active）
            } for ep in self.endpoints]     # 遍历每个端点
