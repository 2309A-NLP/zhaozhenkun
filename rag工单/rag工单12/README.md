# LightRAG 金融文档智能问答系统

## 项目概述

本项目基于 LightRAG（Lightweight Retrieval-Augmented Generation）框架，使用两份招股说明书 PDF 构建知识图谱，实现 RAG 与 LightRAG 双模式检索问答，并对比评估两种模式的性能差异。

- **工单编号**：人工智能NLP-RAG项目-12-LightRAG优化
- **创建时间**：2025年8月26日
- **创建人**：王洪荣
- **工时**：2人日

## 技术架构

```
rag工单12/
├── 设计/              # 设计层 — 全局配置
│   └── config.py      # 集中配置管理（模型路径、API密钥、参数常量）
├── 研发/              # 研发层 — 核心处理流水线
│   ├── pdf_parser.py      # PDF 解析（PyMuPDF）
│   ├── text_chunker.py    # 文本分块（重叠策略）
│   ├── embedder.py        # BGE-M3 向量编码（FP16/CUDA）
│   ├── llm_client.py      # MiMo API 封装（HTTP/重试）
│   ├── entity_extractor.py # LLM 实体关系提取（批量/去重）
│   ├── graph_builder.py   # 知识图谱构建（NetworkX/增量更新）
│   ├── retriever.py       # 双模式检索（RAG/LightRAG）
│   └── qa_generator.py    # 问答生成（上下文拼接/LLM生成）
├── 测试/              # 测试层 — 评估对比
│   ├── evaluator.py       # 综合评估（RAGAS + 4维LLM评分）
│   └── ragas_eval.py      # RAGAS 标准指标评估
├── 优化/              # 优化层 — 调优分析
│   └── optimizer.py       # 参数调优/缓存验证/耗时统计
├── 部署/              # 部署层 — 入口与展示
│   ├── 0_run.py           # 最终入口（Web对话/评估流水线）
│   ├── run.py             # 全流程评估流水线（8步）
│   ├── web_app.py         # Flask Web 对话界面
│   └── templates/         # HTML 模板
├── cache/             # 缓存目录（中间结果）
├── output/            # 输出目录（评估报告/图谱可视化）
├── 架构图.html        # 系统架构 SVG 图
└── 部署/run_full.bat  # Windows 一键启动脚本
```

## 技术栈

| 组件 | 技术 |
|------|------|
| PDF 解析 | PyMuPDF (fitz) |
| 嵌入模型 | BGE-M3 (sentence-transformers, FP16) |
| 知识图谱 | NetworkX (有向图) |
| LLM API | 小米 MiMo v2.5-pro (Token Plan) |
| Web 框架 | Flask |
| 可视化 | D3.js (力导向图) |
| 评估框架 | RAGAS + LLM 4维评分 |
| 硬件 | RTX 5060 8GB VRAM |

## 实现步骤

### 第一步：环境准备

```bash
pip install PyMuPDF sentence-transformers networkx flask numpy requests
pip install ragas langchain-openai datasets  # RAGAS 评估依赖
```

### 第二步：初始化数据

```bash
cd rag工单12/部署
python 0_run.py --pipeline --rebuild
```

流程自动执行 8 个步骤：
1. **PDF 解析** — 提取两份招股说明书的全部文本（约250页）
2. **文本分块** — 重叠策略切分（chunk_size=300, overlap=50）
3. **向量编码** — BGE-M3 FP16 编码（batch=2, max_seq=1024）
4. **实体提取** — MiMo API 批量提取（IPO 专用类型体系）
5. **图谱构建** — NetworkX 有向图（含增量更新能力）
6. **双模式检索** — RAG（纯向量）/ LightRAG（向量+图谱）
7. **问答生成** — 基于上下文调用 MiMo API 生成
8. **评估对比** — RAGAS + LLM 4维双评估体系

### 第三步：Web 对话

```bash
python 0_run.py                   # 默认启动 Web（端口5000）
python 0_run.py --port 8080       # 自定义端口
```

浏览器访问 `http://localhost:5000`，支持 RAG/LightRAG 一键切换。

## 测试问题

共16题，覆盖两份招股说明书：
- 招股说明书1（武汉力源信息）：6题 — ID: 1-6
- 招股说明书2（武汉兴图新科）：10题 — ID: 33, 95, 207, 260, 531, 543, 793, 795, 957

## 过程问题记录

### 问题1：BGE-M3 显存不足
- **现象**：batch_size=4 时 CUDA OOM（8GB显存）
- **原因**：BGE-M3 模型约2.2GB + 中间激活峰值占满显存
- **解决**：batch_size 降至 2，启用 FP16 半精度

### 问题2：LLM JSON 格式不稳定
- **现象**：实体提取返回格式不一致（有时是字符串而非对象）
- **原因**：MiMo API 的 temperature=0.1 仍有随机性
- **解决**：merge_extractions 中增加 str/dict/list 兼容处理

### 问题3：实体提取耗时过长
- **现象**：200 chunks 逐个提取约需15分钟 API 时间
- **原因**：单 chunk 提取导致 API 调用次数过多
- **解决**：实现批量提取（每批5个 chunk），减少 API 调用次数

### 问题4：图谱孤立节点过多
- **现象**：首次构建图谱密度 <0.01
- **原因**：实体提取 prompt 未针对招股书内容优化
- **解决**：重构实体/关系类型体系为 IPO 招股书专用分类

## 评估指标

### RAGAS 标准指标
- **Faithfulness**（忠实度）：回答是否忠于检索上下文
- **Answer Relevancy**（回答相关性）：回答是否切题
- **Context Precision**（上下文精准度）：检索信号噪声比
- **Context Recall**（上下文召回率）：检索覆盖完整性

### LLM 4维评分
- **相关性**（1-5）：是否紧扣问题
- **完整性**（1-5）：是否覆盖全部要点
- **准确性**（1-5）：信息是否准确
- **流畅性**（1-5）：语言表达质量

## 验收对照

| 验收项 | 状态 |
|--------|------|
| 实体类型/关系类型针对 PDF 内容优化 | ✅ IPO招股书专用16类实体 + 18类关系 |
| 16题 RAG vs LightRAG 检索对比 | ✅ 双模式检索 + 对比评估 |
| RAGAS 评估指标对比 | ✅ RAGAS 标准指标 + LLM 4维评分 |
| 知识图谱产出 | ✅ D3.js 交互式可视化 |
| 过程记录文档 | ✅ 本 README |
| 增量更新能力 | ✅ graph_builder.incremental_update() |
