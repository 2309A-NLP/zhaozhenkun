#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
05_优化 — 性能优化配置与调优
==============================================================================
提供系统各级性能参数的集中管理：
- LLM 调用优化（缓存、超时、重试）
- 记忆检索优化（向量搜索调参、结果去重）
- 并发控制（请求限流、连接池）
- 效果评估指标
==============================================================================
"""

import os  # 环境变量
import time  # 时间相关，用于超时控制
from typing import Dict, Any, List, Optional  # 类型注解
from functools import lru_cache  # LRU 缓存装饰器，用于结果去重
from dataclasses import dataclass, field  # 数据类，简化配置对象定义


# ============================================================
# 一、LLM 调用优化配置
# ============================================================

@dataclass
class LLMConfig:
    """DeepSeek LLM 调用的优化参数。

    调整这些参数可以在速度、成本和准确性之间找到平衡。
    """
    # --- 模型选择 ---
    model: str = "deepseek-v4-flash"  # 使用 deepseek-v4-flash，速度快成本低

    # --- 重试策略 ---
    max_retries: int = 3  # API 调用失败时最大重试次数
    retry_delay: float = 1.0  # 初始重试延迟（秒），后续指数增长
    retry_backoff: float = 2.0  # 重试延迟的倍乘因子

    # --- 超时控制 ---
    request_timeout: int = 60  # 单次 API 请求超时秒数

    # --- 温度参数（按任务类型优化） ---
    extraction_temperature: float = 0.1  # 信息提取：低温度确保准确性和一致性
    summarization_temperature: float = 0.3  # 摘要生成：适中温度允许一定的措辞变化
    retrieval_temperature: float = 0.0  # 检索分析：零温度确保完全确定性

    # --- Token 限制 ---
    extraction_max_tokens: int = 1000  # 提取任务最大输出 token
    summarization_max_tokens: int = 500  # 摘要任务最大输出 token
    retrieval_max_tokens: int = 300  # 检索分析最大输出 token


# ============================================================
# 二、记忆检索优化配置
# ============================================================

@dataclass
class RetrievalConfig:
    """记忆检索优化参数：搜索精度、缓存、去重。"""
    default_top_k: int = 5  # 默认 Top-K
    max_top_k: int = 20  # 最大返回条数
    min_score_threshold: float = 0.3  # 最低相似度阈值
    enable_cache: bool = True  # 是否启用缓存
    cache_ttl: int = 300  # 缓存 TTL（秒）
    cache_max_size: int = 128  # 最大缓存条目
    dedup_threshold: float = 0.85  # 去重相似度阈值
    dedup_enabled: bool = True  # 是否启用来重


# ============================================================
# 三、并发控制配置
# ============================================================

@dataclass
class ConcurrencyConfig:
    """并发控制：限流、连接池、存储上限。"""
    rate_limit_enabled: bool = True  # 启用限流
    max_requests_per_second: int = 10  # 每秒最大请求
    burst_size: int = 20  # 突发允许量
    http_pool_connections: int = 20  # 连接池大小
    http_pool_maxsize: int = 50  # 最大连接
    max_memories_per_user: int = 1000  # 每用户最大记忆
    memory_cleanup_batch_size: int = 100  # 清理批次大小


# ============================================================
# 四、效果评估配置
# ============================================================

@dataclass
class EvaluationConfig:
    """效果评估：性能目标、维度权重、测试场景。"""
    target_retrieval_latency_ms: float = 200.0  # 检索延迟目标 <200ms
    target_write_latency_ms: float = 2000.0  # 写入延迟目标
    accuracy_weight: float = 0.4  # 准确性权重
    recall_weight: float = 0.3  # 召回率权重
    latency_weight: float = 0.2  # 延迟权重
    consistency_weight: float = 0.1  # 一致性权重
    test_scenarios: List[str] = field(default_factory=lambda: [
        "medical_revisit", "tourism_personalization", "education_knowledge_tracking",
    ])


# ============================================================
# 五、系统级优化工具函数
# ============================================================

class PerformanceMonitor:
    """运行时性能监控器：追踪延迟、成功率、缓存命中率。"""

    def __init__(self):
        """初始化监控指标。"""
        self._latencies: List[float] = []  # 延迟列表(ms)
        self._total_requests: int = 0  # 总请求
        self._successful_requests: int = 0  # 成功数
        self._cache_hits: int = 0  # 缓存命中
        self._cache_misses: int = 0  # 缓存未命中
        self._start_time: float = time.time()  # 启动时间

    def record_request(self, latency_ms: float, success: bool = True,
                       cache_hit: bool = False):
        """记录一次请求的性能数据。"""
        self._total_requests += 1
        self._latencies.append(latency_ms)
        if success:
            self._successful_requests += 1
        if cache_hit:
            self._cache_hits += 1
        else:
            self._cache_misses += 1

    @property
    def avg_latency_ms(self) -> float:
        """平均延迟(ms)。"""
        return sum(self._latencies) / len(self._latencies) if self._latencies else 0.0

    @property
    def p95_latency_ms(self) -> float:
        """P95 延迟(ms)。"""
        if not self._latencies:
            return 0.0
        sorted_lat = sorted(self._latencies)
        idx = int(len(sorted_lat) * 0.95)
        return sorted_lat[min(idx, len(sorted_lat) - 1)]

    @property
    def success_rate(self) -> float:
        """请求成功率。"""
        return self._successful_requests / self._total_requests if self._total_requests else 1.0

    @property
    def cache_hit_rate(self) -> float:
        """缓存命中率。"""
        total = self._cache_hits + self._cache_misses
        return self._cache_hits / total if total else 0.0

    def get_report(self) -> Dict[str, Any]:
        """生成性能报告字典。"""
        uptime = time.time() - self._start_time
        return {
            "uptime_seconds": round(uptime, 1),
            "total_requests": self._total_requests,
            "success_rate": round(self.success_rate * 100, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "cache_hit_rate": round(self.cache_hit_rate * 100, 2),
            "latency_ok": self.avg_latency_ms < 200.0,  # 满足 <200ms 目标？
        }


# 简单的 LRU 缓存实现，用于记忆检索结果去重
@lru_cache(maxsize=128)
def deduplicate_memories(memories_tuple: tuple, threshold: float = 0.85) -> tuple:
    """对记忆列表去重，避免误删分数接近但内容不同的历史记录。

    Args:
        memories_tuple: 记忆元组（用于 LRU 缓存的可哈希输入）
        threshold: 兼容保留参数，当前实现优先按 id / 文本精确去重

    Returns:
        去重后的记忆元组
    """
    mems = list(memories_tuple)
    if len(mems) <= 1:
        return tuple(mems)

    seen_ids = set()
    seen_texts = set()
    deduped = []

    for mem in mems:
        memory_id = str(mem.get("id") or "").strip()
        memory_text = str(mem.get("memory") or mem.get("text") or "").strip()
        normalized_text = " ".join(memory_text.split())

        if memory_id and memory_id in seen_ids:
            continue
        if normalized_text and normalized_text in seen_texts:
            continue

        deduped.append(mem)
        if memory_id:
            seen_ids.add(memory_id)
        if normalized_text:
            seen_texts.add(normalized_text)

    return tuple(deduped)


# ============================================================
# 六、全局配置实例
# ============================================================
# 使用环境变量覆盖默认值，方便不同环境灵活配置

llm_config = LLMConfig(
    model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
    request_timeout=int(os.getenv("LLM_TIMEOUT", "60")),
)

retrieval_config = RetrievalConfig(
    default_top_k=int(os.getenv("RETRIEVAL_TOP_K", "5")),
    enable_cache=os.getenv("ENABLE_CACHE", "true").lower() == "true",
    cache_ttl=int(os.getenv("CACHE_TTL", "300")),
)

concurrency_config = ConcurrencyConfig(
    rate_limit_enabled=os.getenv("RATE_LIMIT", "true").lower() == "true",
    max_requests_per_second=int(os.getenv("MAX_RPS", "10")),
)

eval_config = EvaluationConfig()

# 全局性能监控器
monitor = PerformanceMonitor()


# ============================================================
# 模块自检
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("  性能优化配置概览")
    print("=" * 50)

    # LLM 配置
    print(f"\n[LLM 配置]")
    print(f"  模型: {llm_config.model}")
    print(f"  提取温度: {llm_config.extraction_temperature}")
    print(f"  摘要温度: {llm_config.summarization_temperature}")
    print(f"  超时: {llm_config.request_timeout}s")

    # 检索配置
    print(f"\n[检索配置]")
    print(f"  默认 Top-K: {retrieval_config.default_top_k}")
    print(f"  最低相似度: {retrieval_config.min_score_threshold}")
    print(f"  缓存: {'启用' if retrieval_config.enable_cache else '禁用'} (TTL={retrieval_config.cache_ttl}s)")

    # 并发配置
    print(f"\n[并发配置]")
    print(f"  限流: {'启用' if concurrency_config.rate_limit_enabled else '禁用'}")
    print(f"  最大 RPS: {concurrency_config.max_requests_per_second}")
    print(f"  每用户最大记忆: {concurrency_config.max_memories_per_user}")

    # 评估配置
    print(f"\n[评估目标]")
    print(f"  检索延迟目标: <{eval_config.target_retrieval_latency_ms}ms")
    print(f"  写入延迟目标: <{eval_config.target_write_latency_ms}ms")

    # 模拟监控报告
    print(f"\n[性能监控模拟]")
    # 模拟一些请求数据
    for lat in [50, 80, 120, 60, 200, 95, 150]:
        monitor.record_request(lat, success=True, cache_hit=(lat < 100))
    # 打印报告
    report = monitor.get_report()
    for key, value in report.items():
        print(f"  {key}: {value}")

    # 测试去重
    print(f"\n[去重测试]")
    test_mems = (
        {"id": "1", "score": 0.9, "memory": "用户喜欢海边"},
        {"id": "2", "score": 0.89, "memory": "用户喜欢海边度假"},  # 与#1 接近
        {"id": "3", "score": 0.5, "memory": "用户对海鲜过敏"},  # 不同
    )
    deduped = deduplicate_memories(test_mems)
    print(f"  输入: {len(test_mems)} 条 -> 输出: {len(deduped)} 条")
    print(f"\n配置加载完成。")
