# ADSD 多角色对话系统 — 设计文档

## 1. 项目概述

**ADSD**（AI-Driven Student Development）是一个基于 RAG 检索增强生成的多角色对话 Web 系统。支持多用户登录、角色切换、语义检索、对话记忆、QPS 监控等特性。

## 2. 系统架构

```
┌─────────────────────────────────────────────────────┐
│                   用户浏览器                          │
│               (chat.html / login.html)               │
└──────────────────┬──────────────────────────────────┘
                   │ HTTP/JSON
                   ▼
┌─────────────────────────────────────────────────────┐
│              Flask Web 服务 (app_routes.py)            │
│   ┌─────────┐  ┌──────────┐  ┌──────────────────┐   │
│   │ 页面路由 │  │  API路由  │  │ QPS 监控中间件    │   │
│   │ / /chat  │  │ /api/*   │  │ before_request   │   │
│   └─────────┘  └────┬─────┘  │ after_request    │   │
│                      │        └──────────────────┘   │
└──────────────────────┼──────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────┐
│            SimpleRAGSystem (app_services.py)           │
│                                                       │
│   ┌──────────┐  ┌──────────┐  ┌─────────────────┐   │
│   │ chat()   │  │ 检索管道  │  │ 性能/压力测试     │   │
│   │ 对话流程  │  │ 多路召回  │  │ 综合测试         │   │
│   └────┬─────┘  └────┬─────┘  └─────────────────┘   │
│        │              │                               │
└────────┼──────────────┼──────────────────────────────┘
         │              │
         ▼              ▼
┌──────────────┐  ┌────────────────────────┐
│ LLMClient    │  │ HybridRetriever        │
│ (llm_client) │  │ (hybrid_retriever)     │
│              │  │                        │
│ Kimi API     │  │ BM25 + TF-IDF + 向量   │
│ 负载均衡     │  │ RRF融合 + BGE Rerank  │
│ 故障转移     │  │                        │
└──────┬───────┘  └───────────┬────────────┘
       │                      │
       ▼                      ▼
┌──────────────┐  ┌────────────────────────┐
│ RateLimiter  │  │ BGMManager (bge_manager)│
│ (rate_limiter)│  │                        │
│ 滑动窗口限流  │  │ BGE-M3 嵌入            │
└──────────────┘  │ BGE-Reranker 重排序     │
                  └───────────┬────────────┘
                              │
                              ▼
                 ┌────────────────────────┐
                 │  MilvusManager          │
                 │  (milvus_manager)       │
                 │  QA 向量库检索          │
                 └────────────────────────┘

┌─────────────────────────────────────────────────────┐
│                   数据层                              │
│   ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐   │
│   │ MySQL  │  │ Redis  │  │Milvus │  │本地JSON│   │
│   │历史记录│  │短期记忆│  │向量库  │  │用户数据 │   │
│   │用户行为│  │缓存    │  │QA索引  │  │知识库  │   │
│   └────────┘  └────────┘  └────────┘  └────────┘   │
└─────────────────────────────────────────────────────┘
```

## 3. 模块分解

### 3.1 在线模块（online/）

| 模块 | 职责 | 关键类/函数 |
|------|------|-------------|
| `main.py` | Flask 启动 | `create_app()`, `main()` |
| `config.py` | 配置加载 | `AVATARS` 字典, 环境变量 |
| `app_routes.py` | 路由注册 | `register_routes()`, 20+ API |
| `app_services.py` | RAG 核心 | `SimpleRAGSystem`, `chat()`, `search_knowledge_debug()` |
| `llm_client.py` | LLM 调用 | `LLMClient`, `call_llm()` |
| `bge_manager.py` | 嵌入/重排序 | `BGMManager`, `embed()`, `rerank()` |
| `hybrid_retriever.py` | 混合检索 | `HybridRetriever`, `bm25_search()`, `rrf` |
| `milvus_manager.py` | 向量检索 | `MilvusManager`, `vector_search()` |
| `session_manager.py` | 会话管理 | `SessionManager`, 线程安全字典 |
| `user_manager.py` | 用户管理 | `UserManager`, 注册/登录 |
| `short_term_memory.py` | 短期记忆 | `ShortTermMemory`, 12轮对话 |
| `redis_manager.py` | Redis 封装 | `RedisManager`, 自动降级 |
| `mysql_manager.py` | MySQL 封装 | `MySQLManager`, 自动建表 |
| `rate_limiter.py` | 限流器 | `RateLimiter`, 滑动窗口 |
| `load_balancer.py` | 负载均衡 | `WeightedRoundRobinBalancer` |
| `output_optimizer.py` | 输出优化 | `LLMOutputOptimizer`, 去套话 |
| `app_monitor.py` | QPS 监控 | `QPSMonitor`, `choose_port()` |
| `app_text.py` | 文本工具 | `repair_text()`, 知识库加载 |
| `utils.py` | 通用工具 | 分词、余弦相似度、向量降维 |

### 3.2 离线模块（offline/）

| 模块 | 职责 |
|------|------|
| `runner.py` | 离线任务调度 |
| `specialized_data_processor.py` | 数据清洗与格式统一 |
| `vector_index_creator.py` | BGE-M3 向量化 + Milvus 索引构建 |
| `pdf_to_milvus.py` | PDF 解析 → 问答生成 → 向量入库 |
| `analyze_processed_data.py` | 数据质量分析 |
| `check_port.py` | 依赖服务端口检查 |

## 4. 核心数据流

### 4.1 对话请求

```
用户 POST /api/chat
  → 会话验证 (session_manager)
  → SimpleRAGSystem.chat()
     ├─ 1. 短期记忆追加用户问题
     ├─ 2. 检索管道（角色知识优先）
     │    ├─ BM25 检索
     │    ├─ TF-IDF 检索
     │    ├─ 向量检索 (BGE-M3 → Milvus)
     │    ├─ RRF 融合排序
     │    └─ BGE Reranker 重排序
     ├─ 3. 构建 Prompt（角色提示 + 记忆 + 检索结果）
     ├─ 4. LLM 调用 (Kimi API)
     │    ├─ 限流检查
     │    ├─ 负载均衡选端点
     │    └─ 故障转移
     ├─ 5. 输出优化（去套话、截断）
     ├─ 6. 短期记忆持久化 (Redis)
     ├─ 7. 聊天记录入库 (MySQL)
     └─ 8. 返回 JSON 响应
```

### 4.2 离线数据流程

```
源数据 (JSONL/JSON/PDF)
  → specialized_data_processor.py → 统一格式
  → vector_index_creator.py → BGE-M3 向量化 → Milvus 入库
  → Redis 缓存 (前 500 条)
  → 本地 JSON/CSV 备份

PDF 专属流程：
  → pdf_to_milvus.py → pdfplumber 解析 → 按课文分篇
  → 生成问答对 → 向量化 → Milvus 去重插入
```

## 5. 角色设计

| 角色 ID | 名称 | 方向 | 检索来源 |
|---------|------|------|---------|
| doctor | 医生 | 健康建议、症状分析 | 通用知识库 |
| psychologist | 心理医生 | 情绪疏导、压力陪伴 | 通用知识库 |
| marketer | 营销专家 | 品牌增长、内容策划 | 通用知识库 |
| chinese_teacher | 语文老师 | 课文讲解、文言文 | 专属知识库 (26篇课文) |

## 6. 降级策略

| 服务不可用 | 降级行为 |
|-----------|---------|
| Kimi API | mock 模式 → 返回预设回答 |
| BGE 模型 | MD5 哈希伪向量 + 简单向量 128 维 |
| Milvus | 仅使用本地 BM25/TF-IDF 检索 |
| Redis | 内存短期记忆（不持久化） |
| MySQL | 日志记录跳过，功能不受影响 |

## 7. 部署架构

```
硬件需求:
  - GPU: 建议 8GB+ VRAM (BGE-M3 推理)
  - 内存: 建议 16GB+
  - 存储: 10GB+ (模型 + 数据)

依赖服务:
  - Milvus 2.3+: 向量数据库
  - Redis 7+: 缓存/会话
  - MySQL 8+: 持久化 (可选)
  - Kimi API: LLM 对话
