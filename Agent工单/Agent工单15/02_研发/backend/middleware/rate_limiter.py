"""
================================================================================
文件名:   middleware/rate_limiter.py
功能:     简易速率限制中间件（内存实现，无需外部依赖）
          —— 防止 API 滥用，保护后端 LLM 调用费用
所属项目: 医疗智能体-影像分析系统
用法:     在 main.py 中用 @app.middleware("http") 注册
================================================================================
"""
import time  # time.time() —— 时间戳
from collections import defaultdict  # defaultdict —— IP → 时间戳列表
from typing import Dict, List  # Dict, List —— 类型标注

# 速率限制窗口（秒）和最大请求数
_RATE_LIMIT_WINDOW = 60  # 每窗口
_RATE_LIMIT_MAX_REQUESTS = 30  # 每个 IP 最多请求

# IP → 请求时间戳列表的内存存储
_rate_limit_store: Dict[str, List[float]] = defaultdict(list)


def _check_rate_limit(client_ip: str) -> bool:
    """检查 IP 是否超出限制，清理过期记录后判断，返回 True=放行"""
    now = time.time()  # 当前时间戳
    window_start = now - _RATE_LIMIT_WINDOW  # 窗口起点
    # 只保留窗口内的记录
    _rate_limit_store[client_ip] = [
        ts for ts in _rate_limit_store[client_ip] if ts > window_start
    ]
    # 超出上限则拒绝
    if len(_rate_limit_store[client_ip]) >= _RATE_LIMIT_MAX_REQUESTS:
        return False
    # 记录本次请求时间
    _rate_limit_store[client_ip].append(now)
    return True


def _cleanup_rate_limit_store() -> int:
    """清理所有过期 IP 记录，防止内存泄漏，返回清理的 IP 数"""
    now = time.time()  # 当前时间
    window_start = now - _RATE_LIMIT_WINDOW  # 窗口
    expired_ips = []  # 待删除的 IP 列表
    for ip, timestamps in _rate_limit_store.items():
        # 过滤保留窗口内的记录
        fresh = [ts for ts in timestamps if ts > window_start]
        if fresh:
            _rate_limit_store[ip] = fresh  # 更新为有效记录
        else:
            expired_ips.append(ip)  # 该 IP 无有效记录
    for ip in expired_ips:
        del _rate_limit_store[ip]  # 删除过期 IP
    return len(expired_ips)  # 返回清理数
