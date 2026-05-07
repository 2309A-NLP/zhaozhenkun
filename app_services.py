# -*- coding: utf-8 -*-
import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# 从配置文件导入各种配置参数
from config import (
    BGE_M3_PATH,  # BGE M3模型路径
    BGE_RERANKER_PATH,  # BGE重排序模型路径
    DEVICE,  # 运行设备（cuda/cpu）
    KIMI_API_KEY,  # Kimi API密钥
    KIMI_BASE_URL,  # Kimi API基础URL
    KIMI_MODEL,  # Kimi模型名称
    MILVUS_HOSTS,  # Milvus主机地址
    MILVUS_PORT,  # Milvus端口
    MYSQL_DATABASE,  # MySQL数据库名
    MYSQL_ENABLED,  # MySQL是否启用
    MYSQL_HOST,  # MySQL主机地址
    MYSQL_PASSWORD,  # MySQL密码
    MYSQL_PORT,  # MySQL端口
    MYSQL_USER,  # MySQL用户名
    REDIS_HOST,  # Redis主机地址
    REDIS_PASSWORD,  # Redis密码
    REDIS_PORT,  # Redis端口
    USER_DATA_FILE,  # 用户数据文件路径
)

# 尝试导入BGE管理器相关模块
try:
    from bge_manager import BGMManager, load_bge_models
except Exception:
    BGMManager = None  # 导入失败时设为None
    load_bge_models = None  # 导入失败时设为None

# 尝试导入混合检索器
try:
    from hybrid_retriever import HybridRetriever
except Exception:
    HybridRetriever = None  # 导入失败时设为None

# 尝试导入LLM客户端
try:
    from llm_client import LLMClient
except Exception:
    LLMClient = None  # 导入失败时设为None

# 导入应用所需的其他模块
from app_monitor import percentile  # 百分位数计算函数
from app_text import DEFAULT_QUERY, SANITIZED_AVATARS, load_local_documents, repair_text  # 文本处理相关
from milvus_manager import MilvusManager  # Milvus向量数据库管理器
from mysql_manager import MySQLManager  # MySQL数据库管理器
from output_optimizer import LLMOutputOptimizer  # LLM输出优化器
from redis_manager import RedisManager  # Redis缓存管理器
from short_term_memory import ShortTermMemory  # 短期记忆管理
from user_manager import UserManager  # 用户管理器
from utils import generate_doc_id  # 文档ID生成工具

logger = logging.getLogger(__name__)  # 获取当前模块的日志记录器

# 全局变量：RAG系统实例
rag_system = None
# 全局变量：系统是否就绪
system_ready = False
# 全局变量：系统错误信息
system_error = ""


class SimpleRAGSystem:
    """简单的RAG（检索增强生成）系统核心类"""

    def __init__(self, runtime_config):
        """初始化RAG系统

        参数:
            runtime_config: 运行时配置字典
        """
        self.device = DEVICE  # 运行设备
        self.vector_dim = 1024  # 向量维度
        self.memory_lock = threading.RLock()  # 内存操作的线程锁
        self.short_term_memories = {}  # 短期记忆存储字典
        self.documents = load_local_documents()  # 加载本地文档
        self.bge_loaded = False  # BGE模型是否加载成功

        # 初始化MySQL管理器
        self.mysql_manager = MySQLManager(
            {
                "host": runtime_config.get("mysql_host", MYSQL_HOST),
                "port": runtime_config.get("mysql_port", MYSQL_PORT),
                "user": runtime_config.get("mysql_user", MYSQL_USER),
                "password": runtime_config.get("mysql_password", MYSQL_PASSWORD),
                "database": runtime_config.get("mysql_database", MYSQL_DATABASE),
                "enabled": runtime_config.get("mysql_enabled", MYSQL_ENABLED),
            }
        )

        # 初始化Redis客户端
        self.redis_client = RedisManager(
            host=runtime_config.get("redis_host", REDIS_HOST),
            port=runtime_config.get("redis_port", REDIS_PORT),
            password=runtime_config.get("redis_password", REDIS_PASSWORD),
        )
        try:
            self.redis_client.connect()  # 尝试连接Redis
        except Exception as exc:
            logger.warning("Redis 初始化失败，将继续以内存模式运行: %s", exc)

        # 初始化用户管理器
        self.user_manager = UserManager(
            user_data_file=runtime_config.get("user_data_file", USER_DATA_FILE),
            mysql_manager=self.mysql_manager,
        )

        # 初始化Milvus向量数据库管理器
        self.milvus_manager = MilvusManager(
            hosts=runtime_config.get("milvus_hosts", MILVUS_HOSTS),
            port=runtime_config.get("milvus_port", MILVUS_PORT),
        )
        try:
            self.milvus_manager.connect()  # 尝试连接Milvus
        except Exception as exc:
            logger.warning("Milvus 初始化失败，将继续使用本地检索链路: %s", exc)

        # 加载BGE模型（如果存在）
        if load_bge_models is not None and Path(BGE_M3_PATH).exists() and Path(BGE_RERANKER_PATH).exists():
            try:
                load_bge_models(
                    {
                        "bge_m3_path": BGE_M3_PATH,
                        "bge_reranker_path": BGE_RERANKER_PATH,
                    },
                    self.device,
                )
                self.bge_loaded = True  # 标记模型加载成功
            except Exception as exc:
                logger.warning("BGE 模型加载失败，将自动降级: %s", exc)

        # 初始化BGE管理器
        self.bge_manager = BGMManager(self.device, self.vector_dim) if BGMManager is not None else None

        # 初始化混合检索器
        self.hybrid_retriever = HybridRetriever() if HybridRetriever is not None else None
        if self.hybrid_retriever is not None and self.documents:
            try:
                self.hybrid_retriever.build_index(self.documents)  # 构建检索索引
            except Exception as exc:
                logger.warning("混合检索索引构建失败: %s", exc)
                self.hybrid_retriever = None  # 失败时设为None

        # 初始化输出优化器和LLM客户端
        self.output_optimizer = LLMOutputOptimizer()
        self.llm_client = None
        self.use_mock = True  # 默认使用模拟模式
        if LLMClient is not None:
            try:
                self.llm_client = LLMClient()
                # 初始化LLM（Kimi）
                self.llm_client.init_llm(KIMI_API_KEY, KIMI_BASE_URL, KIMI_MODEL, [], [], [])
                self.use_mock = self.llm_client.use_mock  # 更新模拟模式状态
            except Exception as exc:
                logger.warning("LLM 初始化失败，切换为 mock 模式: %s", exc)
                self.use_mock = True  # 失败时使用模拟模式

    def _memory_key(self, session_id):
        """生成Redis中存储短期记忆的键名"""
        return f"rag:short_memory:{session_id}"

    def _get_short_memory(self, session_id):
        """获取指定会话的短期记忆对象

        参数:
            session_id: 会话ID

        返回:
            ShortTermMemory: 短期记忆对象
        """
        with self.memory_lock:  # 加锁保证线程安全
            memory = self.short_term_memories.get(session_id)
            if memory is None:  # 如果记忆中不存在该会话
                memory = ShortTermMemory(max_turns=12)  # 创建新的短期记忆，最多保存12轮对话
                self.short_term_memories[session_id] = memory
                # 如果Redis可用，从Redis加载历史记忆
                if getattr(self.redis_client, "enabled", False):
                    raw = self.redis_client.get(self._memory_key(session_id))
                    if raw:
                        try:
                            # 反序列化并恢复记忆
                            for item in json.loads(raw):
                                memory.add(item.get("role", "user"), item.get("content", ""), item.get("metadata", {}))
                        except Exception:
                            pass  # 恢复失败时忽略
            return memory

    def _persist_short_memory(self, session_id):
        """将短期记忆持久化到Redis

        参数:
            session_id: 会话ID
        """
        if not getattr(self.redis_client, "enabled", False):
            return  # Redis未启用，直接返回
        memory = self.short_term_memories.get(session_id)
        if not memory:
            return  # 没有记忆，直接返回
        payload = json.dumps(memory.conversation, ensure_ascii=False)  # 序列化对话记录
        self.redis_client.set(self._memory_key(session_id), payload, expire=24 * 3600)  # 存储到Redis，过期时间24小时

    def clear_short_memory(self, session_id):
        """清除指定会话的短期记忆

        参数:
            session_id: 会话ID
        """
        with self.memory_lock:
            self.short_term_memories.pop(session_id, None)  # 从内存中移除
        if getattr(self.redis_client, "enabled", False):
            self.redis_client.delete(self._memory_key(session_id))  # 从Redis中删除

    def _serialize_results(self, results, limit=5):
        """序列化检索结果，提取关键字段并限制数量

        参数:
            results: 检索结果列表
            limit: 最大返回数量

        返回:
            list: 序列化后的结果列表
        """
        serialized = []
        for item in results[:limit]:  # 只处理前limit个结果
            serialized.append(
                {
                    "question": repair_text(item.get("question", "")),  # 问题
                    "answer": repair_text(item.get("answer", "")),  # 答案
                    "source": repair_text(item.get("source", "")),  # 来源
                    "score": round(float(item.get("score", 0.0)), 4),  # 综合得分
                    "fusion_score": round(float(item.get("fusion_score", 0.0)), 4),  # 融合得分
                    "rerank_score": round(float(item.get("rerank_score", 0.0)), 4),  # 重排序得分
                    "vector_score": round(float(item.get("vector_score", 0.0)), 4),  # 向量得分
                    "tfidf_score": round(float(item.get("tfidf_score", 0.0)), 4),  # TF-IDF得分
                    "bm25_score": round(float(item.get("bm25_score", 0.0)), 4),  # BM25得分
                    "retrieval_method": item.get("retrieval_method", ""),  # 检索方法
                }
            )
        return serialized

    def _fallback_keyword_search(self, query, top_k):
        """降级的关键词搜索（当混合检索不可用时）

        参数:
            query: 查询文本
            top_k: 返回结果数量

        返回:
            list: 检索结果列表
        """
        query = query.strip()
        if not query or not self.documents:
            return []  # 无效查询或无文档时返回空列表
        query_chars = set(query)  # 获取查询中的字符集合
        scored = []
        for doc in self.documents:  # 遍历所有文档
            text = f"{doc.get('question', '')} {doc.get('answer', '')}"  # 拼接文档文本
            overlap = len(query_chars.intersection(set(text)))  # 计算字符重合度
            if overlap <= 0:
                continue  # 无重合时跳过
            scored.append(
                {
                    **doc,  # 原始文档字段
                    "score": float(overlap),  # 重合度作为得分
                    "retrieval_method": "keyword",  # 标记为关键词检索
                }
            )
        scored.sort(key=lambda item: item.get("score", 0), reverse=True)  # 按得分降序排序
        return scored[:top_k]  # 返回前top_k个结果

    def search_knowledge_debug(self, query, top_k=5):
        """知识库检索调试方法，返回详细的检索过程和结果

        参数:
            query: 查询文本
            top_k: 返回结果数量

        返回:
            dict: 包含检索结果和详细调试信息的字典
        """
        overall_start = time.perf_counter()  # 记录开始时间
        bm25_results = []  # BM25检索结果
        tfidf_results = []  # TF-IDF检索结果
        vector_results = []  # 向量检索结果
        fused_results = []  # 融合结果
        reranked_results = []  # 重排序结果
        timings = {}  # 各阶段耗时
        top_k = max(1, int(top_k))  # 确保top_k至少为1

        if not query.strip():  # 查询为空时返回空结果
            return {
                "query": query,
                "results": [],
                "recall": {},
                "timings": {"total_ms": 0.0},
                "modes": [],
            }

        # 1. 词法检索阶段（BM25 + TF-IDF）
        stage_start = time.perf_counter()
        if self.hybrid_retriever is not None:
            try:
                bm25_results = self.hybrid_retriever.bm25_search(query, top_k=max(top_k * 2, 6))
                tfidf_results = self.hybrid_retriever.tfidf_search(query, top_k=max(top_k * 2, 6))
            except Exception as exc:
                logger.warning("本地混合检索失败: %s", exc)
        elif self.documents:
            bm25_results = self._fallback_keyword_search(query, max(top_k * 2, 6))
        timings["lexical_ms"] = round((time.perf_counter() - stage_start) * 1000, 2)  # 记录词法检索耗时

        # 2. 向量检索阶段
        stage_start = time.perf_counter()
        if self.milvus_manager.collection is not None and self.bge_manager is not None:
            try:
                query_vector = self.bge_manager.embed(query)  # 将查询转换为向量
                vector_results = self.milvus_manager.vector_search(query_vector, limit=max(top_k * 2, 6))  # 向量检索
            except Exception as exc:
                logger.warning("Milvus 向量检索失败: %s", exc)
        timings["vector_ms"] = round((time.perf_counter() - stage_start) * 1000, 2)  # 记录向量检索耗时

        # 3. 召回结果分组
        recall_groups = {}
        if bm25_results:
            recall_groups["bm25"] = bm25_results
        if tfidf_results:
            recall_groups["tfidf"] = tfidf_results
        if vector_results:
            recall_groups["vector"] = vector_results

        # 4. 结果融合阶段（RRF算法）
        stage_start = time.perf_counter()
        if len(recall_groups) >= 2 and self.hybrid_retriever is not None:
            try:
                fused_results = self.hybrid_retriever.reciprocal_rank_fusion(recall_groups)  # RRF融合
            except Exception as exc:
                logger.warning("RRF 融合失败: %s", exc)
        elif recall_groups:
            # 降级融合：去重合并
            merged = []
            seen = set()
            for group_name in ("vector", "bm25", "tfidf"):  # 按优先级顺序
                for item in recall_groups.get(group_name, []):
                    # 生成文档唯一标识
                    doc_id = item.get("doc_id") or generate_doc_id(
                        item.get("question", ""),
                        item.get("answer", ""),
                        item.get("source", "")
                    )
                    if doc_id in seen:
                        continue  # 已存在的文档跳过
                    seen.add(doc_id)
                    merged.append(dict(item))
            fused_results = merged
        timings["fusion_ms"] = round((time.perf_counter() - stage_start) * 1000, 2)  # 记录融合耗时

        # 5. 重排序阶段（使用BGE重排序模型）
        stage_start = time.perf_counter()
        if fused_results and self.bge_manager is not None:
            try:
                reranked_results = self.bge_manager.rerank(
                    query,
                    [dict(item) for item in fused_results[: max(top_k * 3, 8)]],  # 取更多候选
                    top_k
                )
            except Exception as exc:
                logger.warning("BGE 重排序失败: %s", exc)
                reranked_results = fused_results[:top_k]  # 重排序失败时使用融合结果
        timings["rerank_ms"] = round((time.perf_counter() - stage_start) * 1000, 2)  # 记录重排序耗时

        # 6. 确定最终结果
        final_results = reranked_results or fused_results[:top_k] or bm25_results[:top_k] or tfidf_results[
                                                                                             :top_k] or vector_results[
                                                                                                        :top_k]
        timings["total_ms"] = round((time.perf_counter() - overall_start) * 1000, 2)  # 记录总耗时

        # 7. 返回详细结果
        return {
            "query": repair_text(query),  # 清理后的查询
            "results": self._serialize_results(final_results, limit=top_k),  # 最终结果
            "recall": {  # 各阶段召回结果
                "bm25": self._serialize_results(bm25_results),
                "tfidf": self._serialize_results(tfidf_results),
                "vector": self._serialize_results(vector_results),
                "fused": self._serialize_results(fused_results),
                "reranked": self._serialize_results(reranked_results or final_results),
            },
            "timings": timings,  # 各阶段耗时
            "modes": [name for name in ("bm25", "tfidf", "vector", "rrf", "bge-rerank") if (  # 使用的检索模式
                    (name == "bm25" and bm25_results)
                    or (name == "tfidf" and tfidf_results)
                    or (name == "vector" and vector_results)
                    or (name == "rrf" and fused_results)
                    or (name == "bge-rerank" and reranked_results)
            )],
        }

    def get_load_balancer_stats(self):
        """获取负载均衡器统计信息

        返回:
            list: 负载均衡器各节点的统计信息
        """
        if self.llm_client is not None and self.llm_client.load_balancer is not None:
            try:
                return self.llm_client.load_balancer.get_stats()  # 获取负载均衡器统计
            except Exception as exc:
                logger.warning("获取负载均衡状态失败: %s", exc)
        # 模拟模式下的默认统计信息
        return [
            {
                "name": "mock",
                "model": KIMI_MODEL or "mock",
                "weight": 1,
                "current_load": 0,
                "total_requests": 0,
                "success_rate": 0 if self.use_mock else 100,
                "avg_response_time": 0,
                "status": "mock" if self.use_mock else "active",
            }
        ]

    def get_system_overview(self):
        """获取系统概览信息

        返回:
            dict: 系统各组件状态概览
        """
        load_balancer_stats = self.get_load_balancer_stats()  # 获取负载均衡统计
        return {
            "documents": len(self.documents),  # 文档数量
            "device": self.device,  # 运行设备
            "llm_mode": "mock" if self.use_mock else "live",  # LLM模式
            "mysql": {  # MySQL状态
                "enabled": bool(getattr(self.mysql_manager, "enabled", False)),
                "host": MYSQL_HOST,
                "database": MYSQL_DATABASE,
            },
            "short_term_memory": {  # 短期记忆状态
                "backend": "redis" if getattr(self.redis_client, "enabled", False) else "in-memory",
                "redis_enabled": bool(getattr(self.redis_client, "enabled", False)),
            },
            "long_term_memory": {  # 长期记忆（Milvus）状态
                "backend": "milvus",
                "connected": self.milvus_manager.collection is not None,
                "hosts": MILVUS_HOSTS,
                "port": MILVUS_PORT,
            },
            "hybrid_retrieval": {  # 混合检索状态
                "enabled": self.hybrid_retriever is not None,
                "bm25": bool(self.hybrid_retriever is not None),
                "tfidf": bool(self.hybrid_retriever is not None),
                "multi_recall": True,
                "rerank": self.bge_manager is not None,
            },
            "bge": {  # BGE模型状态
                "m3_path": BGE_M3_PATH,
                "rerank_path": BGE_RERANKER_PATH,
                "m3_exists": Path(BGE_M3_PATH).exists(),
                "rerank_exists": Path(BGE_RERANKER_PATH).exists(),
                "loaded": self.bge_loaded,
            },
            "load_balancer": {  # 负载均衡器状态
                "enabled": bool(self.llm_client is not None and self.llm_client.load_balancer is not None),
                "endpoint_count": len(load_balancer_stats),
                "last_endpoint": getattr(self.llm_client, "last_balancer_endpoint",
                                         "mock") if self.llm_client else "mock",
            },
        }

    def run_performance_test(self, query, rounds=12, top_k=5):
        """运行性能测试

        参数:
            query: 测试查询文本
            rounds: 测试轮数
            top_k: 检索返回数量

        返回:
            dict: 性能测试结果
        """
        latencies = []  # 总耗时列表
        retrieval_latencies = []  # 检索耗时列表
        memory_latencies = []  # 记忆获取耗时列表
        rows = []  # 每轮测试详情

        for idx in range(max(1, int(rounds))):  # 循环执行测试
            total_start = time.perf_counter()  # 开始计时

            # 1. 获取短期记忆
            memory_start = time.perf_counter()
            memory = self._get_short_memory(f"perf::{idx}")  # 创建临时会话
            context_preview = memory.get_context(4)  # 获取最近4条对话上下文
            memory_ms = round((time.perf_counter() - memory_start) * 1000, 2)

            # 2. 执行检索
            retrieval = self.search_knowledge_debug(query, top_k=top_k)
            retrieval_ms = float(retrieval["timings"].get("total_ms", 0))

            # 3. 计算总耗时
            total_ms = round((time.perf_counter() - total_start) * 1000, 2)
            latencies.append(total_ms)
            retrieval_latencies.append(retrieval_ms)
            memory_latencies.append(memory_ms)

            # 4. 记录本轮结果
            rows.append(
                {
                    "round": idx + 1,
                    "total_ms": total_ms,
                    "retrieval_ms": retrieval_ms,
                    "memory_ms": memory_ms,
                    "modes": retrieval["modes"],
                    "hit_count": len(retrieval["results"]),
                    "context_ready": bool(context_preview),
                }
            )

        # 5. 统计汇总结果
        return {
            "query": repair_text(query),
            "rounds": len(rows),
            "avg_ms": round(sum(latencies) / len(latencies), 2),  # 平均耗时
            "p95_ms": percentile(latencies, 0.95),  # 95分位耗时
            "min_ms": round(min(latencies), 2),  # 最小耗时
            "max_ms": round(max(latencies), 2),  # 最大耗时
            "avg_retrieval_ms": round(sum(retrieval_latencies) / len(retrieval_latencies), 2),  # 平均检索耗时
            "avg_memory_ms": round(sum(memory_latencies) / len(memory_latencies), 2),  # 平均记忆耗时
            "rows": rows,
        }

    def run_stress_test(self, query, concurrency=8, request_count=40, top_k=5):
        """运行压力测试（并发测试）

        参数:
            query: 测试查询文本
            concurrency: 并发数
            request_count: 总请求数
            top_k: 检索返回数量

        返回:
            dict: 压力测试结果
        """
        concurrency = max(1, min(int(concurrency), 32))  # 限制并发数范围1-32
        request_count = max(1, min(int(request_count), 300))  # 限制请求数范围1-300
        latencies = []  # 响应耗时列表
        success_count = 0  # 成功请求计数
        started_at = time.perf_counter()  # 测试开始时间

        def worker():
            """单个压测工作线程"""
            started = time.perf_counter()
            try:
                retrieval = self.search_knowledge_debug(query, top_k=top_k)  # 执行检索
                latency = round((time.perf_counter() - started) * 1000, 2)  # 计算耗时
                return {"success": True, "latency_ms": latency, "hit_count": len(retrieval["results"])}
            except Exception as exc:
                return {"success": False, "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                        "error": str(exc)}

        # 使用线程池执行并发请求
        rows = []
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            # 提交所有任务
            futures = [executor.submit(worker) for _ in range(request_count)]
            # 收集完成的任务结果
            for future in as_completed(futures):
                result = future.result()
                rows.append(result)
                latencies.append(float(result["latency_ms"]))
                if result["success"]:
                    success_count += 1

        duration_seconds = max(time.perf_counter() - started_at, 0.001)  # 总耗时
        return {
            "query": repair_text(query),
            "concurrency": concurrency,  # 并发数
            "request_count": request_count,  # 请求总数
            "duration_seconds": round(duration_seconds, 2),  # 总耗时
            "throughput_rps": round(request_count / duration_seconds, 2),  # 吞吐量（请求/秒）
            "success_rate": round(success_count / request_count * 100, 2),  # 成功率
            "avg_ms": round(sum(latencies) / len(latencies), 2),  # 平均响应时间
            "p95_ms": percentile(latencies, 0.95),  # 95分位响应时间
            "max_ms": round(max(latencies), 2),  # 最大响应时间
            "rows": rows[:60],  # 只保留前60条详细记录
        }

    def chat(self, session_id, username, avatar_id, question, history_messages):
        """聊天对话方法：处理用户问题并生成回答

        参数:
            session_id: 会话ID
            username: 用户名
            avatar_id: 角色ID
            question: 用户问题
            history_messages: 历史消息列表

        返回:
            dict: 包含回答和检索信息的字典
        """
        avatar = SANITIZED_AVATARS.get(avatar_id, SANITIZED_AVATARS["doctor"])  # 获取角色配置

        # 1. 将用户问题添加到短期记忆
        memory = self._get_short_memory(session_id)
        memory.add("user", question, {"avatar_id": avatar_id})

        # 2. 检索相关知识
        retrieval = self.search_knowledge_debug(question, top_k=5)
        retrieved = retrieval["results"]
        memory_context = memory.get_context(6)  # 获取最近6条对话

        # 3. 构建上下文文本
        context_text = "暂无"
        if retrieved:
            context_text = "\n".join(
                f"{idx + 1}. {item.get('answer', '')[:300]}"  # 截取前300字符
                for idx, item in enumerate(retrieved[:4])  # 最多使用4条检索结果
            )

        # 4. 构建提示词
        prompt = (
            f"{avatar.get('prompt', '你是一位专业助手。')}\n\n"
            f"【短期记忆】\n{memory_context or '暂无'}\n\n"
            f"【长期记忆 / Milvus 知识召回】\n{context_text}\n\n"
            f"【用户问题】\n{question}"
        )

        # 5. 调用LLM生成回答
        if self.use_mock or self.llm_client is None:
            # 模拟模式：使用检索结果的第一条作为回答
            prefix = retrieved[0]["answer"] if retrieved else "当前系统处于演示模式。"
            answer = f"{prefix}\n\n补充说明：你刚刚问的是“{question}”。"
        else:
            try:
                answer = self.llm_client.call_llm(prompt)  # 调用真实LLM
            except Exception as exc:
                logger.exception("LLM 调用失败: %s", exc)
                answer = f"暂时无法完成回答，请稍后重试。你的问题是：{question}"

        # 6. 优化输出格式
        answer = self.output_optimizer.optimize(answer, question, retrieved)

        # 7. 将回答添加到短期记忆
        memory.add("assistant", answer, {"avatar_id": avatar_id})
        self._persist_short_memory(session_id)  # 持久化记忆

        # 8. 保存聊天记录到MySQL
        try:
            self.mysql_manager.save_chat_message(session_id, username, avatar_id, "user", question, 0)
            self.mysql_manager.save_chat_message(session_id, username, avatar_id, "assistant", answer, 0)
            self.mysql_manager.update_session(session_id, username, avatar_id)
        except Exception as exc:
            logger.warning("聊天记录写入失败: %s", exc)

        # 9. 返回结果
        return {
            "success": True,
            "avatar_id": avatar_id,
            "answer": answer,
            "retrieved_count": len(retrieved),  # 检索结果数量
            "retrieval_modes": retrieval["modes"],  # 使用的检索模式
            "short_memory_backend": "redis" if getattr(self.redis_client, "enabled", False) else "in-memory",
            "top_hits": retrieved[:3],  # 前3个检索结果
        }

    def register_user(self, username, email="", password=""):
        """注册新用户

        参数:
            username: 用户名
            email: 邮箱
            password: 密码

        返回:
            dict: 注册结果
        """
        return self.user_manager.register_user(username, email, password)

    def login_user(self, username, password=""):
        """用户登录

        参数:
            username: 用户名
            password: 密码

        返回:
            dict: 登录结果
        """
        return self.user_manager.login_user(username, password)

    def set_user_avatar(self, username, avatar_id):
        """设置用户的默认角色

        参数:
            username: 用户名
            avatar_id: 角色ID
        """
        return self.user_manager.set_user_avatar(username, avatar_id)


def init_system(runtime_config=None):
    """初始化全局RAG系统

    参数:
        runtime_config: 运行时配置字典
    """
    global rag_system, system_ready, system_error

    # 默认运行时配置
    runtime_config = runtime_config or {
        "user_data_file": USER_DATA_FILE,
        "bge_m3_path": BGE_M3_PATH,
        "bge_reranker_path": BGE_RERANKER_PATH,
    }

    try:
        rag_system = SimpleRAGSystem(runtime_config)  # 创建RAG系统实例
        system_ready = True  # 标记系统就绪
        system_error = ""  # 清空错误信息
        logger.info("系统初始化完成")
    except Exception as exc:
        rag_system = None  # 初始化失败，设为None
        system_ready = False  # 标记系统未就绪
        system_error = str(exc)  # 记录错误信息
        logger.exception("系统初始化失败: %s", exc)


def get_system_state():
    """获取系统状态

    返回:
        dict: 包含RAG系统实例、就绪状态和错误信息的字典
    """
    return {
        "rag_system": rag_system,
        "system_ready": system_ready,
        "system_error": system_error,
    }