# 医疗健康咨询 Agent — 架构设计文档

## 工单编号
人工智能NLP-Agent数字人项目-医疗智能体-健康咨询

## 系统架构

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  用户Query   │────▶│ EntityExtractor│────▶│   QueryIntent │
│ (自然语言)   │     │  (LLM few-shot) │     │ (疾病+类别)   │
└─────────────┘     └──────────────┘     └──────┬──────┘
                                                 │
                    ┌──────────────┐              │
                    │  LLM Answer  │◀─────────────┤
                    │  Generator   │              │
                    └──────┬───────┘     ┌───────┴──────┐
                           │             │CypherGenerator│
                           │             │ (15类模板)    │
                           │             └───────┬──────┘
                           │                     │
                           │             ┌───────┴──────┐
                           │             │ GraphQuery   │
                           │             │ (Neo4j/降级)  │
                           │             └───────┬──────┘
                           │                     │
                           ▼                     ▼
                    ┌─────────────────────────────────┐
                    │          AgentResponse           │
                    │  (答案 + Cypher + 图谱结果)      │
                    └─────────────────────────────────┘
```

## 知识图谱 Schema

```
(Disease) ──TREATED_BY──▶ (Department)
(Disease) ──USES_DRUG──▶ (Drug)
(Disease) ──HAS_COMPLICATION──▶ (Complication)
(Disease) ──TREATED_WITH──▶ (Treatment)
(Disease) ──HAS_SYMPTOM──▶ (Symptom)
(Disease) ──HAS_PREVENTION──▶ (Prevention)
(Disease) ──HAS_NURSING──▶ (Nursing)
(Disease) ──CAN_EAT──▶ (Food {type:"can_eat"})
(Disease) ──AVOID_EAT──▶ (Food {type:"not_eat"})
```

## 模块职责

| 模块 | 行数 | 职责 |
|------|------|------|
| kg_builder.py | 121 | JSONL 解析 (6143条) |
| kg_importer.py | 275 | Neo4j 批量导入 |
| entity_extractor.py | 281 | LLM 实体抽取 + 规则降级 |
| cypher_generator.py | 231 | 15类查询 → Cypher 映射 |
| graph_query.py | 208 | Neo4j 执行 + 本地降级 |
| llm_answer.py | 172 | LLM 答案生成 |
| agent.py | 182 | 4步主编排 |
| api.py | 192 | FastAPI 服务 |
| config.py | 136 | 配置加载 |
| models.py | 107 | 数据模型 |

## 数据流

1. 用户 Query → EntityExtractor (LLM) → QueryIntent {disease, category, keywords}
2. QueryIntent → CypherGenerator → Cypher 语句
3. Cypher → GraphQueryExecutor → Neo4j 图谱结果 (Neo4j不可用时降级JSONL)
4. {Query + Intent + 图谱结果} → LLMAnswerGenerator → 自然语言答案
5. AgentResponse → API → JSON 返回

## 容错策略

- Neo4j 不可用 → 自动降级到本地 medical.json 检索
- LLM API 不可用 → 规则抽取 + 模板答案
- 未识别疾病名 → 提示用户明确疾病
- 无效输入 → 返回友好错误提示
