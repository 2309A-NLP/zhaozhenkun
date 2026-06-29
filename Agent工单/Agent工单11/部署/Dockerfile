# ===================================================================
# Agent 工单11 — 医疗挂号Agent系统 Docker 镜像
# ===================================================================
FROM python:3.10-slim

LABEL description="medical-agent — 医疗挂号Agent系统"
LABEL version="1.0"

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# 国内pip镜像(清华源)
ARG PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python依赖(轻量化: 只需flask+requests)
RUN pip3 install --no-cache-dir -i ${PIP_INDEX} \
    flask>=3.0 flask-cors>=4.0 requests>=2.31

# 复制项目文件
COPY 研发/ /app/研发/
COPY 部署/templates/ /app/部署/templates/
COPY hospital.db /app/hospital.db
COPY run.py /app/run.py

ENV APP_HOME=/app
ENV HOSPITAL_DB_PATH=/app/hospital.db

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5003/api/health || exit 1

EXPOSE 5003
ENTRYPOINT ["python3", "/app/run.py"]
