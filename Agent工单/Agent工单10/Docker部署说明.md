# Docker 部署说明 — Agent 数字人智能体系统

工单编号: 人工智能NLP-Agent数字人项目-Agent数字人部署任务
版本: V1.0
日期: 2026-06-25

## 一、环境要求

| 项目 | 最低要求 | 说明 |
|------|---------|------|
| Docker | 24.0+ | `docker --version` |
| Docker Compose | v2.0+ | `docker compose version` |
| NVIDIA Driver | 525+ | `nvidia-smi` (GPU推理需要) |
| nvidia-docker2 | 已安装 | `docker run --gpus all nvidia/cuda:12.4.0-runtime-ubuntu22.04 nvidia-smi` |
| 磁盘 | ≥15GB 空闲 | 镜像 ~6GB + 模型 ~2GB |
| 网络 | 需访问 api.deepseek.com | DeepSeek API 调用 |

### 验证 GPU Docker 支持
```bash
# 如果以下命令能显示 GPU 信息，则 GPU Docker 已就绪
docker run --rm --gpus all nvidia/cuda:12.4.0-runtime-ubuntu22.04 nvidia-smi
```

## 二、快速启动

### 1. 配置环境变量
```bash
cd Agent工单9

# 编辑 .env 文件，至少填入 DEEPSEEK_API_KEY 和 QWEN_API_KEY
# 如果已有 config.py 中的密钥，可跳过此步（已自动复制）
```

### 2. 构建镜像
```bash
docker compose build
```
首次构建约需 10-15 分钟（下载 PyTorch CUDA 包 + FunASR 等依赖）。

### 3. 启动服务
```bash
# 后台启动
docker compose up -d

# 查看日志（等待模型加载）
docker compose logs -f agent
```

### 4. 访问
浏览器打开: **http://localhost:5002**

### 5. 停止
```bash
docker compose down
```

## 三、服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| Agent 智能体 | 5002 | Flask Web + 文本对话 + 语音对话 |
| GPT-SoVITS (可选) | 9880 | 独立 TTS 服务，不启动则自动回退 EdgeTTS |

## 四、API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 聊天 UI 界面 |
| `/api/chat` | POST | 文本对话（主接口） |
| `/api/voice/chat` | POST | 语音对话管线（音频→ASR→Agent→TTS→视频） |
| `/api/tts` | POST | 文本转语音 |
| `/api/voice/clone` | POST | 声音克隆注册 |
| `/api/health` | GET | 健康检查（ASR/TTS/DH 状态） |
| `/api/video/stream` | GET | MJPEG 数字人视频流 |
| `/api/metrics` | GET | SLA 性能指标 |

## 五、数据持久化

| Volume | 容器路径 | 内容 |
|--------|---------|------|
| `agent-data-db` | `/app/data/db` | SQLite 数据库（记账本、日程） |
| `agent-data-voice` | `/app/data/voice_samples` | 声音克隆参考音频 |
| `agent-data-avatars` | `/app/data/avatars` | 数字人头像图片 |
| `agent-data-output` | `/app/data/output` | 生成的 MP4 回复视频 |
| `agent-data-logs` | `/app/data/logs` | 运行日志 |

```bash
# 查看 Volume 内容
docker volume ls | grep agent-data
docker run --rm -v agent-data-db:/data alpine ls /data
```

## 六、常见问题

### Q1: 启动后无法访问？
```bash
# 检查容器是否运行
docker compose ps
# 查看日志
docker compose logs agent --tail=50
# 健康检查
curl http://localhost:5002/api/health
```

### Q2: 数字人无唇形同步？
容器内 SadTalker 需要 GPU。确认：
```bash
# 检查 GPU 是否透传成功
docker exec agent-digital-human python3 -c "import torch; print(torch.cuda.is_available())"
# 应输出: True
```
若输出 False，确认 `nvidia-docker2` 已安装且 `docker compose up` 时未报 GPU 相关错误。

### Q3: 语音识别/合成不可用？
FunASR 模型首次使用时会从 ModelScope 自动下载（~300MB），请等待首次请求完成。
TTS 会优先尝试 GPT-SoVITS，不可用时自动回退 EdgeTTS（在线免费）。

### Q4: 基金问答返回"数据库未找到"？
金融数据集未挂载或路径不对。检查 .env 中的 `FINANCIAL_DATA_PATH` 是否指向正确的 `bs_challenge_financial_14b_dataset` 目录。

### Q5: 如何更新代码后重新部署？
```bash
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Q6: 镜像太大，如何瘦身？
当前镜像约 6-8GB（含 PyTorch CUDA + FunASR）。如需瘦身可：
- 使用 `python:3.10-slim` 基础镜像 + CPU 版 PyTorch（牺牲 GPU 加速）
- 数字人将自动回退到占位模式（静态帧+音频）

## 七、容器管理命令

```bash
# 进入容器调试
docker exec -it agent-digital-human bash

# 查看资源占用
docker stats agent-digital-human

# 查看日志（实时跟踪）
docker compose logs -f agent

# 重启服务
docker compose restart agent

# 彻底清理（含数据卷）
docker compose down -v
```

## 八、生产环境建议

1. **API 密钥**: 不要在 .env 中硬编码，生产环境使用 Docker Secrets 或 K8s Secrets
2. **HTTPS**: 前置 Nginx 反向代理，配置 SSL 证书
3. **GPU 资源**: 限制 GPU 显存使用 `--gpus '"device=0"'`，多实例时避免 OOM
4. **日志**: 接入 ELK/Loki 集中式日志系统
5. **监控**: 对接 Prometheus + Grafana，利用 /api/metrics 和 /api/health 端点
