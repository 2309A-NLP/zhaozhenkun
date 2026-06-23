#!/usr/bin/env python3
"""
文档质量评估系统主入口
Document Quality Assessment System Main Entry Point
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.assessor import DocumentQualityAssessor
from core.base import ConfigManager

# 模块级logger
logger = logging.getLogger("dqa.main")

# 默认日志目录
DEFAULT_LOG_DIR = Path(__file__).parent.parent / "logs"


def setup_logging(log_level: str = 'INFO', log_file: str = None):
    """统一日志配置 — 同时输出到控制台和文件"""
    log_format = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    root_logger = logging.getLogger("dqa")
    root_logger.handlers.clear()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # 控制台
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(getattr(logging, log_level.upper()))
    ch.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    root_logger.addHandler(ch)

    # 文件
    if log_file is None:
        os.makedirs(DEFAULT_LOG_DIR, exist_ok=True)
        log_file = str(DEFAULT_LOG_DIR / "dqa.log")
    else:
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)

    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logging.DEBUG)  # 文件始终记录DEBUG级别
    fh.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    root_logger.addHandler(fh)

    # 同时给core.base的logger也配上
    for name in ("dqa.core", "dqa.api", ""):
        lg = logging.getLogger(name)
        lg.handlers.clear()

    logger.info("日志系统初始化完成 (level=%s, file=%s)", log_level, log_file)
    return root_logger


def run_assessment(args):
    """运行评估"""
    logger.info("开始评估: %s", args.input)

    assessor = DocumentQualityAssessor(args.config)

    if os.path.isdir(args.input):
        result = assessor.assess_directory(args.input)
    elif os.path.isfile(args.input):
        result = assessor.assess_files([args.input])
    else:
        logger.error("输入路径不存在: %s", args.input)
        return 1

    if args.output:
        report_files = assessor.generate_report(
            result, output_dir=args.output, formats=args.formats
        )
        logger.info("报告已生成: %s", report_files)

    if args.summary:
        _log_summary(result)

    return 0


def _log_summary(result: dict):
    """将评估摘要输出到日志"""
    sep = "=" * 80
    logger.info("\n%s\n评估结果摘要\n%s", sep, sep)

    summary = result.get('summary', {})
    for section_name, section_content in summary.items():
        logger.info("\n[%s]\n%s\n%s", section_name, "-" * 40, section_content)

    logger.info("\n%s", sep)
    logger.info("待确认项目: %d 项", result.get('pending_confirmation_count', 0))
    logger.info("待审核项目: %d 项", result.get('pending_review_count', 0))
    logger.info("%s", sep)


def run_api_server(args):
    """运行API服务"""
    from api.api import run_api
    logger.info("启动API服务: %s:%s (debug=%s)", args.host, args.port, args.debug)

    run_api(
        host=args.host,
        port=args.port,
        debug=args.debug,
        config_path=args.config,
    )
    return 0


def main():
    parser = argparse.ArgumentParser(
        description='文档质量评估系统 — Document Quality Assessment',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py assess /path/to/documents -o ./reports -s
  python main.py assess /path/to/document.pdf -o ./reports
  python main.py api --host 0.0.0.0 --port 5000 --debug
        """,
    )

    parser.add_argument('--config', '-c', help='配置文件路径')
    parser.add_argument(
        '--log-level', '-l',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO', help='日志级别 (默认: INFO)',
    )
    parser.add_argument('--log-file', help='日志文件路径 (默认: logs/dqa.log)')

    subparsers = parser.add_subparsers(dest='command', help='可用命令')

    # assess
    ap = subparsers.add_parser('assess', help='评估文档质量')
    ap.add_argument('input', help='输入文件或文件夹路径')
    ap.add_argument('--output', '-o', help='报告输出目录')
    ap.add_argument('--formats', '-f', nargs='+', default=['json', 'html'],
                    choices=['json', 'html'], help='报告格式')
    ap.add_argument('--summary', '-s', action='store_true', help='输出评估摘要')

    # api
    ap2 = subparsers.add_parser('api', help='启动API服务')
    ap2.add_argument('--host', default='0.0.0.0', help='主机地址')
    ap2.add_argument('--port', '-p', type=int, default=5000, help='端口')
    ap2.add_argument('--debug', '-d', action='store_true', help='调试模式')

    args = parser.parse_args()

    setup_logging(args.log_level, args.log_file)

    if args.command == 'assess':
        return run_assessment(args)
    elif args.command == 'api':
        return run_api_server(args)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
