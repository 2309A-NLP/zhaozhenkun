# ADSD — 多角色对话系统

**AI-Driven Student Development**（自适应学习系统）

一个基于 RAG（检索增强生成）的多角色对话 Web 应用，支持多用户登录、角色切换、语义检索。

---

## 功能特性

- 🎭 **4 种预设角色**：医生、心理医生、营销专家、语文老师
- 🔐 **多用户登录/注册**：独立的会话管理
- 🧠 **RAG 检索增强**：BGE-M3 语义向量 + Milvus 向量数据库
- 🔄 **混合检索**：稠密向量 + 稀疏检索
- 📊 **QPS 监控**、负载均衡、性能测试面板
- 📄 **PDF 导入**：离线数据预处理支持

## 技术栈

| 组件 | 用途 |
|------|------|
| Flask | Web 框架 |
| Kimi API (Moonshot) | LLM 对话生成 |
| BGE-M3 / BGE-Reranker | 向量嵌入 & 重排序 |
| Milvus | 向量数据库 |
| Redis | 缓存 & 会话 |
| MySQL | 持久化存储 |

## 快速开始

### 1. 克隆

```bash
git clone https://github.com/你的用户名/multi-user-dialogue-system.git
cd multi-user-dialogue-system
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入你的 API Key 和数据库密码
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 下载模型

将 BGE-M3 和 BGE-Reranker 模型放入 `models/` 目录：

```
models/
├── bge-m3/
└── bge-reranker-base/
```

### 5. 启动服务

```bash
# 确保 Milvus、Redis 已启动

# 启动 Web 服务
python main.py online

# 或离线处理数据
python main.py offline processor
python main.py offline index
```

访问 `http://localhost:5010` 即可使用。

## 项目结构

```
multi-user-dialogue-system/
├── main.py              # 入口
├── online/              # Web 服务
│   ├── config.py        # 配置
│   ├── app_routes.py    # 路由 & API
│   ├── app_services.py  # RAG 系统
│   ├── llm_client.py    # LLM 调用
│   ├── bge_manager.py   # BGE 嵌入
│   └── templates/       # 前端页面
├── offline/             # 离线数据处理
└── processed_data/      # 处理后的数据集
```
