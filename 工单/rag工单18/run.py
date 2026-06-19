#!/usr/bin/env python3
"""项目统一入口。"""

import argparse
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parent
RND_DIR = PROJECT_ROOT / "研发"
if str(RND_DIR) not in sys.path:
    sys.path.insert(0, str(RND_DIR))

import importlib.util

MAIN_SPEC = importlib.util.spec_from_file_location("rag18_main", RND_DIR / "main.py")
if MAIN_SPEC is None or MAIN_SPEC.loader is None:
    raise RuntimeError("无法加载研发/main.py")
MAIN_MODULE = importlib.util.module_from_spec(MAIN_SPEC)
MAIN_SPEC.loader.exec_module(MAIN_MODULE)

run_assessment = MAIN_MODULE.run_assessment
run_api_server = MAIN_MODULE.run_api_server
setup_logging = MAIN_MODULE.setup_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="文档质量评估项目统一入口")
    parser.add_argument("--config", "-c", help="配置文件路径")
    parser.add_argument(
        "--log-level",
        "-l",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="日志级别",
    )
    parser.add_argument("--log-file", help="日志文件路径")
    parser.add_argument("--assess", help="待评估的文件或目录路径")
    parser.add_argument("--output", default=str(PROJECT_ROOT / "测试" / "reports"), help="报告输出目录")
    parser.add_argument(
        "--formats",
        nargs="+",
        default=["json", "html"],
        choices=["json", "html"],
        help="报告格式",
    )
    parser.add_argument("--summary", action="store_true", help="打印评估摘要")
    parser.add_argument("--api", action="store_true", help="启动 API 服务")
    parser.add_argument("--host", default="0.0.0.0", help="API 服务主机")
    parser.add_argument("--port", type=int, default=5000, help="API 服务端口")
    parser.add_argument("--debug", action="store_true", help="启用 Flask debug")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    setup_logging(args.log_level, args.log_file)

    if args.assess:
        assess_args = SimpleNamespace(
            input=args.assess,
            output=args.output,
            formats=args.formats,
            summary=args.summary,
            config=args.config,
        )
        return run_assessment(assess_args)

    if args.api:
        api_args = SimpleNamespace(
            host=args.host,
            port=args.port,
            debug=args.debug,
            config=args.config,
        )
        return run_api_server(api_args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
