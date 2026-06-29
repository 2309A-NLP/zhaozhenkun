# ===================================================================
# Agent 工单10 — 数字人智能体系统 Docker 镜像
# ===================================================================
FROM nvidia/cuda:12.4.0-runtime-ubuntu22.04

LABEL description="digitalhuman - Agent数字人系统"
LABEL version="1.0"

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# 国内 pip 镜像（清华源，构建快）
ARG PIP_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.10 python3.10-dev python3-pip \
    ffmpeg libsndfile1 libsndfile1-dev \
    libgl1-mesa-glx libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1 \
    curl git wget \
    && rm -rf /var/lib/apt/lists/* \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.10 1 \
    && python3 -m pip install --upgrade -i ${PIP_INDEX} pip setuptools wheel

WORKDIR /app

# ============================================================
# Python 依赖 — 使用国内镜像加速
# ============================================================

# PyTorch CPU（~200MB，清华源快；数字人占位模式可用）
RUN pip3 install --no-cache-dir -i ${PIP_INDEX} \
    torch torchvision torchaudio

# FunASR + ModelScope
RUN pip3 install --no-cache-dir -i ${PIP_INDEX} \
    funasr>=1.0 modelscope>=1.14

# 音频/视频
RUN pip3 install --no-cache-dir -i ${PIP_INDEX} \
    numpy opencv-python-headless>=4.8 \
    librosa>=0.10 soundfile>=0.12 scipy>=1.10

# Web + 工具
RUN pip3 install --no-cache-dir -i ${PIP_INDEX} \
    flask>=3.0 flask-cors>=4.0 requests>=2.31 \
    edge-tts>=6.1 dashscope>=1.17 openai>=1.0 \
    scikit-learn>=1.3 aiohttp>=3.9 python-multipart>=0.0.6 pyyaml>=6.0

# SadTalker 数字人依赖（唇形同步）
RUN pip3 install --no-cache-dir -i ${PIP_INDEX} \
    scikit-image>=0.21 kornia>=0.7 facexlib>=0.3 face-alignment>=1.4 \
    ffmpeg-python>=0.2 imageio-ffmpeg>=0.5 yacs>=0.1 pydub>=0.25

# 复制项目
COPY 研发/ /app/研发/
COPY 部署/ /app/部署/
COPY 设计/ /app/设计/
COPY static/ /app/static/
COPY run.py /app/run.py

RUN mkdir -p /app/data/db /app/data/voice_samples \
             /app/data/avatars /app/data/output /app/data/logs /app/tools

ENV APP_HOME=/app
ENV TOOLS_ROOT=/app/tools
ENV LEDGER_DB_PATH=/app/data/db/money_notes.db
ENV SCHEDULE_DB_PATH=/app/data/db/schedule_notes.db
ENV SCHEDULE_LOCAL_DB_PATH=/app/data/db/schedule_notes.db
ENV VOICE_SAMPLES_DIR=/app/data/voice_samples
ENV DH_AVATARS_DIR=/app/data/avatars
ENV DH_OUTPUT_DIR=/app/data/output

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5002/api/health || exit 1

EXPOSE 5002
ENTRYPOINT ["python3", "/app/run.py"]
