# Embedding 模型微调项目

## 项目概述

对 BGE-M3 嵌入模型进行 LoRA 微调，使其在招股说明书（金融领域）上的检索效果优于原始模型。

**工单编号:** 人工智能NLP-RAG项目-11-Embeddings模型微调任务V1.0
**工时:** 2人日
**目标:** 微调后Embedding检索效果 > 微调前，有数据指标支撑

## 项目结构

```
rag工单11/
├── run.py                 # 根入口（自动加载子目录到sys.path，调用run_all）
├── 设计/
│   ├── config.py          # 全局配置（模型路径/API/训练参数/评估参数）  ~140行
│   ├── README.md          # 本文件
│   └── 说明文档.txt        # 简要说明
├── 研发/
│   ├── data_prep.py       # PDF解析→文本切分→三元组构造              ~134行
│   ├── losses.py          # 损失函数（triplet/contrastive/cosine/matryoshka） ~130行
│   ├── trainer.py         # LoRA微调训练器                            ~183行
│   ├── mimo_api.py        # MiMo API（问答对生成+质量评分）           ~170行
│   └── chat_mimo.py       # MiMo交互式对话助手                        ~78行
├── 测试/
│   ├── evaluator.py       # 评估器（三元组+RAG检索+对比报告）        ~240行
│   ├── check_cuda.py      # CUDA环境检查
│   └── check_deps.py      # 依赖包检查
├── 部署/
│   ├── run_all.py         ★ 总入口（调用全部6个模块，5步流水线）      ~190行
│   ├── main.py            # 4步流水线（备用入口）
│   └── install_*.bat      # Windows安装脚本
├── 优化/
│   └── __init__.py
└── output/                # 所有产出物
    ├── data/              # 训练数据（三元组+问答对）
    ├── models/            # LoRA权重（checkpoint-XX/ + final/）
    └── eval/              # 评估报告
```

## 核心流程

```
PDF文档 → 文本切分 → 三元组构造 → MiMo问答对生成
  → 基线评估(三元组+RAG检索) → LoRA微调 → 微调后评估 → 对比报告
```

## 使用方法

```bash
# 完整流水线
python run_all.py

# 分步执行
python run_all.py --step 1   # 数据准备
python run_all.py --step 2   # 基线评估
python run_all.py --step 3   # LoRA微调训练
python run_all.py --step 4   # 微调后评估
python run_all.py --step 5   # 对比报告
```

## 评估指标

| 指标 | 说明 |
|------|------|
| Recall@K | 前K个结果中包含相关文档的比例 |
| MRR | 第一个相关文档排名的倒数均值 |
| 分离度 | 正例相似度 - 负例相似度，越大越好 |
| RAG_Recall@K | 真实RAG检索场景的召回率 |
| RAG_MRR | 真实RAG检索场景的MRR |

## 损失函数

| 函数 | 适用场景 | 配置值 |
|------|----------|--------|
| Triplet Loss | (锚点,正例,负例)三元组 | triplet |
| Contrastive Loss | 正负例句子对 | contrastive |
| Cosine Similarity Loss | 带相似度分数的对 | cosine_sim |
| Matryoshka Loss | 可截断嵌入 | matryoshka |

## 验收标准

- 微调后Embedding检索指标 > 微调前（Recall@K ↑ / MRR ↑ / 分离度 ↑）
- 所有指标有JSON报告支撑
