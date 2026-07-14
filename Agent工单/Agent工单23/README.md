# Research Agent — 用 PAI-LangStudio 实现 Research Agent 工单

**项目编号**: 人工智能-Agent数字人-23  
基于阿里云天池算法大赛赛题，构建一个多步推理 Research Agent。  
禁止模型微调，仅凭 Agent 工程能力（规划、工具调用、提示词优化）。

---

## 项目结构

```
Agent工单23/
├── 设计/                    # 设计层
│   ├── prompts.py          # System Prompt 与提示词模板
│   └── __init__.py
├── 研发/                    # 研发层
│   ├── config.py           # 配置管理（API密钥、参数等）
│   ├── llm_client.py       # DeepSeek LLM 客户端
│   ├── search_tools.py     # 搜索工具（SerpAPI/DuckDuckGo）
│   ├── agent_core.py       # ReAct Agent 核心循环
│   └── __init__.py
├── 测试/                    # 测试层
│   ├── generate_answers.py # 批量答案生成器
│   └── __init__.py
├── 部署/                    # 部署层
│   ├── app.py              # PAI-EAS HTTP 服务
│   ├── requirements.txt    # Python 依赖
│   ├── Dockerfile          # Docker 镜像构建
│   └── __init__.py
├── 优化/                    # 优化层
│   ├── answer_normalizer.py # 答案归一化与质量评估
│   └── __init__.py
├── 23附件/                  # 竞赛数据
│   └── question.jsonl      # 100道评测题目
└── README.md               # 本文件
```

## 快速开始

### 1. 环境准备

```bash
# 安装依赖
pip install -r 部署/requirements.txt

# 设置环境变量（可选，也可使用 config.py 中的默认值）
export DEEPSEEK_API_KEY="sk-xxx"
export SERPAPI_API_KEY="xxx"  # 可选，用于增强搜索
```

### 2. 运行 HTTP 服务

```bash
# 启动服务（默认端口 8000）
python 部署/app.py

# API 调用示例
curl -X POST http://localhost:8000/api/answer \
  -H "Content-Type: application/json" \
  -d '{"id": 0, "question": "2024年巴黎奥运会的开幕式在哪个场馆举行？"}'
```

### 3. 批量生成答案

```bash
# 对 100 道题目批量生成答案
python 测试/generate_answers.py

# 指定题目范围（断点续传默认开启）
python 测试/generate_answers.py --start 0 --end 50

# 禁用断点续传
python 测试/generate_answers.py --no-resume
```

### 4. 自检测试

```bash
# 测试各模块是否正常
python 设计/prompts.py          # 提示词模块自检
python 研发/config.py           # 配置模块自检
python 研发/llm_client.py       # LLM 客户端连通性测试
python 研发/search_tools.py     # 搜索工具测试
python 研发/agent_core.py       # Agent 核心功能测试
python 优化/answer_normalizer.py # 答案归一化测试
```

## 配置说明

核心配置在 `研发/config.py` 中：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| DEEPSEEK_API_KEY | (已配置) | DeepSeek API 密钥 |
| DEEPSEEK_BASE_URL | https://api.deepseek.com | API 地址 |
| DEEPSEEK_MODEL | deepseek-chat | 模型名称 |
| SERPAPI_API_KEY | (需配置) | SerpAPI 密钥（搜索增强） |
| MAX_AGENT_TURNS | 10 | 最大推理轮数 |
| LLM_TEMPERATURE | 0.3 | LLM 温度参数 |

## 架构说明

### ReAct 循环

```
用户问题 → 分析(LLM) → 搜索(search) → 观察结果 → 分析(LLM) → ... → 最终答案
               ↑                        ↓
               └──── 信息不足则继续 ←────┘
```

### Agent 推理流程

1. 接收自然语言问题
2. LLM 分析问题，输出 JSON action
3. 执行 search/fetch 工具
4. 将工具结果注入对话上下文
5. LLM 继续推理，直到给出最终答案
6. 答案归一化处理

## PAI-LangStudio 部署

在 PAI-LangStudio 代码模式中：
1. 将本项目完整上传
2. 配置模型为 Qwen 系列（通过 PAI Model Gallery 或阿里云百炼）
3. 部署为 PAI-EAS 服务
4. 服务将自动暴露 `/api/answer` 接口

## 约束条件

- 禁止任何形式的模型微调
- 仅使用允许的模型服务
- 禁止硬编码评测题答案
- 所有 Agent 逻辑在项目包内实现
