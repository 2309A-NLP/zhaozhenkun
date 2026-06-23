# RAG工单18 - 文档质量评估Skill与工作流集成项目

## 项目简介

本项目用于实现“文档质量评估”能力，并以可复用组件的方式接入智能体工作流。

当前项目采用五分类结构：
- 设计：需求说明、总结、交付文档
- 研发：核心代码、API、工作流集成骨架
- 测试：测试脚本与示例报告
- 优化：验证结果与改进记录
- 部署：依赖、安装、启动脚本

## 当前交付边界

本项目已完成：
- 文档质量评估核心能力
- CLI 调用入口
- REST API 接口
- 工作流集成骨架与调用适配层
- Windows / WSL 双环境运行说明

本项目未直接内嵌某一外部平台完整源码；如需接入具体 RAGFlow / Agent 平台，请按“设计/README.md”中的集成说明对接。

## 目录结构

```text
rag工单18/
├── 设计/
├── 研发/
│   ├── api/
│   ├── config/
│   ├── core/
│   ├── workflow/
│   ├── __init__.py
│   └── main.py
├── 测试/
├── 优化/
├── 部署/
├── run.py
└── README.md
```

## 快速开始

### Windows（推荐）

1. 打开终端进入项目根目录
2. 安装依赖：

```bash
pip install -r 部署/requirements.txt
```

3. 评估目录：

```bash
python run.py --assess "C:\\你的文档目录" --output "测试\\reports" --summary
```

4. 启动 API：

```bash
python run.py --api --host 0.0.0.0 --port 5000
```

### WSL

Windows 路径要写成 `/mnt/c/...` 形式，例如：

```bash
python3 run.py --assess "/mnt/c/Users/31326/Desktop/示例文档" --output "测试/reports" --summary
```

## API 路径

统一使用以下接口前缀：
- POST `/v1/document/quality-inspection`
- POST `/v1/document/quality-inspection/upload`
- GET `/v1/document/quality-inspection/report/<filename>`
- GET `/v1/document/quality-inspection/health`
- GET `/v1/document/quality-inspection/config`
- PUT `/v1/document/quality-inspection/config`

注意：本项目不再使用 `/api/v1/...` 旧写法。

## 工作流集成说明

工作流集成代码位于：
- `研发/workflow/skill_adapter.py`
- `研发/workflow/document_workflow.py`

它们提供：
- 技能输入标准化
- 质量评估调用封装
- 按质量结果进行后续路由的骨架

## 关键说明

1. 根目录已清理重复副本与缓存目录。
2. 项目主入口统一为 `run.py`。
3. 启动脚本、文档、API 路径已统一。
4. 该项目现在是“可交付的单项目版本”，不是双份代码并存版本。
