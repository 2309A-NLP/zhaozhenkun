# 医疗智能体-影像分析系统 V1.0

**工单编号：** 人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0

---

## 📂 项目结构

```
Agent工单13/
├── 📄 README.md                    # 项目总览
├── 📄 start.bat / start.sh         # 一键启动
│
├── 📁 01_设计/                     # 📐 设计阶段
│   ├── 原始工单需求.pdf            # 工单原始文件
│   ├── 需求分析文档.md             # 用户故事 + 功能需求
│   ├── 系统架构设计.md             # 架构图 + 技术选型
│   └── API接口设计.md              # REST API 规范
│
├── 📁 02_研发/                     # 💻 研发阶段
│   ├── backend/                    # Python FastAPI 后端
│   │   ├── main.py                 # 服务入口
│   │   ├── config.py               # 配置中心
│   │   ├── api/                    # VQA / MRG / RAG / Upload
│   │   ├── services/               # 千问 + DeepSeek 客户端
│   │   └── rag/                    # ChromaDB + 嵌入模型
│   └── frontend/                   # Web 前端
│       ├── index.html              # 单页应用
│       ├── css/style.css           # 医疗级 UI
│       └── js/                     # VQA / MRG / RAG 交互
│
├── 📁 03_测试/                     # 🧪 测试阶段
│   ├── 测试计划.md                 # 测试用例 + 结果
│   ├── test_api.py                 # API 自动化测试
│   └── 测试数据/                   # 测试用数据
│
├── 📁 04_部署/                     # 🚀 部署阶段
│   ├── docker/                     # Dockerfile
│   ├── docker-compose.yml          # 一键编排
│   └── 部署文档.md                 # 环境配置指南
│
├── 📁 05_优化/                     # ⚡ 优化阶段
│   ├── 性能优化方案.md             # 瓶颈分析 + 方案
│   ├── 安全加固清单.md             # 已实施 + 待改进
│   └── 后续迭代计划.md             # V1.1 → V2.1
│
└── 📁 data/                        # 共享数据
    ├── uploads/                    # 上传文件
    ├── knowledge/                  # 知识库文档
    └── chroma_db/                  # 向量数据库
```

## 🚀 快速启动

```bash
# 开发模式
cd 02_研发/backend
pip install -r requirements.txt
python main.py
# 访问 http://localhost:8000

# Docker 部署
cd 04_部署
export QWEN_API_KEY="your-key"
export DEEPSEEK_API_KEY="your-key"
docker-compose up -d
# 访问 http://localhost
```

## 🎯 功能模块

| 功能 | 技术 | 接口 |
|------|------|------|
| VQA 视觉问答 | 千问 qwen-vl-plus | POST /api/vqa/ask |
| MRG 报告生成 | 千问 qwen-vl-plus | POST /api/mrg/generate |
| RAG 检索增强 | DeepSeek + ChromaDB | POST /api/rag/query |
