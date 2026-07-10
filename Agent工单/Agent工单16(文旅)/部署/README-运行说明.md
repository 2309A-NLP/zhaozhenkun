# 运行说明

> 工单编号：人工智能CV-AIGC-16-【必选】文旅Agent任务工单-需求分析与功能设计V1.1-20260306

---

## 一、项目定位

本项目是《文旅创新智脑》AI智能体的完整交付项目，包含：
- **需求分析与架构设计文档**
- **交互式HTML原型**（已接入真实LLM API）
- **Python后端服务**（FastAPI + 流式对话）
- **可直接交互的AI智能体**（数字人对话、快捷指令、PPT/流程图生成）

---

## 二、快速启动

### Windows（推荐）

双击运行：
```
研发\start_server.bat
```

### 手动启动

```bash
# 1. 进入研发目录
cd 研发

# 2. 安装依赖（仅首次）
pip install -r requirements.txt

# 3. 启动服务
python server.py
```

---

## 三、使用方式

启动后在浏览器打开：**http://localhost:8765**

| 页面 | 功能 | 说明 |
|------|------|------|
| 🤖 数字人对话 | AI实时聊天 | 流式响应，支持Kimi/DeepSeek/千问切换 |
| 🔍 知识检索 | 文旅知识搜索 | LLM驱动的RAG式检索 |
| ⚡ 快捷指令 | 5个专业指令 | 资源挖掘/场景创意/文化创新/数字营销/效益提升 |
| 🎨 PPT/流程图 | AI自动生成 | 生成可下载的PPT文件和Mermaid流程图 |
| 📊 管理后台 | 运营Dashboard | 客流/设备/告警数据展示 |

---

## 四、API接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/chat` | POST | AI对话（流式SSE） |
| `/api/quick-command` | POST | 执行快捷指令（流式SSE） |
| `/api/search` | POST | 知识检索（流式SSE） |
| `/api/generate-ppt` | POST | 生成PPT文件 |
| `/api/generate-flowchart` | POST | 生成Mermaid流程图 |
| `/api/health` | GET | 健康检查 |

API文档：http://localhost:8765/docs

---

## 五、大模型配置

| 模型 | 用途 | 配置文件 |
|------|------|---------|
| Kimi (moonshot-v1-8k) | 主对话模型 | 部署/config/kimi_config.json |
| DeepSeek (deepseek-chat) | 备选/技术分析 | server.py 内置 |
| 千问 (qwen-plus) | 备选/场景分析 | server.py 内置 |

前端可随时切换模型。

---

## 六、生成文件

PPT文件生成后保存在：`研发/output/`

---

## 七、技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| 异步HTTP | httpx |
| PPT生成 | python-pptx |
| 流程图 | Mermaid.js (CDN) |
| 前端 | 纯HTML/CSS/JS (零框架) |
| 大模型 | Kimi / DeepSeek / 千问 (API) |
