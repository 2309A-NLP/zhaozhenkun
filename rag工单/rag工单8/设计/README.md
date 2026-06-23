# RAG工单8 — GraphRAG金融问答系统

> **工单编号**: 人工智能NLP-RAG-基于Graph RAG 实现金融问答  
> **项目版本**: V1.0  
> **数据来源**: CCF竞赛金融年报数据集（平安银行、招商银行、中国平安、中国人寿等9份年报）

---

## 一、系统架构

```
┌─────────────────────────────────────────────────────┐
│                   用户界面                            │
│         🌐 Flask Web (index.html)                   │
│   文字输入 / 🎤 语音输入 / 中英文切换               │
│   知识图谱D3.js可视化 / 评估报告展示                  │
└────────────────────────┬────────────────────────────┘
                         │ HTTP REST API
┌────────────────────────▼────────────────────────────┐
│                   业务层                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │pdf_parser│→ │text_     │→ │   embedder       │   │
│  │PDF解析   │  │chunker   │  │  BGE-M3向量化    │   │
│  └──────────┘  │文本分块   │  └────────┬─────────┘   │
│                 └──────────┘           │              │
│  ┌──────────┐  ┌──────────┐           ▼              │
│  │entity_   │  │graph_    │  ┌──────────────────┐   │
│  │graph_    │← │retriever │← │milvus_handler    │   │
│  │builder   │  │混合检索  │  │Milvus向量库      │   │
│  │知识图谱  │  └──────────┘  └──────────────────┘   │
│  └──────────┘                                        │
│  ┌──────────┐  ┌──────────┐                          │
│  │qa_       │  │evaluator │                          │
│  │generator │  │LLM评估   │                          │
│  │问答生成  │  │+报告     │                          │
│  └──────────┘  └──────────┘                          │
└──────────────────────────────────────────────────────┘
```

## 二、技术选型

| 模块 | 技术 | 说明 |
|------|------|------|
| PDF解析 | PyMuPDF (fitz) | 解析CCF竞赛金融年报PDF，支持超大文档 |
| 文本分块 | 自定义重叠切片 | 300字/块，50字重叠，保持上下文连贯 |
| 向量模型 | **BGE-M3** (本地) | 1024维稠密向量，FP16半精度，batch=2 |
| 向量库 | **Milvus** (IVF_FLAT) | 12968向量快速检索，IP内积度量 |
| 知识图谱 | **NetworkX** + DeepSeek | 实体/关系提取，BFS扩展2跳 |
| 大模型 | **DeepSeek Chat** | 实体提取 + 问答生成 + LLM评估 |
| 问答引擎 | DeepSeek API | 基于检索上下文生成金融分析回答 |
| Web框架 | Flask + D3.js | 问答界面 + 力导向图谱可视化 |
| 语音输入 | Web Speech API | 浏览器原生语音识别(Chrome/Edge) |
| 评估 | LLM智能评分 | 4维度：相关性/完整性/准确性/流畅性 |

## 三、开发流程

### 3.1 环境要求

- Python 3.10+
- Milvus 2.3+（Docker运行）
- GPU 8GB+（BGE-M3推理）
- 浏览器 Chrome/Edge（语音输入）

### 3.2 安装

```bash
# 启动Milvus
docker start milvus-etcd milvus-minio milvus-standalone

# 安装依赖
pip install PyMuPDF pymilvus sentence-transformers openai flask flask-cors networkx
```

### 3.3 运行

```bash
cd /mnt/c/Users/31326/Desktop/rag工单8

# 完整流程（解析→入库→检索→评估→Web）
python3 run.py

# 测试模式（前2题快速验证）
python3 run.py --test

# 强制重建所有数据
python3 run.py --rebuild

# 仅启动Web界面
python3 run.py --web-only
```

## 四、模块说明

| 模块 | 文件 | 行数 | 职责 |
|------|------|:----:|------|
| 配置中心 | config.py | 87 | 路径/API/模型/Milvus参数统一管理 |
| PDF解析 | pdf_parser.py | 132 | 解析CCF年报+提取测试问题 |
| 文本分块 | text_chunker.py | 104 | 300字重叠切片，带来源追踪 |
| 向量嵌入 | embedder.py | 120 | BGE-M3加载/编码/批处理 |
| Milvus操作 | milvus_handler.py | 162 | 集合/索引/插入/搜索/删除 |
| 图谱构建 | entity_graph_builder.py | 162 | DeepSeek实体提取+NetworkX图 |
| 混合检索 | graph_retriever.py | 189 | 向量检索+图谱BFS扩展融合 |
| 问答生成 | qa_generator.py | 106 | DeepSeek金融问答上下文组装 |
| LLM评估 | evaluator.py | 146 | 4维度评分+关键词降级+HTML报告 |
| Web界面 | app.py | 159 | Flask API+延迟初始化 |
| 前端页面 | templates/index.html | 285 | 问答/图谱/评估/语音/双语 |
| 主入口 | run.py | 147 | 协调全流程，调用所有子模块 |

## 五、数据流

```
① PDF解析 ──→ ② 分块 ──→ ③ BGE-M3向量化 ──→ ④ Milvus入库
                                        │
                             ⑤ DeepSeek实体提取
                                        │
                             ⑥ NetworkX知识图谱
                                        │
          ┌──────────────────────────────┤
          ▼                              ▼
   ⑦ 纯向量检索                    ⑧ GraphRAG混合检索
   (baseline)                      (向量+图谱扩展)
          │                              │
          └──────────────┬───────────────┘
                         ▼
                  ⑨ DeepSeek问答生成
                         │
                  ⑩ LLM评估对比
                         │
                  ⑪ Web展示 + 报告
```

## 六、评估结果

| 指标 | 纯向量 | GraphRAG | 变化 |
|------|:------:|:--------:|:----:|
| 相关性 | 9.00 | 9.00 | +0.00 |
| 完整性 | 7.50 | 7.50 | +0.00 |
| 准确性 | 8.50 | 8.50 | +0.00 |
| 流畅性 | 10.00 | 9.50 | -0.50 |
| 响应时间 | 14.25s | 11.98s | **-2.27s** |

> **说明**: 当前知识图谱仅处理前15个chunk（DeepSeek API成本控制），全量处理后可进一步提升检索质量。

## 七、使用方法

### 7.1 问答
1. 打开浏览器访问 `http://127.0.0.1:5008`
2. 在输入框输入金融相关问题
3. 勾选"启用图谱增强"使用GraphRAG模式
4. 点击"提问"或按回车

### 7.2 语音输入
1. 点击麦克风按钮 🎤
2. 浏览器会请求麦克风权限，点击"允许"
3. 直接说出问题（支持中文语音识别）
4. 说完后自动识别并提交问答

### 7.3 查看结果
- **知识图谱**: 右侧显示实体关系力导向图
- **评估对比**: 展示纯向量 vs GraphRAG分数
- **问答记录**: 底部表格显示历史问答

## 八、项目文件

```
rag工单8/
├── config.py                 # 全局配置
├── pdf_parser.py             # PDF解析
├── text_chunker.py           # 文本分块
├── embedder.py               # BGE-M3向量嵌入
├── milvus_handler.py         # Milvus向量库
├── entity_graph_builder.py   # 知识图谱构建
├── graph_retriever.py        # 混合检索
├── qa_generator.py           # 问答生成
├── evaluator.py              # LLM评估
├── app.py                    # Web服务
├── run.py                    # 主入口
├── templates/
│   └── index.html            # 前端页面
└── output/
    ├── chunks.json            # 分块数据
    ├── knowledge_graph.json   # 知识图谱
    ├── qa_results.json        # 问答结果
    ├── evaluation_before.json # 向量评估
    ├── evaluation_after.json  # GraphRAG评估
    ├── evaluation_summary.json# 评估摘要
    └── evaluation_report.html # 评估报告
```
