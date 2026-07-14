# ==============================================================================
# 部署 — Research Agent Docker 镜像
# ==============================================================================
# 构建方式: docker build -t research-agent:latest .
# 运行方式: docker run -p 8000:8000 -e DEEPSEEK_API_KEY=sk-xxx research-agent:latest
# ==============================================================================

# 基础镜像: Python 3.10 slim 版本
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONUNBUFFERED=1          # Python 输出不缓冲
ENV PYTHONDONTWRITEBYTECODE=1   # 不生成 .pyc 文件
ENV EAS_SERVICE_PORT=8000       # 默认服务端口

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \                      # HTTP 测试工具
    ca-certificates \           # SSL 证书
    && rm -rf /var/lib/apt/lists/*  # 清理 apt 缓存

# 复制依赖文件
COPY 部署/requirements.txt /app/requirements.txt

# 安装 Python 依赖
RUN pip install --no-cache-dir -r /app/requirements.txt

# 复制项目代码
COPY . /app/

# 暴露服务端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# 启动命令
CMD ["python", "部署/app.py"]
