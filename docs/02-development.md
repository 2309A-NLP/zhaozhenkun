# ADSD 多角色对话系统 — 研发文档

## 1. 开发环境配置

### 1.1 系统要求

| 组件 | 版本要求 | 说明 |
|------|---------|------|
| Python | 3.10+ | 推荐 3.10-3.12 |
| CUDA | 11.8+ | GPU 加速（可选） |
| Node.js | 18+ | 构建语文老师知识库 |

### 1.2 环境搭建

```bash
# 1. 克隆项目
git clone <repo-url>
cd multi-user-dialogue-system

# 2. 创建虚拟环境
python -m venv venv
# Windows: venv\Scripts\activate
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 Kimi API Key、数据库密码等

# 5. 下载 BGE 模型
# 从 ModelScope 下载:
# git clone https://www.modelscope.cn/BAAI/bge-m3.git models/bge-m3
# git clone https://www.modelscope.cn/BAAI/bge-reranker-v2-m3.git models/bge-reranker-base

# 6. 启动依赖服务
# Docker 方式（推荐）:
docker compose up -d milvus redis mysql
# 或本地安装后启动

# 7. 检查服务
python main.py offline check

# 8. 启动开发服务器
python main.py online
# 访问 http://localhost:5010
```

## 2. 项目结构

```
multi-user-dialogue-system/
├── main.py                          # 项目入口
├── requirements.txt                 # Python 依赖
├── .env.example                     # 环境变量模板
├── .gitignore                       # Git 忽略规则
├── README.md                        # 项目说明
│
├── online/                          # 在线服务模块
│   ├── __init__.py
│   ├── main.py                      # Flask 启动
│   ├── config.py                    # 配置（角色、数据库、模型）
│   ├── app_routes.py                # 路由 & API（690 行）
│   ├── app_services.py              # RAG 核心逻辑（1540 行 ★）
│   ├── app_text.py                  # 文本处理 & 知识库加载
│   ├── app_monitor.py               # QPS 监控
│   ├── bge_manager.py               # BGE 嵌入 & 重排序
│   ├── hybrid_retriever.py          # BM25 + TF-IDF 混合检索
│   ├── llm_client.py                # Kimi API 调用
│   ├── milvus_manager.py            # Milvus 向量检索
│   ├── session_manager.py           # 会话管理
│   ├── user_manager.py              # 用户注册/登录
│   ├── short_term_memory.py         # 短期对话记忆
│   ├── redis_manager.py             # Redis 缓存
│   ├── mysql_manager.py             # MySQL 持久化
│   ├── rate_limiter.py              # 限流器
│   ├── load_balancer.py             # LLM 端点负载均衡
│   ├── output_optimizer.py          # 输出优化
│   ├── utils.py                     # 通用工具函数
│   └── templates/                   # 前端模板
│       ├── login.html               # 登录页面
│       ├── chat.html                # 聊天页面
│       └── *dashboard.html          # 监控仪表盘
│
├── offline/                         # 离线数据处理
│   ├── __init__.py
│   ├── runner.py                    # 任务调度
│   ├── specialized_data_processor.py # 数据清洗
│   ├── vector_index_creator.py      # 向量索引构建
│   ├── pdf_to_milvus.py             # PDF 导入管道
│   ├── analyze_processed_data.py    # 数据分析
│   ├── check_port.py                # 端口检查
│   └── scripts/
│       └── build_chinese_teacher_knowledge.js
│
└── processed_data/                  # 处理后数据（gitignored）
    ├── chinese_teacher_vector_records.json
    └── avatar_knowledge/chinese_teacher.json
```

## 3. 开发规范

### 3.1 代码风格

- 使用 `# -*- coding: utf-8 -*-` 文件头
- 中文注释 + 每行后解释性注释
- 函数有文档字符串（docstring）
- 类型提示（Type Hints）可选但推荐

### 3.2 模块依赖原则

```
上层模块可以依赖下层，禁止循环依赖
app_routes.py → app_services.py → 各子模块
                                  → bge_manager
                                  → llm_client
                                  → milvus_manager
                                  → hybrid_retriever
                                  → session_manager
                                  → user_manager
                                  → ...
```

## 4. 核心模块开发说明

### 4.1 SimpleRAGSystem（app_services.py）

**初始化顺序：**
1. MySQLManager.connect() — MySQL 连接 + 建表
2. RedisManager.connect() — Redis 连接（失败则 enabled=False）
3. MilvusManager.connect() — Milvus 连接
4. load_bge_models() — BGE 模型加载
5. HybridRetriever.build_index() — 构建本地检索索引
6. LLMClient.init_llm() — LLM 连接测试
7. OutputOptimizer — 输出优化器初始化
8. UserManager — 用户管理器初始化

**重要：** 初始化在后台线程中异步执行（online/main.py 中 threading.Thread），不阻塞 Web 服务器启动。

### 4.2 检索管道

```
search_knowledge_debug(question, avatar_id)
  │
  ├─ 有角色知识库? ──→ BM25 检索角色知识
  │                    ├─ question 检索
  │                    └─ question×3 + answer 加权检索
  │                    └─ RRF 融合 → BGE Rerank → 结果
  │
  └─ 无角色知识库? ──→ 通用知识检索
                       ├─ BM25 (rank_bm25)
                       ├─ TF-IDF (sklearn TfidfVectorizer)
                       ├─ 向量检索 (BGE-M3 → Milvus)
                       ├─ RRF 融合 (k=60)
                       └─ BGE Reranker 重排序
```

### 4.3 LLM 调用流程

```
LLMClient.call_llm(prompt)
  ├─ RateLimiter.wait_if_needed() — 滑动窗口限流
  ├─ LoadBalancer.next() — 加权轮询选端点
  ├─ OpenAI client.create() — 调用 API
  │    └─ 失败时 → 故障转移：尝试下一个端点
  ├─ LoadBalancer.record_result() — 记录指标
  └─ LoadBalancer.release() — 释放连接计数
```

## 5. 数据库表结构

### MySQL

```sql
-- 聊天历史
CREATE TABLE chat_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(64),
    username VARCHAR(64),
    avatar_id VARCHAR(32),
    role VARCHAR(16),           -- 'user' | 'assistant'
    content TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session (session_id),
    INDEX idx_user (username, created_at)
);

-- 用户行为
CREATE TABLE user_actions (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(64),
    action VARCHAR(32),         -- 'login' | 'register' | 'switch_avatar'
    detail TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 会话
CREATE TABLE sessions (
    session_id VARCHAR(64) PRIMARY KEY,
    username VARCHAR(64),
    avatar_id VARCHAR(32),
    login_ip VARCHAR(45),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### Milvus

- 集合名: `qa_embeddings`
- 向量维度: 1024 (BGE-M3)
- 向量字段: `embedding` (FLOAT_VECTOR)
- 标量字段: `id`, `question`, `answer`, `source`
- 索引类型: IVF_FLAT / IP (内积)

### Redis

| Key 模式 | 用途 | 过期 |
|----------|------|------|
| `short_memory:{session_id}` | 短期记忆 | 24h |
| `embedding_cache:{hash}` | 向量缓存 | 1h |
| `hot_qa:{id}` | 热门问答 | 24h |

## 6. 角色新增指南

在 `config.py` 的 `AVATARS` 字典中添加新角色：

```python
"your_role_id": {
    "name": "角色显示名",
    "icon": "图标字",
    "color": "#十六进制色",
    "desc": "一句话描述",
    "welcome": "欢迎语",
    "prompt": "AI 系统提示词",
    "suggestions": ["示例问题1", "示例问题2", "示例问题3"],
}
```

如果需要专属知识库，在 `processed_data/avatar_knowledge/` 下放入 `{role_id}.json` 文件即可。
