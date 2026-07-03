"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-MCP V1.0
MCP Server —— 兼容性重新导出入口

此模块保持原有 import 路径 mcp_server.mcp_serve 可用。
所有实现已拆分到:
  - mcp_server.mcp_core               (FastMCP 实例、启动函数)
  - mcp_server.mcp_registration_tools  (挂号管理工具)
  - mcp_server.mcp_other_tools         (健康咨询 / 地图 / 影像工具)

启动方式 (与原有保持一致):
  stdio 模式（默认，用于 Claude Desktop 等 MCP Client 连接）:
    python mcp_server/mcp_serve.py

  HTTP 模式（用于 Web 集成）:
    python mcp_server/mcp_serve.py --transport sse --port 8087

MCP Client 接入:
  将以下配置添加到 MCP Client 的配置文件中:
  {
    "medical-agent": {
      "command": "python",
      "args": ["mcp_server/mcp_serve.py"],
      "cwd": "/path/to/Agent工单15/02_研发/backend"
    }
  }
================================================================================
"""

# 导入核心模块 (创建 FastMCP 实例)
from mcp_server.mcp_core import mcp, run_stdio, run_sse

# 导入工具模块 (触发 @mcp.tool() 装饰器注册)
import mcp_server.mcp_registration_tools as _reg_tools    # noqa: F401
import mcp_server.mcp_other_tools as _other_tools          # noqa: F401

# 保持原有命名空间可用
__all__ = ["mcp", "run_stdio", "run_sse"]


# ================================================================
# __main__ 启动入口
# ================================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="医疗智能体 MCP Server")
    parser.add_argument("--transport", choices=["stdio", "sse"], default="stdio",
                       help="传输协议 (默认: stdio)")
    parser.add_argument("--port", type=int, default=8087,
                       help="HTTP 模式端口 (默认: 8087)")
    parser.add_argument("--host", default="127.0.0.1",
                       help="HTTP 模式监听地址 (默认: 127.0.0.1)")
    args = parser.parse_args()

    if args.transport == "sse":
        run_sse(host=args.host, port=args.port)
    else:
        run_stdio()
