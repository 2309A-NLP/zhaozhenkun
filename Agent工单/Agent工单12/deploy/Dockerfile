# ============================================================
# deploy/Dockerfile - 医疗健康咨询 Agent 镜像
# 功能: 构建包含完整依赖环境的容器镜像
# 工单编号: 人工智能NLP-Agent数字人项目-医疗智能体-健康咨询
# ============================================================

FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制 dev 目录（研发代码）
COPY dev/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY dev/ ./

# 复制测试和数据
COPY test/ ./test/
COPY medical.json .

# 暴露 API 端口
EXPOSE 8003

# 默认启动: 构建图谱 + 启动服务
CMD ["sh", "-c", "python run.py build && python run.py serve"]
