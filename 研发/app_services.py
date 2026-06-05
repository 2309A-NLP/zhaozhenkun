"""
app_services — ADSD 项目在线模块核心业务逻辑。

功能说明：
- SimpleRAGSystem 类：RAG（检索增强生成）系统的核心实现
  - 初始化各组件（MySQL、Redis、Milvus、BGE模型、混合检索器、LLM客户端）
  - 提供知识库检索（BM25/TF-IDF/向量检索 + RRF融合 + BGE重排序）
  - 提供角色专属知识库检索
  - 短期记忆管理（内存 + Redis持久化）
  - 聊天对话（检索 + LLM生成 + 输出优化）
  - 用户注册/登录/角色设置
  - 性能测试、压力测试、综合测试
  - 系统概览与负载均衡状态获取
- init_system()：全局初始化函数，创建SimpleRAGSystem实例
- get_system_state()：获取当前系统状态
"""
# -*- coding: utf-8 -*-
# 指定文件编码为UTF-8，确保中文字符能正确处理

import json
# 导入json模块，用于序列化和反序列化数据（如短期记忆持久化到Redis）
import logging
# 导入logging模块，用于输出运行日志 
import threading
# 导入threading模块，用于线程安全和后台初始化
import time
# 导入time模块，用于性能计时
from concurrent.futures import ThreadPoolExecutor, as_completed
# 导入线程池执行器和任务完成收集器，用于并发请求测试
from pathlib import Path
# 从pathlib导入Path，用于路径操作

# 从配置文件导入各种配置参数
from 设计.config import (
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
    from 研发.bge_manager import BGMManager, load_bge_models
except Exception:
    BGMManager = None  # 导入失败时设为None
    load_bge_models = None  # 导入失败时设为None

# 尝试导入混合检索器
try:
    from 研发.hybrid_retriever import HybridRetriever
except Exception:
    HybridRetriever = None  # 导入失败时设为None

# 尝试导入LLM客户端
try:
    from 研发.llm_client import LLMClient
except Exception:
    LLMClient = None  # 导入失败时设为None

# 导入应用所需的其他模块
from 测试.app_monitor import percentile  # 百分位数计算函数
from 设计.app_text import DEFAULT_QUERY, SANITIZED_AVATARS, load_avatar_documents, load_local_documents, repair_text  # 文本处理相关
from 研发.milvus_manager import MilvusManager  # Milvus向量数据库管理器
from 研发.mysql_manager import MySQLManager  # MySQL数据库管理器
from 优化.output_optimizer import LLMOutputOptimizer  # LLM输出优化器
from 研发.redis_manager import RedisManager  # Redis缓存管理器
from 研发.short_term_memory import ShortTermMemory  # 短期记忆管理
from 研发.user_manager import UserManager  # 用户管理器
from 研发.utils import generate_doc_id  # 文档ID生成工具

logger = logging.getLogger(__name__)
# 获取当前模块的日志记录器实例

# 全局变量：RAG系统实例
rag_system = None
# 全局变量：系统是否就绪
system_ready = False
# 全局变量：系统错误信息
system_error = ""


class SimpleRAGSystem:
    # 定义RAG（检索增强生成）系统核心类

    """简单的RAG（检索增强生成）系统核心类"""

    def __init__(self, runtime_config):
        # 定义类的构造方法，初始化RAG系统所有组件

        """
        初始化RAG系统

        参数:
            runtime_config: 运行时配置字典
        """
        self.device = DEVICE
        # 设置运行设备（从配置中读取）
        self.vector_dim = 1024
        # 设置向量维度为1024（BGE-M3模型的默认维度）
        self.memory_lock = threading.RLock()
        # 创建可重入锁，用于保护短期记忆操作的线程安全
        self.short_term_memories = {}
        # 初始化短期记忆存储字典（键为session_id，值为ShortTermMemory对象）
        self.documents = load_local_documents()
        # 加载本地知识库文档（问答对列表）
        self.avatar_documents = load_avatar_documents()
        # 加载角色专属知识库文档（字典，键为avatar_id，值为文档列表）
        self.bge_loaded = False
        # BGE模型是否加载成功的标志，初始为False

        # 初始化MySQL管理器
        self.mysql_manager = MySQLManager(
            # 传入MySQL连接配置
            {
                "host": runtime_config.get("mysql_host", MYSQL_HOST),
                # MySQL主机地址
                "port": runtime_config.get("mysql_port", MYSQL_PORT),
                # MySQL端口
                "user": runtime_config.get("mysql_user", MYSQL_USER),
                # MySQL用户名
                "password": runtime_config.get("mysql_password", MYSQL_PASSWORD),
                # MySQL密码
                "database": runtime_config.get("mysql_database", MYSQL_DATABASE),
                # 数据库名
                "enabled": runtime_config.get("mysql_enabled", MYSQL_ENABLED),
                # 是否启用
            }
        )

        # 初始化Redis客户端
        self.redis_client = RedisManager(
            # 传入Redis连接配置
            host=runtime_config.get("redis_host", REDIS_HOST),
            # Redis主机地址
            port=runtime_config.get("redis_port", REDIS_PORT),
            # Redis端口
            password=runtime_config.get("redis_password", REDIS_PASSWORD),
            # Redis密码
        )
        try:
            self.redis_client.connect()
            # 尝试连接Redis服务器
        except Exception as exc:
            # 如果连接失败
            logger.warning("Redis 初始化失败，将继续以内存模式运行: %s", exc)
            # 记录警告日志，降级为内存模式运行

        # 初始化用户管理器
        self.user_manager = UserManager(
            # 传入用户数据文件路径和MySQL管理器
            user_data_file=runtime_config.get("user_data_file", USER_DATA_FILE),
            # 用户数据文件路径
            mysql_manager=self.mysql_manager,
            # MySQL管理器实例（用于同步用户数据）
        )

        # 初始化Milvus向量数据库管理器
        self.milvus_manager = MilvusManager(
            # 传入Milvus连接配置
            hosts=runtime_config.get("milvus_hosts", MILVUS_HOSTS),
            # Milvus主机地址列表
            port=runtime_config.get("milvus_port", MILVUS_PORT),
            # Milvus端口
        )
        try:
            self.milvus_manager.connect()
            # 尝试连接Milvus服务器
        except Exception as exc:
            # 如果连接失败
            logger.warning("Milvus 初始化失败，将继续使用本地检索链路: %s", exc)
            # 记录警告日志，降级为只使用本地检索

        # 加载BGE模型（如果模型文件存在）
        if load_bge_models is not None and Path(BGE_M3_PATH).exists() and Path(BGE_RERANKER_PATH).exists():
            # 检查：导入成功且两个模型文件夹都存在
            try:
                load_bge_models(
                    # 调用加载函数
                    {
                        "bge_m3_path": BGE_M3_PATH,
                        # BGE-M3嵌入模型路径
                        "bge_reranker_path": BGE_RERANKER_PATH,
                        # BGE重排序模型路径
                    },
                    self.device,
                    # 运行设备
                )
                self.bge_loaded = True
                # 标记模型加载成功
            except Exception as exc:
                # 如果加载失败
                logger.warning("BGE 模型加载失败，将自动降级: %s", exc)
                # 记录警告日志

        # 初始化BGE管理器
        self.bge_manager = BGMManager(self.device, self.vector_dim) if BGMManager is not None else None
        # 如果BGMManager类可用则创建实例，否则设为None

        # 初始化混合检索器
        self.hybrid_retriever = HybridRetriever() if HybridRetriever is not None else None
        # 如果HybridRetriever类可用则创建实例
        if self.hybrid_retriever is not None and self.documents:
            # 如果混合检索器创建成功且有本地文档
            try:
                self.hybrid_retriever.build_index(self.documents)
                # 用文档构建检索索引
            except Exception as exc:
                # 如果构建失败
                logger.warning("混合检索索引构建失败: %s", exc)
                # 记录警告日志
                self.hybrid_retriever = None
                # 将检索器设为None，后续会使用降级方案

        self.avatar_retrievers = {}
        # 初始化角色专属检索器字典
        if HybridRetriever is not None:
            # 如果HybridRetriever类可用
            for avatar_id, docs in self.avatar_documents.items():
                # 遍历每个角色的文档
                if not docs:
                    # 如果文档列表为空
                    continue
                    # 跳过
                try:
                    retriever = HybridRetriever()
                    # 为每个角色创建一个独立的混合检索器
                    retriever.build_index(docs)
                    # 用角色文档构建索引
                    self.avatar_retrievers[avatar_id] = retriever
                    # 存入字典
                except Exception as exc:
                    # 如果构建失败
                    logger.warning("角色知识检索索引构建失败: %s | %s", avatar_id, exc)
                    # 记录警告日志

        # 初始化输出优化器和LLM客户端
        self.output_optimizer = LLMOutputOptimizer()
        # 创建LLM输出优化器实例（用于格式化回答）
        self.llm_client = None
        # LLM客户端初始为None
        self.use_mock = True
        # 默认使用模拟模式（不调用真实LLM）
        if LLMClient is not None:
            # 如果LLMClient类可用
            try:
                self.llm_client = LLMClient()
                # 创建LLM客户端实例
                self.llm_client.init_llm(KIMI_API_KEY, KIMI_BASE_URL, KIMI_MODEL, [], [], [])
                # 初始化LLM（Kimi）：传入API密钥、基础URL、模型名称、以及空的知识库/记忆列表
                self.use_mock = self.llm_client.use_mock
                # 更新模拟模式状态（如果API密钥有效则为False，否则为True）
            except Exception as exc:
                # 如果初始化失败
                logger.warning("LLM 初始化失败，切换为 mock 模式: %s", exc)
                # 记录警告日志
                self.use_mock = True
                # 使用模拟模式

    def _memory_key(self, session_id):
        # 定义私有方法：生成本Redis中存储短期记忆的键名

        """生成Redis中存储短期记忆的键名"""
        return f"rag:short_memory:{session_id}"
        # 返回格式为"rag:short_memory:{session_id}"的字符串键

    def _get_short_memory(self, session_id):
        # 定义私有方法：获取指定会话的短期记忆对象

        """
        获取指定会话的短期记忆对象

        参数:
            session_id: 会话ID

        返回:
            ShortTermMemory: 短期记忆对象
        """
        with self.memory_lock:
            # 加锁保证线程安全
            memory = self.short_term_memories.get(session_id)
            # 从内存字典中获取该会话的短期记忆
            if memory is None:
                # 如果内存中不存在该会话的记忆
                memory = ShortTermMemory(max_turns=12)
                # 创建新的短期记忆对象，最多保存12轮对话
                self.short_term_memories[session_id] = memory
                # 存入内存字典
                if getattr(self.redis_client, "enabled", False):
                    # 如果Redis客户端已启用
                    raw = self.redis_client.get(self._memory_key(session_id))
                    # 从Redis获取该会话的历史记忆（JSON字符串）
                    if raw:
                        # 如果获取到数据
                        try:
                            for item in json.loads(raw):
                                # 反序列化JSON为列表，遍历每个条目
                                memory.add(item.get("role", "user"), item.get("content", ""), item.get("metadata", {}))
                                # 将每条记忆恢复到ShortTermMemory对象中
                        except Exception:
                            # 如果反序列化或恢复失败
                            pass
                            # 静默忽略（保留空记忆）
        return memory
        # 返回短期记忆对象

    def _persist_short_memory(self, session_id):
        # 定义私有方法：将短期记忆持久化到Redis

        """
        将短期记忆持久化到Redis

        参数:
            session_id: 会话ID
        """
        if not getattr(self.redis_client, "enabled", False):
            # 如果Redis未启用
            return
            # 直接返回，不做持久化
        memory = self.short_term_memories.get(session_id)
        # 从内存中获取该会话的短期记忆
        if not memory:
            # 如果记忆不存在
            return
            # 直接返回
        payload = json.dumps(memory.conversation, ensure_ascii=False)
        # 将记忆中的对话记录序列化为JSON字符串（不转义ASCII，保留中文）
        self.redis_client.set(self._memory_key(session_id), payload, expire=24 * 3600)
        # 存储到Redis，设置过期时间为24小时

    def clear_short_memory(self, session_id):
        # 定义方法：清除指定会话的短期记忆

        """
        清除指定会话的短期记忆

        参数:
            session_id: 会话ID
        """
        with self.memory_lock:
            # 加锁保证线程安全
            self.short_term_memories.pop(session_id, None)
            # 从内存字典中移除该会话的记忆
        if getattr(self.redis_client, "enabled", False):
            # 如果Redis已启用
            self.redis_client.delete(self._memory_key(session_id))
            # 从Redis中删除该会话的记忆

    def _serialize_results(self, results, limit=5):
        # 定义私有方法：序列化检索结果，提取关键字段并限制数量

        """
        序列化检索结果，提取关键字段并限制数量

        参数:
            results: 检索结果列表
            limit: 最大返回数量

        返回:
            list: 序列化后的结果列表
        """
        serialized = []
        # 初始化空列表
        for item in results[:limit]:
            # 只处理前limit个结果
            serialized.append(
                # 提取每个文档的关键字段
                {
                    "question": repair_text(item.get("question", "")),
                    # 问题文本（乱码修复）
                    "answer": repair_text(item.get("answer", "")),
                    # 答案文本（乱码修复）
                    "source": repair_text(item.get("source", "")),
                    # 来源信息（乱码修复）
                    "score": round(float(item.get("score", 0.0)), 4),
                    # 综合得分，保留4位小数
                    "fusion_score": round(float(item.get("fusion_score", 0.0)), 4),
                    # 融合得分
                    "rerank_score": round(float(item.get("rerank_score", 0.0)), 4),
                    # 重排序得分
                    "vector_score": round(float(item.get("vector_score", 0.0)), 4),
                    # 向量检索得分
                    "tfidf_score": round(float(item.get("tfidf_score", 0.0)), 4),
                    # TF-IDF得分
                    "bm25_score": round(float(item.get("bm25_score", 0.0)), 4),
                    # BM25得分
                    "retrieval_method": item.get("retrieval_method", ""),
                    # 使用的检索方法
                }
            )
        return serialized
        # 返回序列化后的结果列表

    def _fallback_keyword_search(self, query, top_k, documents=None):
        # 定义私有方法：降级的关键词搜索（当混合检索不可用时使用）

        """
        降级的关键词搜索（当混合检索不可用时）

        参数:
            query: 查询文本
            top_k: 返回结果数量

        返回:
            list: 检索结果列表
        """
        query = query.strip()
        # 去除查询文本两端的空白
        corpus = documents if documents is not None else self.documents
        # 确定搜索范围：如果传入了文档则使用，否则使用全局文档
        if not query or not corpus:
            # 如果查询为空或文档为空
            return []
            # 返回空列表
        query_chars = set(query)
        # 获取查询文本的不重复字符集合
        scored = []
        # 初始化得分列表
        for doc in corpus:
            # 遍历所有文档
            text = f"{doc.get('question', '')} {doc.get('answer', '')}"
            # 拼接文档的问题和答案文本
            overlap = len(query_chars.intersection(set(text)))
            # 计算查询字符集合与文档字符集合的交集大小（字符重合度）
            if overlap <= 0:
                # 如果没有重合字符
                continue
                # 跳过该文档
            scored.append(
                # 将文档及其得分添加到列表
                {
                    **doc,
                    # 解包原始文档的所有字段
                    "score": float(overlap),
                    # 用字符重合度作为得分
                    "retrieval_method": "keyword",
                    # 标记为关键词检索
                }
            )
        scored.sort(key=lambda item: item.get("score", 0), reverse=True)
        # 按得分降序排序
        return scored[:top_k]
        # 返回得分最高的前top_k个结果

    def _search_avatar_knowledge_debug(self, query, avatar_id, top_k=5):
        # 定义私有方法：检索角色专属知识库，详细调试模式

        """检索角色专属知识库，命中后优先返回"""
        documents = self.avatar_documents.get(avatar_id) or []
        # 获取该角色的文档列表
        retriever = self.avatar_retrievers.get(avatar_id)
        # 获取该角色的专属混合检索器
        if not query.strip() or not documents:
            # 如果查询为空或没有文档
            return {
                "query": repair_text(query),
                # 清理后的查询
                "results": [],
                # 空结果
                "recall": {},
                # 空召回分组
                "timings": {"total_ms": 0.0},
                # 耗时为0
                "modes": [],
                # 空模式列表
            }

        overall_start = time.perf_counter()
        # 记录整体开始时间（高精度计时器）
        bm25_results = []
        # BM25检索结果
        tfidf_results = []
        # TF-IDF检索结果
        fused_results = []
        # 融合后的结果
        reranked_results = []
        # 重排序后的结果
        timings = {}
        # 各阶段耗时字典
        top_k = max(1, int(top_k))
        # 确保top_k至少为1

        stage_start = time.perf_counter()
        # 记录词法检索阶段开始时间
        try:
            if retriever is not None:
                # 如果有混合检索器
                bm25_results = retriever.bm25_search(query, top_k=max(top_k * 2, 6))
                # BM25检索，候选数取top_k*2和6中的较大值
                tfidf_results = retriever.tfidf_search(query, top_k=max(top_k * 2, 6))
                # TF-IDF检索
            else:
                # 如果没有混合检索器
                bm25_results = self._fallback_keyword_search(query, max(top_k * 2, 6), documents=documents)
                # 使用降级的关键词搜索
        except Exception as exc:
            # 如果检索失败
            logger.warning("角色知识检索失败: %s | %s", avatar_id, exc)
            # 记录警告日志
        timings["avatar_lexical_ms"] = round((time.perf_counter() - stage_start) * 1000, 2)
        # 记录词法检索耗时（毫秒）

        recall_groups = {}
        # 初始化召回结果分组字典
        if bm25_results:
            # 如果有BM25结果
            recall_groups["bm25"] = bm25_results
            # 添加到分组
        if tfidf_results:
            # 如果有TF-IDF结果
            recall_groups["tfidf"] = tfidf_results
            # 添加到分组

        stage_start = time.perf_counter()
        # 记录融合阶段开始时间
        if len(recall_groups) >= 2 and retriever is not None:
            # 如果有至少两种检索结果且有混合检索器
            try:
                fused_results = retriever.reciprocal_rank_fusion(recall_groups)
                # 使用RRF（倒数排名融合）算法融合多种检索结果
            except Exception as exc:
                # 如果融合失败
                logger.warning("角色知识 RRF 融合失败: %s | %s", avatar_id, exc)
                # 记录警告日志
        elif recall_groups:
            # 如果只有一种检索结果或没有检索器
            seen = set()
            # 用于去重的文档ID集合
            merged = []
            # 合并后的结果列表
            for group_name in ("bm25", "tfidf"):
                # 按优先级顺序遍历检索类型
                for item in recall_groups.get(group_name, []):
                    # 遍历该类型的每个结果
                    doc_id = item.get("doc_id") or generate_doc_id(
                        # 获取文档ID，如果没有则根据内容生成
                        item.get("question", ""),
                        item.get("answer", ""),
                        item.get("source", "")
                    )
                    if doc_id in seen:
                        # 如果文档ID已存在
                        continue
                        # 跳过重复
                    seen.add(doc_id)
                    # 记录文档ID
                    merged.append(dict(item))
                    # 将文档添加到合并列表
            fused_results = merged
            # 将去重合并后的结果作为融合结果
        timings["avatar_fusion_ms"] = round((time.perf_counter() - stage_start) * 1000, 2)
        # 记录融合耗时

        stage_start = time.perf_counter()
        # 记录重排序阶段开始时间
        if fused_results and self.bge_manager is not None:
            # 如果有融合结果且有BGE重排序模型
            try:
                reranked_results = self.bge_manager.rerank(
                    # 对融合结果进行语义重排序
                    query,
                    # 原始查询
                    [dict(item) for item in fused_results[: max(top_k * 3, 8)]],
                    # 取更多候选结果（top_k*3和8的较大值）进行重排序
                    top_k
                    # 最终返回top_k个结果
                )
            except Exception as exc:
                # 如果重排序失败
                logger.warning("角色知识 BGE 重排序失败: %s | %s", avatar_id, exc)
                # 记录警告日志
                reranked_results = fused_results[:top_k]
                # 降级：直接使用融合结果的前top_k个
        timings["avatar_rerank_ms"] = round((time.perf_counter() - stage_start) * 1000, 2)
        # 记录重排序耗时

        final_results = reranked_results or fused_results[:top_k] or bm25_results[:top_k] or tfidf_results[:top_k]
        # 确定最终结果：优先使用重排序结果，然后融合结果、BM25结果、TF-IDF结果
        timings["total_ms"] = round((time.perf_counter() - overall_start) * 1000, 2)
        # 记录总耗时

        return {
            # 返回详细结果
            "query": repair_text(query),
            # 清理后的查询
            "results": self._serialize_results(final_results, limit=top_k),
            # 最终结果（序列化）
            "recall": {
                # 各阶段召回结果
                "bm25": self._serialize_results(bm25_results),
                # BM25召回结果
                "tfidf": self._serialize_results(tfidf_results),
                # TF-IDF召回结果
                "fused": self._serialize_results(fused_results),
                # 融合结果
                "reranked": self._serialize_results(reranked_results or final_results),
                # 重排序结果
            },
            "timings": timings,
            # 各阶段耗时
            "modes": [name for name in ("avatar-bm25", "avatar-tfidf", "avatar-rrf", "avatar-bge-rerank") if (
                    # 本次检索实际使用的模式列表
                    (name == "avatar-bm25" and bm25_results)
                    or (name == "avatar-tfidf" and tfidf_results)
                    or (name == "avatar-rrf" and fused_results)
                    or (name == "avatar-bge-rerank" and reranked_results)
            )],
        }

    def search_knowledge_debug(self, query, top_k=5, avatar_id=None):
        # 定义方法：知识库检索调试，返回详细的检索过程和结果

        """
        知识库检索调试方法，返回详细的检索过程和结果

        参数:
            query: 查询文本
            top_k: 返回结果数量
            avatar_id: 角色ID（有专属知识库时优先使用）

        返回:
            dict: 包含检索结果和详细调试信息的字典
        """
        overall_start = time.perf_counter()
        # 记录整体开始时间
        bm25_results = []
        # BM25检索结果列表
        tfidf_results = []
        # TF-IDF检索结果列表
        vector_results = []
        # 向量检索结果列表
        fused_results = []
        # RRF融合结果列表
        reranked_results = []
        # BGE重排序结果列表
        timings = {}
        # 各阶段耗时字典
        top_k = max(1, int(top_k))
        # 确保top_k至少为1

        if not query.strip():
            # 如果查询为空（仅空白字符）
            return {
                "query": query,
                # 原样返回查询
                "results": [],
                # 空结果
                "recall": {},
                # 空召回
                "timings": {"total_ms": 0.0},
                # 耗时0
                "modes": [],
                # 空模式
            }

        if avatar_id in self.avatar_documents:
            # 如果指定了角色ID且该角色有专属知识库
            avatar_retrieval = self._search_avatar_knowledge_debug(query, avatar_id, top_k=top_k)
            # 调用角色专属知识库检索
            if avatar_retrieval.get("results"):
                # 如果检索到了结果
                return avatar_retrieval
                # 直接返回角色检索结果（优先使用角色知识库）

        # 1. 词法检索阶段（BM25 + TF-IDF）
        stage_start = time.perf_counter()
        # 记录词法检索开始时间
        if self.hybrid_retriever is not None:
            # 如果有混合检索器
            try:
                bm25_results = self.hybrid_retriever.bm25_search(query, top_k=max(top_k * 2, 6))
                # 执行BM25检索，候选数取top_k*2和6中的较大值
                tfidf_results = self.hybrid_retriever.tfidf_search(query, top_k=max(top_k * 2, 6))
                # 执行TF-IDF检索
            except Exception as exc:
                # 如果检索失败
                logger.warning("本地混合检索失败: %s", exc)
                # 记录警告日志
        elif self.documents:
            # 如果没有混合检索器但有文档
            bm25_results = self._fallback_keyword_search(query, max(top_k * 2, 6))
            # 使用降级的关键词搜索
        timings["lexical_ms"] = round((time.perf_counter() - stage_start) * 1000, 2)
        # 记录词法检索耗时（毫秒）

        # 2. 向量检索阶段
        stage_start = time.perf_counter()
        # 记录向量检索开始时间
        if self.milvus_manager.collection is not None and self.bge_manager is not None:
            # 如果Milvus已连接且有BGE嵌入模型
            try:
                query_vector = self.bge_manager.embed(query)
                # 使用BGE-M3模型将查询文本转换为向量
                vector_results = self.milvus_manager.vector_search(query_vector, limit=max(top_k * 2, 6))
                # 在Milvus中执行向量相似度检索
            except Exception as exc:
                # 如果向量检索失败
                logger.warning("Milvus 向量检索失败: %s", exc)
                # 记录警告日志
        timings["vector_ms"] = round((time.perf_counter() - stage_start) * 1000, 2)
        # 记录向量检索耗时

        # 3. 召回结果分组
        recall_groups = {}
        # 初始化召回结果分组字典
        if bm25_results:
            # 如果有BM25结果
            recall_groups["bm25"] = bm25_results
            # 添加到分组
        if tfidf_results:
            # 如果有TF-IDF结果
            recall_groups["tfidf"] = tfidf_results
            # 添加到分组
        if vector_results:
            # 如果有向量检索结果
            recall_groups["vector"] = vector_results
            # 添加到分组

        # 4. 结果融合阶段（RRF算法）
        stage_start = time.perf_counter()
        # 记录融合开始时间
        if len(recall_groups) >= 2 and self.hybrid_retriever is not None:
            # 如果至少有2种检索结果且有混合检索器
            try:
                fused_results = self.hybrid_retriever.reciprocal_rank_fusion(recall_groups)
                # 使用RRF（倒数排名融合）算法融合多种检索结果
            except Exception as exc:
                # 如果融合失败
                logger.warning("RRF 融合失败: %s", exc)
                # 记录警告日志
        elif recall_groups:
            # 如果只有1种检索结果或没有混合检索器，使用降级融合：去重合并
            merged = []
            # 合并列表
            seen = set()
            # 文档ID去重集合
            for group_name in ("vector", "bm25", "tfidf"):
                # 按优先级顺序（向量>BM25>TF-IDF）遍历
                for item in recall_groups.get(group_name, []):
                    # 遍历该类型的每个结果
                    doc_id = item.get("doc_id") or generate_doc_id(
                        # 获取文档ID
                        item.get("question", ""),
                        item.get("answer", ""),
                        item.get("source", "")
                    )
                    if doc_id in seen:
                        # 如果已存在
                        continue
                        # 跳过重复
                    seen.add(doc_id)
                    # 记录文档ID
                    merged.append(dict(item))
                    # 添加到合并列表
            fused_results = merged
            # 去重合并后的结果作为融合结果
        timings["fusion_ms"] = round((time.perf_counter() - stage_start) * 1000, 2)
        # 记录融合耗时

        # 5. 重排序阶段（使用BGE重排序模型）
        stage_start = time.perf_counter()
        # 记录重排序开始时间
        if fused_results and self.bge_manager is not None:
            # 如果有融合结果且有BGE重排序模型
            try:
                reranked_results = self.bge_manager.rerank(
                    # 对融合结果进行语义重排序
                    query,
                    # 原始查询
                    [dict(item) for item in fused_results[: max(top_k * 3, 8)]],
                    # 取更多候选结果（top_k*3和8的较大值）进行重排序
                    top_k
                    # 最终返回top_k个结果
                )
            except Exception as exc:
                # 如果重排序失败
                logger.warning("BGE 重排序失败: %s", exc)
                # 记录警告日志
                reranked_results = fused_results[:top_k]
                # 降级：直接使用融合结果的前top_k个
        timings["rerank_ms"] = round((time.perf_counter() - stage_start) * 1000, 2)
        # 记录重排序耗时

        # 6. 确定最终结果
        final_results = reranked_results or fused_results[:top_k] or bm25_results[:top_k] or tfidf_results[:top_k] or vector_results[:top_k]
        # 优先级：重排序结果 > 融合结果 > BM25 > TF-IDF > 向量结果
        timings["total_ms"] = round((time.perf_counter() - overall_start) * 1000, 2)
        # 记录总耗时

        # 7. 返回详细结果
        return {
            "query": repair_text(query),
            # 清理后的查询
            "results": self._serialize_results(final_results, limit=top_k),
            # 最终结果（序列化）
            "recall": {
                # 各阶段召回结果
                "bm25": self._serialize_results(bm25_results),
                # BM25召回结果
                "tfidf": self._serialize_results(tfidf_results),
                # TF-IDF召回结果
                "vector": self._serialize_results(vector_results),
                # 向量召回结果
                "fused": self._serialize_results(fused_results),
                # 融合结果
                "reranked": self._serialize_results(reranked_results or final_results),
                # 重排序结果
            },
            "timings": timings,
            # 各阶段耗时
            "modes": [name for name in ("bm25", "tfidf", "vector", "rrf", "bge-rerank") if (
                    # 本次检索实际使用的模式列表
                    (name == "bm25" and bm25_results)
                    or (name == "tfidf" and tfidf_results)
                    or (name == "vector" and vector_results)
                    or (name == "rrf" and fused_results)
                    or (name == "bge-rerank" and reranked_results)
            )],
        }

    def run_retrieval_probe(self, query, top_k=5, include_results=False, avatar_id=None):
        # 定义方法：返回精简的检索结果（用于HTTP压测场景）

        """返回适合 HTTP 压测的精简检索结果"""
        top_k = max(1, int(top_k))
        # 确保top_k至少为1
        retrieval = self.search_knowledge_debug(query, top_k=top_k, avatar_id=avatar_id)
        # 调用详细的检索调试方法
        recall = retrieval.get("recall", {})
        # 获取召回分组信息
        result = {
            # 构建精简返回结果
            "query": retrieval.get("query", repair_text(query)),
            # 查询文本
            "top_k": top_k,
            # 检索数量
            "hit_count": len(retrieval.get("results", [])),
            # 命中数量
            "timings": retrieval.get("timings", {}),
            # 各阶段耗时
            "modes": retrieval.get("modes", []),
            # 使用的检索模式
            "recall_counts": {
                # 各模式召回数量统计
                "bm25": len(recall.get("bm25", [])),
                "tfidf": len(recall.get("tfidf", [])),
                "vector": len(recall.get("vector", [])),
                "fused": len(recall.get("fused", [])),
                "reranked": len(recall.get("reranked", [])),
            },
        }
        if include_results:
            # 如果需要包含结果详情
            result["results"] = [
                # 提取每个结果的关键字段
                {
                    "question": item.get("question", ""),
                    # 问题
                    "source": item.get("source", ""),
                    # 来源
                    "score": item.get("score", 0.0),
                    # 得分
                    "retrieval_method": item.get("retrieval_method", ""),
                    # 检索方法
                }
                for item in retrieval.get("results", [])
                # 遍历检索结果
            ]
        return result
        # 返回精简结果

    def _is_smalltalk(self, text):
        # 定义私有方法：判断是否为寒暄或无业务信息的输入

        """判断是否为寒暄或无业务信息输入"""
        normalized = repair_text((text or "").strip()).lower()
        # 清理并修复文本，转为小写
        if not normalized:
            # 如果为空
            return True
            # 视为寒暄
        for token in ("。", "！", "？", "!", "?", ".", ",", "，"):
            # 移除常见的标点符号
            normalized = normalized.replace(token, "")
            # 替换为空字符串
        return normalized in {"你好", "您好", "hi", "hello", "在吗", "在不在", "1", "test", "测试", "喂", "哈喽"}
        # 判断是否为常见的寒暄词集合

    def _mock_avatar_reply(self, avatar_id, question, retrieved):
        # 定义私有方法：按角色生成模拟回复（mock模式时使用）

        """按角色生成 mock 回复，避免串角色话术"""
        question = repair_text(question)
        # 修复问题中的乱码
        if self._is_smalltalk(question):
            # 如果是寒暄
            greetings = {
                # 各角色的寒暄回复模板
                "doctor": "你好，我是医生助手。你可以告诉我症状、持续时间和顾虑。",
                "psychologist": "你好，我是心理顾问助手。你可以和我聊压力、焦虑、低落或关系问题。",
                "marketer": "你好，我是营销专家助手。你可以问我定位、增长、内容或转化问题。",
                "chinese_teacher": "你好，我是语文老师助手。你可以问我课文内容、主旨、写法、文言词句或答题思路。",
            }
            return greetings.get(avatar_id, "你好，我是当前角色助手。请直接说你的问题。")
            # 返回对应角色的欢迎语

        if retrieved:
            # 如果有检索到相关知识
            prefix = (retrieved[0].get("answer") or "").strip()
            # 获取第一个检索结果的答案
            if prefix:
                # 如果答案非空
                return f"{prefix}\n\n补充说明：你刚刚问的是“{question}”。"
                # 返回答案 + 补充说明

        fallbacks = {
            # 各角色的默认回复模板（无检索结果时使用）
            "doctor": f"我先按医生角色接待你。请补充症状、持续时间、严重程度和是否已用药。你刚刚问的是“{question}”。",
            "psychologist": f"我先按心理顾问角色接待你。可以说说你现在最困扰的感受、触发原因和持续多久。你刚刚问的是“{question}”。",
            "marketer": f"我先按营销专家角色接待你。请补充产品、目标人群、渠道和你想解决的指标。你刚刚问的是“{question}”。",
            "chinese_teacher": f"我先按语文老师角色接待你。请告诉我是课文内容、主旨、写作手法、人物形象，还是文言词句问题。你刚刚问的是“{question}”。",
        }
        return fallbacks.get(avatar_id, f"当前系统处于演示模式。你刚刚问的是“{question}”。")
        # 返回对应角色的默认回复

    def get_load_balancer_stats(self):
        # 定义方法：获取负载均衡器统计信息

        """
        获取负载均衡器统计信息

        返回:
            list: 负载均衡器各节点的统计信息
        """
        if self.llm_client is not None and self.llm_client.load_balancer is not None:
            # 如果LLM客户端存在且启用了负载均衡器
            try:
                return self.llm_client.load_balancer.get_stats()
                # 获取负载均衡器各节点的统计信息
            except Exception as exc:
                # 如果获取失败
                logger.warning("获取负载均衡状态失败: %s", exc)
                # 记录警告日志
        # 模拟模式下的默认统计信息
        return [
            # 返回一个默认的mock节点信息
            {
                "name": "mock",
                # 节点名称
                "model": KIMI_MODEL or "mock",
                # 模型名称
                "weight": 1,
                # 权重
                "current_load": 0,
                # 当前负载
                "total_requests": 0,
                # 总请求数
                "success_rate": 0 if self.use_mock else 100,
                # 成功率：mock模式为0，否则为100
                "avg_response_time": 0,
                # 平均响应时间
                "status": "mock" if self.use_mock else "active",
                # 状态：mock模式为"mock"，否则为"active"
            }
        ]

    def get_system_overview(self):
        # 定义方法：获取系统概览信息

        """
        获取系统概览信息

        返回:
            dict: 系统各组件状态概览
        """
        load_balancer_stats = self.get_load_balancer_stats()
        # 获取负载均衡器统计信息
        return {
            # 返回系统各组件状态
            "documents": len(self.documents),
            # 本地知识库文档总数
            "device": self.device,
            # 运行设备（cuda/cpu）
            "llm_mode": "mock" if self.use_mock else "live",
            # LLM模式：mock（模拟）或live（真实）
            "mysql": {
                # MySQL数据库状态
                "enabled": bool(getattr(self.mysql_manager, "enabled", False)),
                # 是否启用
                "host": MYSQL_HOST,
                # 主机地址
                "database": MYSQL_DATABASE,
                # 数据库名
            },
            "short_term_memory": {
                # 短期记忆状态
                "backend": "redis" if getattr(self.redis_client, "enabled", False) else "in-memory",
                # 后端类型：redis或in-memory
                "redis_enabled": bool(getattr(self.redis_client, "enabled", False)),
                # Redis是否启用
            },
            "long_term_memory": {
                # 长期记忆（Milvus向量数据库）状态
                "backend": "milvus",
                # 后端类型
                "connected": self.milvus_manager.collection is not None,
                # 是否已连接
                "hosts": MILVUS_HOSTS,
                # 主机地址列表
                "port": MILVUS_PORT,
                # 端口
            },
            "hybrid_retrieval": {
                # 混合检索状态
                "enabled": self.hybrid_retriever is not None,
                # 是否启用
                "bm25": bool(self.hybrid_retriever is not None),
                # BM25是否可用
                "tfidf": bool(self.hybrid_retriever is not None),
                # TF-IDF是否可用
                "multi_recall": True,
                # 支持多路召回
                "rerank": self.bge_manager is not None,
                # BGE重排序是否可用
            },
            "bge": {
                # BGE模型状态
                "m3_path": BGE_M3_PATH,
                # BGE-M3嵌入模型路径
                "rerank_path": BGE_RERANKER_PATH,
                # BGE重排序模型路径
                "m3_exists": Path(BGE_M3_PATH).exists(),
                # M3模型文件是否存在
                "rerank_exists": Path(BGE_RERANKER_PATH).exists(),
                # 重排序模型文件是否存在
                "loaded": self.bge_loaded,
                # 是否已成功加载
            },
            "load_balancer": {
                # 负载均衡器状态
                "enabled": bool(self.llm_client is not None and self.llm_client.load_balancer is not None),
                # 是否启用
                "endpoint_count": len(load_balancer_stats),
                # LLM端点数量
                "last_endpoint": getattr(self.llm_client, "last_balancer_endpoint",
                                         "mock") if self.llm_client else "mock",
                # 最近使用的端点
            },
        }

    def run_performance_test(self, query, rounds=12, top_k=5):
        # 定义方法：运行性能测试（顺序执行多轮检索）

        """
        运行性能测试

        参数:
            query: 测试查询文本
            rounds: 测试轮数
            top_k: 检索返回数量

        返回:
            dict: 性能测试结果
        """
        latencies = []
        # 总耗时列表
        retrieval_latencies = []
        # 检索耗时列表
        memory_latencies = []
        # 记忆获取耗时列表
        rows = []
        # 每轮测试详情列表

        for idx in range(max(1, int(rounds))):
            # 循环执行指定轮数的测试（至少1轮）
            total_start = time.perf_counter()
            # 记录本轮开始时间

            # 1. 获取短期记忆
            memory_start = time.perf_counter()
            # 记录记忆获取开始时间
            memory = self._get_short_memory(f"perf::{idx}")
            # 创建一个临时会话ID获取短期记忆
            context_preview = memory.get_context(4)
            # 获取最近4条对话作为上下文预览
            memory_ms = round((time.perf_counter() - memory_start) * 1000, 2)
            # 计算记忆获取耗时

            # 2. 执行检索
            retrieval = self.search_knowledge_debug(query, top_k=top_k)
            # 执行知识库检索
            retrieval_ms = float(retrieval["timings"].get("total_ms", 0))
            # 获取检索耗时

            # 3. 计算总耗时
            total_ms = round((time.perf_counter() - total_start) * 1000, 2)
            # 计算本轮总耗时
            latencies.append(total_ms)
            # 添加到总耗时列表
            retrieval_latencies.append(retrieval_ms)
            # 添加到检索耗时列表
            memory_latencies.append(memory_ms)
            # 添加到记忆耗时列表

            # 4. 记录本轮结果
            rows.append(
                # 记录本轮详情
                {
                    "round": idx + 1,
                    # 轮次编号（从1开始）
                    "total_ms": total_ms,
                    # 本轮总耗时
                    "retrieval_ms": retrieval_ms,
                    # 检索耗时
                    "memory_ms": memory_ms,
                    # 记忆获取耗时
                    "modes": retrieval["modes"],
                    # 使用的检索模式
                    "hit_count": len(retrieval["results"]),
                    # 命中文档数
                    "context_ready": bool(context_preview),
                    # 上下文是否可用
                }
            )

        # 5. 统计汇总结果
        return {
            # 返回性能测试汇总
            "query": repair_text(query),
            # 测试查询
            "rounds": len(rows),
            # 实际执行轮数
            "avg_ms": round(sum(latencies) / len(latencies), 2),
            # 平均耗时
            "p95_ms": percentile(latencies, 0.95),
            # 95分位耗时
            "min_ms": round(min(latencies), 2),
            # 最小耗时
            "max_ms": round(max(latencies), 2),
            # 最大耗时
            "avg_retrieval_ms": round(sum(retrieval_latencies) / len(retrieval_latencies), 2),
            # 平均检索耗时
            "avg_memory_ms": round(sum(memory_latencies) / len(memory_latencies), 2),
            # 平均记忆获取耗时
            "rows": rows,
            # 每轮测试详情
        }

    def run_stress_test(self, query, concurrency=8, request_count=40, top_k=5):
        # 定义方法：运行压力测试（并发请求）

        """
        运行压力测试（并发测试）

        参数:
            query: 测试查询文本
            concurrency: 并发数
            request_count: 总请求数
            top_k: 检索返回数量

        返回:
            dict: 压力测试结果
        """
        concurrency = max(1, min(int(concurrency), 32))
        # 限制并发数范围：1-32
        request_count = max(1, min(int(request_count), 300))
        # 限制总请求数范围：1-300
        latencies = []
        # 响应耗时列表
        success_count = 0
        # 成功请求计数
        started_at = time.perf_counter()
        # 记录测试开始时间

        def worker():
            # 定义单个压测工作线程函数
            """单个压测工作线程"""
            started = time.perf_counter()
            # 记录本线程开始时间
            try:
                retrieval = self.search_knowledge_debug(query, top_k=top_k)
                # 执行知识库检索
                latency = round((time.perf_counter() - started) * 1000, 2)
                # 计算耗时
                return {"success": True, "latency_ms": latency, "hit_count": len(retrieval["results"])}
                # 返回成功结果
            except Exception as exc:
                # 如果出现异常
                return {"success": False, "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                        "error": str(exc)}
                # 返回失败结果及错误信息

        # 使用线程池执行并发请求
        rows = []
        # 存储所有请求的结果
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            # 创建线程池，最大工作线程数为concurrency
            futures = [executor.submit(worker) for _ in range(request_count)]
            # 提交所有请求任务到线程池
            for future in as_completed(futures):
                # 遍历已完成的任务（按完成顺序）
                result = future.result()
                # 获取任务结果
                rows.append(result)
                # 添加到结果列表
                latencies.append(float(result["latency_ms"]))
                # 记录耗时
                if result["success"]:
                    # 如果请求成功
                    success_count += 1
                    # 成功计数加1

        duration_seconds = max(time.perf_counter() - started_at, 0.001)
        # 计算总耗时（秒），避免除零
        return {
            # 返回压力测试结果
            "query": repair_text(query),
            # 测试查询
            "concurrency": concurrency,
            # 并发数
            "request_count": request_count,
            # 请求总数
            "duration_seconds": round(duration_seconds, 2),
            # 总耗时（秒）
            "throughput_rps": round(request_count / duration_seconds, 2),
            # 吞吐量（请求/秒）
            "success_rate": round(success_count / request_count * 100, 2),
            # 成功率（%）
            "avg_ms": round(sum(latencies) / len(latencies), 2),
            # 平均响应时间（毫秒）
            "p95_ms": percentile(latencies, 0.95),
            # 95分位响应时间
            "max_ms": round(max(latencies), 2),
            # 最大响应时间
            "rows": rows[:60],
            # 只保留前60条详细记录
        }

    def run_combined_test(self, query, concurrency=8, request_count=40, top_k=5):
        # 定义方法：运行综合测试（一次输出混合检索、负载均衡和压力测试结果）

        """综合测试：一次输出混合检索、负载均衡和压力测试结果"""
        overview = self.get_system_overview()
        # 获取系统概览
        retrieval = self.run_retrieval_probe(query, top_k=top_k, include_results=True)
        # 执行检索探针（包含详情）
        load_balancer_stats = self.get_load_balancer_stats()
        # 获取负载均衡器统计
        stress = self.run_stress_test(
            # 执行压力测试
            query,
            concurrency=concurrency,
            request_count=request_count,
            top_k=top_k,
        )

        endpoint_count = len(load_balancer_stats)
        # 负载均衡端点数量
        total_requests = sum(int(item.get("total_requests", 0) or 0) for item in load_balancer_stats)
        # 总请求数（各端点求和）
        avg_success_rate = round(
            # 计算平均成功率
            sum(float(item.get("success_rate", 0) or 0) for item in load_balancer_stats) / endpoint_count,
            2,
        ) if endpoint_count else 0.0
        # 如果有端点则计算平均值，否则为0
        avg_response_time = round(
            # 计算平均响应时间
            sum(float(item.get("avg_response_time", 0) or 0) for item in load_balancer_stats) / endpoint_count,
            2,
        ) if endpoint_count else 0.0
        # 如果有端点则计算平均值，否则为0

        return {
            # 返回综合测试结果
            "query": repair_text(query),
            # 测试查询
            "top_k": max(1, int(top_k)),
            # top_k值
            "overview": overview,
            # 系统概览
            "retrieval": retrieval,
            # 检索探针结果
            "load_balancer": {
                # 负载均衡汇总
                "enabled": overview.get("load_balancer", {}).get("enabled", False),
                # 是否启用
                "endpoint_count": endpoint_count,
                # 端点数量
                "total_requests": total_requests,
                # 总请求数
                "avg_success_rate": avg_success_rate,
                # 平均成功率
                "avg_response_time": avg_response_time,
                # 平均响应时间
                "stats": load_balancer_stats,
                # 各端点详细统计
            },
            "stress": stress,
            # 压力测试结果
        }

    def chat(self, session_id, username, avatar_id, question, history_messages):
        # 定义方法：聊天对话（处理用户问题并生成回答）

        """
        聊天对话方法：处理用户问题并生成回答

        参数:
            session_id: 会话ID
            username: 用户名
            avatar_id: 角色ID
            question: 用户问题
            history_messages: 历史消息列表

        返回:
            dict: 包含回答和检索信息的字典
        """
        avatar = SANITIZED_AVATARS.get(avatar_id, SANITIZED_AVATARS["doctor"])
        # 获取当前角色的配置信息

        # 1. 将用户问题添加到短期记忆
        memory = self._get_short_memory(session_id)
        # 获取该会话的短期记忆对象
        memory.add("user", question, {"avatar_id": avatar_id})
        # 将用户问题添加到短期记忆中

        # 2. 检索相关知识
        retrieval = self.search_knowledge_debug(question, top_k=5, avatar_id=avatar_id)
        # 从知识库中检索与问题相关的文档
        retrieved = retrieval["results"]
        # 获取检索结果列表
        memory_context = memory.get_context(6)
        # 获取最近6条短期记忆对话记录

        # 3. 构建上下文文本
        context_text = "暂无"
        # 默认上下文文本
        if retrieved:
            # 如果有检索结果
            context_text = "\n".join(
                # 格式化检索结果为编号列表
                f"{idx + 1}. {item.get('answer', '')[:300]}"
                # 使用答案文本的前300个字符
                for idx, item in enumerate(retrieved[:4])
                # 最多使用4条检索结果
            )

        # 4. 构建提示词（Prompt）
        prompt = (
            # 组合角色的系统提示词、短期记忆、检索结果和用户问题
            f"{avatar.get('prompt', '你是一位专业助手。')}\n\n"
            # 角色系统提示词
            f"【短期记忆】\n{memory_context or '暂无'}\n\n"
            # 短期记忆（最近对话历史）
            f"【长期记忆 / Milvus 知识召回】\n{context_text}\n\n"
            # 长期记忆（向量检索结果）
            f"【用户问题】\n{question}"
            # 用户当前问题
        )

        # 5. 调用LLM生成回答
        if self.use_mock or self.llm_client is None:
            # 如果是mock模式或LLM客户端不可用
            answer = self._mock_avatar_reply(avatar_id, question, retrieved)
            # 使用模拟回复
        else:
            # 如果是真实模式
            try:
                answer = self.llm_client.call_llm(prompt)
                # 调用真实LLM生成回答
            except Exception as exc:
                # 如果调用失败
                logger.exception("LLM 调用失败: %s", exc)
                # 记录异常日志
                answer = f"暂时无法完成回答，请稍后重试。你的问题是：{question}"
                # 返回降级回复

        # 6. 优化输出格式
        answer = self.output_optimizer.optimize(answer, question, retrieved)
        # 使用输出优化器对LLM回答进行后处理（格式化、去重等）

        # 7. 将回答添加到短期记忆
        memory.add("assistant", answer, {"avatar_id": avatar_id})
        # 将AI回答添加到短期记忆中
        self._persist_short_memory(session_id)
        # 将短期记忆持久化到Redis

        # 8. 保存聊天记录到MySQL
        try:
            self.mysql_manager.save_chat_message(session_id, username, avatar_id, "user", question, 0)
            # 保存用户消息到数据库
            self.mysql_manager.save_chat_message(session_id, username, avatar_id, "assistant", answer, 0)
            # 保存AI回答到数据库
            self.mysql_manager.update_session(session_id, username, avatar_id)
            # 更新会话信息
        except Exception as exc:
            # 如果写入失败
            logger.warning("聊天记录写入失败: %s", exc)
            # 记录警告日志（不阻塞主流程）

        # 9. 返回结果
        return {
            # 返回聊天结果
            "success": True,
            # 成功标志
            "avatar_id": avatar_id,
            # 当前角色ID
            "answer": answer,
            # AI生成的回答
            "retrieved_count": len(retrieved),
            # 检索到的相关文档数量
            "retrieval_modes": retrieval["modes"],
            # 使用的检索模式
            "short_memory_backend": "redis" if getattr(self.redis_client, "enabled", False) else "in-memory",
            # 短期记忆后端类型
            "top_hits": retrieved[:3],
            # 前3个检索结果
        }

    def register_user(self, username, email="", password=""):
        # 定义方法：注册新用户

        """
        注册新用户

        参数:
            username: 用户名
            email: 邮箱
            password: 密码

        返回:
            dict: 注册结果
        """
        return self.user_manager.register_user(username, email, password)
        # 委托给UserManager处理

    def login_user(self, username, password=""):
        # 定义方法：用户登录

        """
        用户登录

        参数:
            username: 用户名
            password: 密码

        返回:
            dict: 登录结果
        """
        return self.user_manager.login_user(username, password)
        # 委托给UserManager处理

    def set_user_avatar(self, username, avatar_id):
        # 定义方法：设置用户的默认角色

        """
        设置用户的默认角色

        参数:
            username: 用户名
            avatar_id: 角色ID
        """
        return self.user_manager.set_user_avatar(username, avatar_id)
        # 委托给UserManager处理


def init_system(runtime_config=None):
    # 定义全局函数：初始化RAG系统

    """
    初始化全局RAG系统

    参数:
        runtime_config: 运行时配置字典
    """
    global rag_system, system_ready, system_error
    # 声明使用全局变量

    runtime_config = runtime_config or {
        # 如果未传入配置，使用默认配置
        "user_data_file": USER_DATA_FILE,
        # 用户数据文件路径
        "bge_m3_path": BGE_M3_PATH,
        # BGE-M3模型路径
        "bge_reranker_path": BGE_RERANKER_PATH,
        # BGE重排序模型路径
    }

    try:
        rag_system = SimpleRAGSystem(runtime_config)
        # 创建RAG系统实例
        system_ready = True
        # 标记系统就绪
        system_error = ""
        # 清空错误信息
        logger.info("系统初始化完成")
        # 记录成功日志
    except Exception as exc:
        # 如果初始化失败
        rag_system = None
        # 系统实例设为None
        system_ready = False
        # 标记系统未就绪
        system_error = str(exc)
        # 记录错误信息
        logger.exception("系统初始化失败: %s", exc)
        # 记录异常日志


def get_system_state():
    # 定义函数：获取系统状态

    """
    获取系统状态

    返回:
        dict: 包含RAG系统实例、就绪状态和错误信息的字典
    """
    return {
        "rag_system": rag_system,
        # RAG系统实例（可能为None）
        "system_ready": system_ready,
        # 系统是否就绪
        "system_error": system_error,
        # 系统错误信息
    }
