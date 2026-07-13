# 工单编号：人工智能NLP-Agent数字人项目-17-教育Agent任务工单-教学场景功能分析及智能备课
# 文件：Dockerfile - 智能备课系统容器化构建文件
# 创建时间：2025年6月
# 使用方式：docker build -t edu-agent-lesson-prep .

FROM python:3.11-slim  # 基于Python 3.11精简镜像

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1  # 不生成.pyc字节码文件
ENV PYTHONUNBUFFERED=1  # 日志实时输出（不缓冲）
ENV APP_HOME=/app  # 应用根目录
WORKDIR $APP_HOME  # 设置工作目录

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    curl \
    wkhtmltopdf \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装Python依赖
# 注意：Docker build context 必须为项目根目录（Agent工单17(教育)/）
COPY 部署/requirements.txt /app/requirements.txt  # 复制依赖清单（从项目根目录）
RUN pip install --no-cache-dir -r /app/requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制应用源码（所有路径相对于Docker build context即项目根目录）
COPY 研发/ /app/  # 复制研发模块到/app/
COPY 设计/ /app/设计/  # 复制设计文档
COPY 测试/ /app/测试/  # 复制测试文件
COPY 优化/ /app/优化/  # 复制优化模块（漏掉的模块）

# 创建数据和日志目录
RUN mkdir -p /app/data/faiss_index \
    /app/data/knowledge_base \
    /app/data/uploads \
    /app/data/exports \
    /app/logs

# 暴露服务端口
EXPOSE 8000  # FastAPI服务端口

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1  # 每30秒检查健康接口

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
