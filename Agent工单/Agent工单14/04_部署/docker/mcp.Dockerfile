# 工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-MCP V1.0
FROM python:3.11-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖（包含 mcp + 后端依赖）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制 MCP 服务代码
COPY mcp_serve.py .

# 暴露 MCP HTTP 端口（用于 SSE 传输模式）
EXPOSE 8081

# 默认 stdio 模式（MCP 客户端直接调用）
# 也可通过环境变量切换为 SSE 模式：MCP_TRANSPORT=sse
CMD ["python", "mcp_serve.py"]
