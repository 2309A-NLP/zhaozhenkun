# 医疗智能体-影像分析系统 V2.0（MCP版）

**工单编号：** 人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
**MCP工单编号：** 人工智能 NLP-Agent 数字人项目-医疗智能体-MCP V1.0

---

## 📂 项目结构

```
Agent工单14/
├── 📄 README.txt                   # 项目总览
├── 📄 start.bat / start.sh         # 一键启动
│
├── 📁 01_设计/                     # 📐 设计阶段
│   ├── 原始工单需求.pdf            # 工单原始文件
│   ├── 需求分析文档.txt            # 用户故事 + 功能需求
│   ├── 系统架构设计.txt            # 架构图 + 技术选型
│   └── API接口设计.txt             # REST API 规范
│
├── 📁 02_研发/                     # 💻 研发阶段
│   ├── backend/                    # Python FastAPI 后端
│   │   ├── main.py                 # 服务入口
│   │   ├── config.py               # 配置中心
│   │   ├── api/                    # VQA/MRG/RAG/Upload/Map/Assistant
│   │   ├── services/               # 千问 + DeepSeek + 高德地图客户端
│   │   ├── rag/                    # ChromaDB + 嵌入模型
│   │   ├── kg/                     # 知识图谱（6143种疾病）
│   │   └── db/                     # SQLite 数据库
│   ├── mcp_server/                 # 🆕 MCP Server
│   │   ├── mcp_serve.py            # MCP 服务（11个工具）
│   │   ├── requirements.txt        # MCP 依赖
│   │   └── mcp_client_config.json  # MCP 客户端配置示例
│   └── frontend/                   # Web 前端
│       ├── index.html              # 单页应用
│       ├── css/style.css           # 医疗级 UI
│       └── js/                     # VQA/MRG/RAG/Map/Assistant
│
├── 📁 03_测试/                     # 🧪 测试阶段
│   ├── 测试计划.txt                # 测试用例 + 结果
│   └── test_api.py                 # API 自动化测试（15个测试）
│
├── 📁 04_部署/                     # 🚀 部署阶段
│   ├── docker/                     # backend / frontend / mcp Dockerfile
│   ├── docker-compose.yml          # 一键编排（含 MCP Server）
│   └── 部署文档.txt                # 环境配置指南
│
├── 📁 05_优化/                     # ⚡ 优化阶段
│   ├── 性能优化方案.txt            # 瓶颈分析 + 方案
│   ├── 安全加固清单.txt            # 已实施 + 待改进
│   └── 后续迭代计划.txt            # V1.1 → V2.1
│
└── 📁 data/                        # 共享数据
    ├── uploads/                    # 上传文件
    ├── knowledge/                  # 知识库文档
    └── chroma_db/                  # 向量数据库
```

## 🚀 快速启动

```bash
# 开发模式（FastAPI 后端）
cd 02_研发/backend
pip install -r requirements.txt
python main.py
# 访问 http://localhost:8000

# MCP Server 独立启动（供 MCP 客户端调用）
cd 02_研发/mcp_server
pip install -r requirements.txt
python mcp_serve.py

# Docker 部署
cd 04_部署
export QWEN_API_KEY="your-key"
export DEEPSEEK_API_KEY="your-key"
export AMAP_API_KEY="your-amap-key"
docker-compose up -d
# 访问 http://localhost
```

## 🎯 功能模块

| 功能 | 技术 | 接口 |
|------|------|------|
| VQA 视觉问答 | 千问 qwen-vl-plus | POST /api/vqa/ask |
| MRG 报告生成 | 千问 qwen-vl-plus | POST /api/mrg/generate |
| RAG 检索增强 | DeepSeek + ChromaDB | POST /api/rag/query |
| 健康助理 | DeepSeek | POST /api/assistant/chat |
| 挂号管理 | DeepSeek + SQLite | POST /api/registration/chat |
| 健康咨询 | 知识图谱 + DeepSeek | POST /api/consultation/chat |
| 🆕 就医导航 | 高德地图 MCP 对接 | POST /api/map/chat |
| 🆕 地点搜索 | 高德地图 POI | POST /api/map/search |
| 🆕 周边推荐 | 高德地图 Around | POST /api/map/nearby |
| 🆕 路线规划 | 高德地图 Direction | POST /api/map/directions |
| 🆕 地理编码 | 高德地图 Geocode | POST /api/map/geocode |

## 🆕 MCP Server 工具列表

| 工具 | 分类 | 描述 |
|------|------|------|
| amap_search_poi | 高德地图 | 关键词地点搜索（医院/酒店/餐厅） |
| amap_search_nearby | 高德地图 | 周边POI搜索（住宿/餐饮/交通） |
| amap_get_directions | 高德地图 | 出行路线规划（驾车/步行/公交） |
| amap_geocode | 高德地图 | 地址→经纬度 |
| amap_regeocode | 高德地图 | 经纬度→地址 |
| amap_weather | 高德地图 | 天气查询 |
| amap_hospital_services | 高德地图 | 医院周边一站式查询 |
| medical_health_consult | 医疗智能体 | 健康咨询（知识图谱） |
| medical_rag_search | 医疗智能体 | 医学知识检索（RAG） |
| medical_registration_intent | 医疗智能体 | 挂号意图解析 |
