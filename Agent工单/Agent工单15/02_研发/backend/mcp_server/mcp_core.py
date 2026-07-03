"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-MCP V1.0
MCP Server 核心模块 —— FastMCP 实例、运行入口、导入

此模块定义:
  - FastMCP Server 实例 (mcp)
  - stdio 启动函数 (run_stdio)
  - SSE/HTTP 启动函数 (run_sse)

工具实现拆分到:
  - mcp_server.mcp_registration_tools  (挂号管理)
  - mcp_server.mcp_other_tools         (健康咨询 / 地图服务 / 影像分析)

兼容入口: mcp_server.mcp_serve.py 保留原有 import 路径, 并包含 __main__ 启动逻辑.
================================================================================
"""
import sys
import os
import json
import logging
from pathlib import Path

# 确保 backend 目录在 sys.path 中
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from mcp.server.fastmcp import FastMCP

_log = logging.getLogger("medical_agent.mcp_server")

# ================================================================
# 创建 FastMCP Server 实例
# ================================================================
mcp = FastMCP(
    name="医疗智能体-Agent MCP Server",
    instructions="""
医疗智能体 MCP Server —— 提供挂号管理、健康咨询、影像分析、地图服务能力。""",
)

_mcp_log = logging.getLogger("medical_agent.mcp")


# ================================================================
# MCP Server 启动函数
# ================================================================

def run_stdio():
    """stdio 模式启动 —— 用于 Claude Desktop 等 MCP Client"""
    print("[医疗智能体 MCP Server] stdio 模式启动", file=sys.stderr)
    mcp.run(transport="stdio")


def run_sse(host: str = "127.0.0.1", port: int = 8087):
    """HTTP SSE 模式启动 —— 用于 Web 集成"""
    import uvicorn
    _log.info("[医疗智能体 MCP Server] SSE 模式启动: http://%s:%d/sse", host, port)

    # FastMCP 内部使用 Starlette，用 uvicorn 启动
    app = mcp.sse_app()
    uvicorn.run(app, host=host, port=port, log_level="info")
