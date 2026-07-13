# -*- coding: utf-8 -*-
# 工单编号：人工智能NLP-Agent数字人项目-17-教育Agent任务工单-教学场景功能分析及智能备课
# 模块：缓存服务 - 多级缓存优化，提升系统响应速度
# 创建时间：2025年6月
# 作者：Agent智能备课系统开发组

import hashlib  # 哈希计算（生成缓存键）
import json  # JSON序列化
import time  # 时间函数
import threading  # 线程安全锁
from typing import Optional, Any, Dict, Callable  # 类型提示
from functools import wraps  # 装饰器工具
from collections import OrderedDict  # 有序字典（LRU实现）


class MemoryCache:
    """内存缓存类 - 基于LRU算法的线程安全内存缓存"""

    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        """初始化缓存 - 设置最大容量和默认过期时间"""
        self._cache: OrderedDict[str, Dict] = OrderedDict()  # 有序字典存储缓存项
        self._max_size = max_size  # 最大缓存条目数
        self._default_ttl = default_ttl  # 默认生存时间（秒）
        self._lock = threading.RLock()  # 可重入锁保证线程安全
        self._hits = 0  # 缓存命中计数
        self._misses = 0  # 缓存未命中计数

    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        """生成缓存键 - 将参数序列化后哈希生成唯一键"""
        raw = f"{prefix}:{json.dumps(args, sort_keys=True)}:{json.dumps(kwargs, sort_keys=True)}"  # 拼接参数字符串
        hash_key = hashlib.md5(raw.encode()).hexdigest()  # MD5哈希
        return f"{prefix}:{hash_key}"  # 返回带前缀的缓存键

    def get(self, key: str) -> Optional[Any]:
        """获取缓存值 - 检查过期时间并返回缓存数据"""
        with self._lock:  # 获取线程锁
            if key not in self._cache:  # 缓存键不存在
                self._misses += 1  # 未命中计数+1
                return None  # 返回None
            item = self._cache[key]  # 获取缓存项
            if item["expires_at"] < time.time():  # 已过期
                del self._cache[key]  # 删除过期项
                self._misses += 1  # 未命中计数+1
                return None  # 返回None
            # LRU策略：将访问的项移到末尾（最新使用）
            self._cache.move_to_end(key)  # 移到有序字典末尾
            self._hits += 1  # 命中计数+1
            return item["value"]  # 返回缓存值

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """设置缓存值 - 带TTL过期时间"""
        with self._lock:  # 获取线程锁
            if len(self._cache) >= self._max_size:  # 缓存已满
                # LRU淘汰：删除最旧的条目（有序字典第一个）
                self._cache.popitem(last=False)  # FIFO淘汰最旧项
            ttl_seconds = ttl if ttl is not None else self._default_ttl  # 使用指定TTL或默认值
            self._cache[key] = {  # 存储缓存项
                "value": value,  # 缓存值
                "expires_at": time.time() + ttl_seconds,  # 过期时间戳
                "created_at": time.time(),  # 创建时间
            }
            self._cache.move_to_end(key)  # 标记为最新使用

    def delete(self, key: str) -> bool:
        """删除缓存项 - 移除指定键的缓存"""
        with self._lock:  # 获取线程锁
            if key in self._cache:  # 键存在
                del self._cache[key]  # 删除缓存
                return True  # 删除成功
            return False  # 键不存在

    def clear(self, prefix: Optional[str] = None) -> int:
        """清空缓存 - 可选按前缀清理"""
        with self._lock:  # 获取线程锁
            if prefix is None:  # 清空全部
                count = len(self._cache)  # 记录数量
                self._cache.clear()  # 清空
                return count  # 返回清除数量
            # 按前缀删除匹配的键
            keys_to_delete = [k for k in self._cache if k.startswith(prefix)]  # 筛选匹配键
            for k in keys_to_delete:  # 遍历删除
                del self._cache[k]  # 删除缓存项
            return len(keys_to_delete)  # 返回删除数量

    def get_stats(self) -> Dict:
        """获取缓存统计信息 - 返回命中率和使用情况"""
        with self._lock:  # 获取线程锁
            total_requests = self._hits + self._misses  # 总请求数
            hit_rate = self._hits / total_requests if total_requests > 0 else 0  # 计算命中率
            return {  # 统计信息字典
                "size": len(self._cache), "max_size": self._max_size,  # 缓存大小
                "hits": self._hits, "misses": self._misses,  # 命中/未命中
                "hit_rate": round(hit_rate, 4),  # 命中率（保留4位小数）
                "total_requests": total_requests,  # 总请求数
            }


# 全局缓存实例
memory_cache = MemoryCache(max_size=2000, default_ttl=1800)  # 2000条/30分钟过期


def cached(prefix: str, ttl: Optional[int] = None):
    """缓存装饰器 - 为函数结果添加自动缓存功能"""
    def decorator(func: Callable) -> Callable:  # 外层装饰器
        @wraps(func)  # 保持原函数元信息
        def wrapper(*args, **kwargs):  # 包装函数
            cache_key = memory_cache._make_key(prefix, *args, **kwargs)  # 生成缓存键
            cached_result = memory_cache.get(cache_key)  # 查询缓存
            if cached_result is not None:  # 缓存命中
                print(f"缓存命中: {prefix}")  # 命中日志
                return cached_result  # 返回缓存结果
            # 缓存未命中，调用原函数
            result = func(*args, **kwargs)  # 执行原函数
            memory_cache.set(cache_key, result, ttl=ttl)  # 存入缓存
            print(f"缓存写入: {prefix}")  # 写入日志
            return result  # 返回计算结果
        return wrapper  # 返回包装函数
    return decorator  # 返回装饰器


class RedisCacheService:
    """Redis缓存服务 - 可选的分布式缓存实现"""

    def __init__(self, redis_url: Optional[str] = None):
        """初始化Redis连接 - 使用可选配置连接"""
        self._redis = None  # Redis客户端（延迟初始化）
        self._redis_url = redis_url  # Redis连接URL
        self._available = False  # Redis是否可用标志

    def _ensure_connection(self) -> bool:
        """确保Redis连接 - 懒加载连接并检测可用性"""
        if self._available:  # 已经确认可用
            return True  # 直接返回
        if not self._redis_url:  # 未配置Redis URL
            return False  # 不可用
        try:
            import redis  # 导入redis库
            self._redis = redis.from_url(self._redis_url, socket_connect_timeout=2)  # 建立连接
            self._redis.ping()  # 测试连接
            self._available = True  # 标记可用
            print("Redis缓存服务连接成功")  # 连接成功日志
            return True  # 可用
        except Exception as e:  # 连接异常
            print(f"Redis连接失败，将使用内存缓存: {e}")  # 降级日志
            return False  # 不可用

    def get(self, key: str) -> Optional[str]:
        """Redis获取缓存 - 读取字符串值"""
        if not self._ensure_connection():  # 确保连接
            return None  # 不可用
        try:
            return self._redis.get(key)  # 获取Redis值
        except Exception:  # 读取异常
            return None  # 返回None

    def set(self, key: str, value: str, ttl: int = 3600) -> bool:
        """Redis设置缓存 - 写入带过期时间的字符串"""
        if not self._ensure_connection():  # 确保连接
            return False  # 不可用
        try:
            self._redis.setex(key, ttl, value)  # 设置带TTL的值
            return True  # 成功
        except Exception:  # 写入异常
            return False  # 失败


# 全局缓存服务实例
redis_cache = RedisCacheService()  # 创建Redis缓存实例（按需启用）
