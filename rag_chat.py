# -*- coding: utf-8 -*-
import time  # 导入时间模块，用于计算耗时和性能统计
import threading  # 导入线程模块，用于异步执行数据库保存操作
from collections import deque  # 导入双端队列，用于存储最近N次的性能数据
from typing import List, Dict, Optional  # 导入类型提示，用于函数参数和返回值的类型注解
from datetime import datetime  # 导入日期时间模块，用于生成消息时间戳
import numpy as np  # 导入NumPy库，用于计算百分位数等统计值

from config import AVATARS  # 从配置文件导入角色配置字典
from utils import cosine_similarity_np  # 从工具模块导入余弦相似度计算函数
from short_term_memory import ShortTermMemory  # 导入短时记忆模块，用于管理会话上下文
from output_optimizer import LLMOutputOptimizer  # 导入输出优化器，用于优化大模型回答
from hybrid_retriever import HybridRetriever  # 导入混合检索器，支持向量+BM25+TF-IDF融合
from bge_manager import BGMManager  # 导入BGE管理器，用于文本向量化和重排序
from milvus_manager import MilvusManager  # 导入Milvus管理器，用于向量数据库操作
from user_manager import UserManager  # 导入用户管理器，处理用户注册、登录等
from llm_client import LLMClient  # 导入大模型客户端，用于调用LLM API
from mysql_manager import MySQLManager  # 导入MySQL管理器，用于持久化存储聊天记录
from redis_manager import RedisManager  # 导入Redis管理器，用于缓存和会话管理


class SimpleRAGChat:
    """RAG聊天系统核心类"""  # 类的文档字符串

    def __init__(self, config: dict, device: str):
        """初始化RAG聊天系统，接收配置和计算设备"""
        self.device = device  # 计算设备（cpu/cuda），用于BGE模型
        self.config = config  # 配置字典，包含所有组件配置
        self.use_mock = True  # 是否使用模拟模式（LLM不可用时自动启用）
        self.vector_dim = 1024  # 向量维度，BGE模型输出1024维向量

        # 初始化各组件
        self.mysql_manager = MySQLManager({  # 初始化MySQL管理器
            "host": config["mysql_host"],  # MySQL主机地址
            "port": config["mysql_port"],  # MySQL端口
            "user": config["mysql_user"],  # MySQL用户名
            "password": config["mysql_password"],  # MySQL密码
            "database": config["mysql_database"],  # 数据库名称
            "enabled": config["mysql_enabled"]  # 是否启用MySQL
        })

        # 初始化 Redis
        self.redis_manager = RedisManager(  # 创建Redis管理器实例
            host=config.get("redis_host", "localhost"),  # Redis主机，默认localhost
            port=config.get("redis_port", 6379),  # Redis端口，默认6379
            password=config.get("redis_password", None)  # Redis密码，可选
        )
        self.redis_manager.connect()  # 连接到Redis服务器

        self.user_manager = UserManager(config["user_data_file"], self.mysql_manager)  # 用户管理器
        self.milvus_manager = MilvusManager(config["milvus_hosts"], config["milvus_port"])  # Milvus向量数据库管理器
        self.llm_client = LLMClient()  # 大模型客户端
        self.hybrid_retriever = HybridRetriever()  # 混合检索器
        self.output_optimizer = LLMOutputOptimizer()  # 输出优化器

        # 初始化BGE
        self.bge_manager = None  # BGE管理器实例，稍后初始化
        self.short_term_memory = {}  # 短时记忆字典，key为"uid:avatar"，value为ShortTermMemory对象

        # 统计
        self.search_times = deque(maxlen=100)  # 搜索耗时队列，最多保留100条
        self.embed_times = deque(maxlen=100)  # 向量化耗时队列，最多保留100条
        self.hybrid_document_count = 0  # 混合检索文档总数

        # 初始化
        self._init_components()  # 调用组件初始化方法

    def _init_components(self):
        """初始化所有组件"""  # 私有方法文档
        self.user_manager = UserManager(self.config["user_data_file"], self.mysql_manager)  # 重新初始化用户管理器
        self.milvus_manager.connect()  # 连接Milvus数据库

        from bge_manager import load_bge_models  # 从bge_manager导入模型加载函数
        load_bge_models(self.config, self.device)  # 加载BGE模型到指定设备

        # 初始化BGMManager
        from bge_manager import bge_model  # 导入已加载的模型实例
        if bge_model:  # 如果模型加载成功
            self.bge_manager = BGMManager(self.device, self.vector_dim)  # 创建BGE管理器

        # 初始化LLM
        self.llm_client.init_llm(  # 初始化大模型客户端
            self.config["kimi_api_key"],  # 主要API密钥
            self.config["kimi_base_url"],  # 主要API基础URL
            self.config["kimi_model"],  # 主要模型名称
            self.config.get("kimi_api_keys", []),  # 多个API密钥（负载均衡）
            self.config.get("kimi_base_urls", []),  # 多个API URL（负载均衡）
            self.config.get("kimi_models", [])  # 多个模型名称（负载均衡）
        )
        self.use_mock = self.llm_client.use_mock  # 同步模拟模式状态

        # 初始化混合检索索引
        self._init_hybrid_index()  # 调用混合检索索引初始化

    def _init_hybrid_index(self):
        """初始化混合检索索引"""  # 私有方法文档
        if self.milvus_manager.collection is None:  # 如果Milvus集合未连接
            return  # 直接返回
        try:
            docs = self.milvus_manager.collection.query(  # 从Milvus查询所有文档
                expr="",  # 空表达式表示查询全部
                output_fields=["question", "answer", "source"],  # 需要返回的字段
                limit=10000  # 最多返回10000条文档
            )
            from utils import generate_doc_id  # 导入文档ID生成函数
            original = [{  # 转换为原始文档格式
                "question": d.get("question", ""),  # 问题文本
                "answer": d.get("answer", ""),  # 答案文本
                "source": d.get("source", "milvus"),  # 来源标识
                "doc_id": generate_doc_id(d.get("question", ""), d.get("answer", ""))  # 生成唯一文档ID
            } for d in docs if d.get("question") or d.get("answer")]  # 只保留有内容文档
            self.hybrid_retriever.build_index(original)  # 构建BM25和TF-IDF索引
            self.hybrid_document_count = len(original)  # 记录文档数量
            print(f"✅ 混合检索索引构建完成 | 文档数: {len(original)}")  # 打印成功信息
        except Exception as e:  # 捕获异常
            print(f"⚠️ 混合检索索引失败: {e}")  # 打印警告信息

    def _get_memory(self, uid: str, avatar: str) -> ShortTermMemory:
        """获取或创建用户的短时记忆实例"""
        key = f"{uid}:{avatar}"  # 组合key，格式"用户ID:角色ID"
        if key not in self.short_term_memory:  # 如果key不存在
            self.short_term_memory[key] = ShortTermMemory()  # 创建新的短时记忆对象
        return self.short_term_memory[key]  # 返回短时记忆实例

    def search_knowledge(self, query: str, top_k: int = 5, use_hybrid: bool = True) -> List[Dict]:
        """知识检索主方法，支持纯向量检索和混合检索"""
        if not query.strip() or self.milvus_manager.collection is None:  # 查询为空或Milvus未连接
            return []  # 返回空列表

        start_time = time.time()  # 记录检索开始时间
        qv = self.bge_manager.embed(query) if self.bge_manager else []  # 将查询文本向量化
        vector_results = self.milvus_manager.vector_search(qv, top_k * 6) if qv else []  # 向量检索（取6倍数量用于后续过滤）

        if not use_hybrid or not self.hybrid_retriever.bm25_index:  # 不使用混合检索或BM25索引不存在
            results = self._rerank(query, self._cosine_filter(query, vector_results, top_k * 2), top_k)  # 仅向量检索+余弦过滤+重排序
        else:  # 使用混合检索
            bm25 = self.hybrid_retriever.bm25_search(query, top_k * 3)  # BM25检索（3倍数量）
            tfidf = self.hybrid_retriever.tfidf_search(query, top_k * 3)  # TF-IDF检索（3倍数量）
            fused = self.hybrid_retriever.reciprocal_rank_fusion(  # 倒数排名融合（RRF）
                {"vector": vector_results, "bm25": bm25, "tfidf": tfidf}  # 三种检索结果融合
            )
            results = self._rerank(query, self._cosine_filter(query, fused, top_k * 2), top_k)  # 余弦过滤+重排序

        self.search_times.append((time.time() - start_time) * 1000)  # 记录本次检索耗时（毫秒）
        return results  # 返回最终结果

    def _cosine_filter(self, query: str, candidates: List[Dict], keep_top: int) -> List[Dict]:
        """余弦相似度过滤，保留与查询语义相似度高的文档"""
        if not candidates or not self.bge_manager:  # 无候选文档或BGE不可用
            return candidates[:keep_top]  # 直接返回前keep_top个

        qv = self.bge_manager.embed(query)  # 查询向量化
        kept, backup = [], []  # kept保留高相似度文档，backup保留低相似度文档
        for item in candidates:  # 遍历候选文档
            # 将问题和答案拼接并截取前1200字符用于向量化
            cv = self.bge_manager.embed(f"{item.get('question', '')}\n{item.get('answer', '')}"[:1200])
            cosine = cosine_similarity_np(qv, cv)  # 计算余弦相似度
            item["cosine_score"] = cosine  # 存储余弦分数
            (kept if cosine >= 0.20 else backup).append(item)  # 分数>=0.20放kept，否则放backup

        kept.sort(key=lambda x: x["cosine_score"], reverse=True)  # keept按余弦分数降序排序
        backup.sort(key=lambda x: x["cosine_score"], reverse=True)  # backup按余弦分数降序排序

        if len(kept) < keep_top:  # 如果kept数量不足keep_top
            kept.extend(backup[:keep_top - len(kept)])  # 从backup补充到keep_top
        return kept[:keep_top]  # 返回前keep_top个

    def _rerank(self, query: str, results: List[Dict], top_k: int) -> List[Dict]:
        """使用BGE模型对检索结果进行重排序"""
        if self.bge_manager:  # 如果BGE管理器可用
            return self.bge_manager.rerank(query, results, top_k)  # 调用BGE重排序
        return results[:top_k]  # 不可用则直接截取前top_k个

    def _mock_avatar_reply(self, avatar_id: str, question: str, context: List[Dict]) -> str:
        """模拟角色回复（当LLM不可用时使用）"""
        ref = f"\n参考：{context[0].get('answer', '')[:120]}" if context else ""  # 格式化参考内容
        replies = {  # 不同角色的模拟回复模板
            "doctor": f"从“{question[:60]}”来看，建议确认症状持续时间和强度，必要时就医。{ref}",  # 医生回复模板
            "psychologist": f"我理解你的感受。试着把困扰拆解一下，我们慢慢聊。{ref}",  # 心理医生回复模板
            "marketer": f"建议先明确目标人群和核心卖点，再确定渠道和内容。{ref}"  # 市场营销回复模板
        }
        return replies.get(avatar_id, f"收到你的问题：{question[:60]}。{ref}").strip()  # 获取对应回复，默认通用回复

    def chat(self, uid: str, avatar_id: str, question: str, msgs: List[Dict]) -> Dict:
        """主聊天方法，处理用户问题并返回回答"""
        avatar = AVATARS[avatar_id]  # 获取角色配置
        mem = self._get_memory(uid, avatar_id)  # 获取短时记忆
        mem.add("user", question)  # 将用户问题加入记忆

        start_time = time.time()  # 记录检索开始时间
        retrieved = self.search_knowledge(question, top_k=4)  # 检索知识，返回最相关4条
        search_time = (time.time() - start_time) * 1000  # 计算检索耗时（毫秒）

        ctx = "\n".join(f"{i + 1}. {item.get('answer', '')[:320]}"  # 格式化参考知识，每条截取320字符
                        for i, item in enumerate(retrieved[:4])) or "暂无相关参考知识。"  # 无结果时显示默认提示

        prompt = f"""{avatar['prompt']}  # 构建LLM提示词，包含角色设定和规则

【规则】只回答当前问题，不扩展无关内容。  # 回答规则
【角色】{avatar['name']}  # 角色名称
【历史】{chr(10).join(f"用户: {m['content']}" for m in msgs[-6:]) or "暂无"}  # 最近6条历史消息
【参考】{ctx}  # 检索到的知识
【问题】{question}"""  # 用户当前问题

        llm_start = time.time()  # 记录LLM调用开始时间
        if self.use_mock:  # 如果是模拟模式
            raw = self._mock_avatar_reply(avatar_id, question, retrieved)  # 生成模拟回复
        else:  # 真实模式
            raw = self.llm_client.call_llm(prompt)  # 调用大模型API
        llm_time = (time.time() - llm_start) * 1000  # 计算LLM耗时（毫秒）

        answer = self.output_optimizer.optimize(raw, question, retrieved)  # 优化输出（去冗余、加参考）
        mem.add(avatar["name"], answer)  # 将助手回答加入短时记忆
        now = datetime.now().isoformat()  # 生成当前时间戳（ISO格式）

        # 异步保存到MySQL
        def save_to_mysql():  # 定义异步保存函数
            try:
                username = uid.split(":")[0] if ":" in uid else uid  # 从uid提取用户名
                self.mysql_manager.save_chat_message(uid, username, avatar_id, "user", question,
                                                     int(search_time + llm_time))  # 保存用户消息
                self.mysql_manager.save_chat_message(uid, username, avatar_id, "assistant", answer, int(llm_time))  # 保存助手回复
                self.mysql_manager.update_session(uid, username, avatar_id)  # 更新会话信息
            except Exception as e:  # 捕获异常
                pass  # 静默失败，不影响主流程

        threading.Thread(target=save_to_mysql, daemon=True).start()  # 启动守护线程异步保存数据

        return {  # 返回聊天响应
            "success": True,  # 请求成功标志
            "avatar_id": avatar_id,  # 角色ID
            "avatar_name": avatar["name"],  # 角色名称
            "icon": avatar["icon"],  # 角色图标
            "color": avatar["color"],  # 角色主题颜色
            "answer": answer,  # 最终回答
            "messages": msgs + [  # 更新后的消息列表
                {"role": "user", "content": question, "timestamp": now},  # 用户消息
                {"role": "assistant", "content": answer, "timestamp": now}  # 助手消息
            ],
            "retrieved_count": len(retrieved),  # 检索到的知识数量
            "load_balancer_endpoint": self.llm_client.last_balancer_endpoint  # 使用的LLM端点
        }

    # 代理方法
    def register_user(self, username: str, email: str = "", password: str = "") -> Dict:
        """注册用户（代理到UserManager）"""
        return self.user_manager.register_user(username, email, password)  # 调用用户管理器的注册方法

    def login_user(self, username: str, password: str = "") -> Dict:
        """用户登录（代理到UserManager）"""
        return self.user_manager.login_user(username, password)  # 调用用户管理器的登录方法

    def set_user_avatar(self, username: str, avatar_id: str) -> bool:
        """设置用户默认角色（代理到UserManager）"""
        return self.user_manager.set_user_avatar(username, avatar_id)  # 调用用户管理器的角色设置方法

    def get_user_avatar(self, username: str) -> str:
        """获取用户默认角色（代理到UserManager）"""
        return self.user_manager.get_user_avatar(username)  # 调用用户管理器的角色获取方法

    def get_performance_stats(self) -> Dict:
        """获取系统性能统计（搜索耗时、向量化耗时）"""
        search_times = list(self.search_times)  # 将双端队列转为列表
        embed_times = list(self.embed_times)  # 将双端队列转为列表
        return {  # 返回统计字典
            "search": {  # 检索性能统计
                "avg": round(np.mean(search_times), 2) if search_times else 0,  # 平均耗时
                "p95": round(np.percentile(search_times, 95), 2) if search_times else 0,  # 95分位数
                "p99": round(np.percentile(search_times, 99), 2) if search_times else 0,  # 99分位数
                "count": len(search_times)  # 统计样本数
            },
            "embed": {  # 向量化性能统计
                "avg": round(np.mean(embed_times), 2) if embed_times else 0,  # 平均耗时
                "p95": round(np.percentile(embed_times, 95), 2) if embed_times else 0,  # 95分位数
                "count": len(embed_times)  # 统计样本数
            }
        }