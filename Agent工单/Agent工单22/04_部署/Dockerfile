# ============================================================
# 多领域智能体长期记忆系统 — Docker 镜像
# ============================================================
# 构建:  docker build -t agent-memory-bridge .
# 运行:  docker run -p 8008:8008 --network host agent-memory-bridge

FROM python:3.11-slim  # 使用轻量级 Python 基础镜像

WORKDIR /app  # 设置工作目录

# --- 安装系统依赖 ---
# gcc 可能被某些 pip 包的编译所依赖
RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

# --- 安装 Python 依赖 ---
# 优先使用清华 pip 镜像加速（国内环境）
COPY 04_部署/requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple \
    -r requirements.txt

# --- 复制项目源码 ---
# 只复制需要的目录，减小镜像体积
COPY 01_设计/ /app/01_设计/
COPY 02_研发/ /app/02_研发/
COPY 03_测试/ /app/03_测试/
COPY 04_部署/ /app/04_部署/
COPY 05_优化/ /app/05_优化/

# --- 暴露桥接 API 端口 ---
EXPOSE 8008

# --- 设置环境变量 ---
# DeepSeek API 配置（运行时注入）
ENV DEEPSEEK_BASE_URL=https://api.deepseek.com
ENV DEEPSEEK_MODEL=deepseek-v4-flash
# mem0 服务地址
ENV MEM0_BASE_URL=http://localhost:8888
# 桥接服务端口
ENV BRIDGE_PORT=8008

# --- 启动命令 ---
CMD ["python", "-u", "02_研发/agent_bridge.py"]
