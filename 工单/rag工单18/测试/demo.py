#!/usr/bin/env python3
"""
文档质量评估系统演示脚本
Document Quality Assessment System Demo Script
"""

import os
import sys
import logging
import tempfile
import shutil
from pathlib import Path

# 添加研发目录到Python路径
project_root = Path(__file__).parent.parent / "研发"
sys.path.insert(0, str(project_root))

from core.assessor import DocumentQualityAssessor

# 日志配置
logger = logging.getLogger("dqa.demo")
LOG_DIR = Path(__file__).parent.parent / "logs"


def setup_demo_logging():
    """演示日志配置"""
    os.makedirs(LOG_DIR, exist_ok=True)
    fmt = logging.Formatter(
        '%(asctime)s [%(levelname)-7s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )

    root = logging.getLogger("dqa")
    root.handlers.clear()
    root.setLevel(logging.DEBUG)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    fh = logging.FileHandler(str(LOG_DIR / "demo.log"), encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)


def create_demo_files(demo_dir: str):
    """创建演示文件"""
    os.makedirs(demo_dir, exist_ok=True)
    files_created = []

    with open(os.path.join(demo_dir, '技术架构文档.txt'), 'w', encoding='utf-8') as f:
        f.write("系统技术架构文档\n\n")
        f.write("1. 概述\n本系统采用微服务架构，基于Spring Boot框架开发。\n\n")
        f.write("2. 技术栈\n- 后端：Java 17, Spring Boot 3.0\n- 数据库：MySQL 8.0, Redis 7.0\n- 消息队列：RabbitMQ 3.12\n- 容器化：Docker, Kubernetes\n\n")
        f.write("3. 部署架构\n系统部署在Kubernetes集群中，支持自动扩缩容。\n" * 20)
    files_created.append('技术架构文档.txt')

    with open(os.path.join(demo_dir, '用户操作手册.md'), 'w', encoding='utf-8') as f:
        f.write("# 用户操作手册\n\n## 1. 登录系统\n访问系统首页，输入用户名和密码进行登录。\n\n")
        f.write("## 2. 数据管理\n### 2.1 数据导入\n点击数据导入按钮，选择要导入的文件。\n\n### 2.2 数据导出\n选择要导出的数据，点击导出按钮。\n\n")
        f.write("## 3. 系统设置\n在系统设置中可以配置各种参数。\n" * 30)
    files_created.append('用户操作手册.md')

    with open(os.path.join(demo_dir, 'API接口文档.html'), 'w', encoding='utf-8') as f:
        f.write("<html><head><title>API接口文档</title></head><body>")
        f.write("<h1>API接口文档</h1><h2>1. 用户管理接口</h2>")
        f.write("<p>POST /api/users - 创建用户</p><p>GET /api/users/{id} - 获取用户信息</p>")
        f.write("<h2>2. 数据接口</h2><p>POST /api/data/upload - 上传数据</p><p>GET /api/data/download - 下载数据</p>")
        f.write("</body></html>" * 10)
    files_created.append('API接口文档.html')

    with open(os.path.join(demo_dir, '员工信息表.txt'), 'w', encoding='utf-8') as f:
        f.write("员工信息表\n\n姓名：张三\n手机号：13800138000\n邮箱：zhangsan@company.com\n")
        f.write("身份证：110101199001011234\n银行卡：6222021234567890123\n\n")
        f.write("姓名：李四\n手机号：13900139000\n邮箱：lisi@company.com\n")
        f.write("身份证：110101199002022345\n银行卡：6222021234567890456\n")
    files_created.append('员工信息表.txt')

    v1 = "项目周会纪要\n\n时间：2024年1月15日\n地点：会议室A\n参会人员：张三、李四、王五\n\n会议内容：\n1. 项目进度汇报\n2. 技术方案讨论\n3. 下周计划安排\n" * 10
    with open(os.path.join(demo_dir, '会议纪要v1.txt'), 'w', encoding='utf-8') as f:
        f.write(v1)
    with open(os.path.join(demo_dir, '会议纪要v2.txt'), 'w', encoding='utf-8') as f:
        f.write(v1)
    files_created.extend(['会议纪要v1.txt', '会议纪要v2.txt'])

    with open(os.path.join(demo_dir, '便签.txt'), 'w', encoding='utf-8') as f:
        f.write("待办事项：\n1. 完成报告\n2. 发送邮件")
    files_created.append('便签.txt')

    logger.info("已创建 %d 个演示文件:", len(files_created))
    for fn in files_created:
        logger.info("  - %s", fn)

    return files_created


def run_demo():
    setup_demo_logging()

    logger.info("=" * 80)
    logger.info("文档质量评估系统 — 演示开始")
    logger.info("=" * 80)

    demo_dir = tempfile.mkdtemp(prefix='dqa_demo_')
    output_dir = os.path.join(demo_dir, 'reports')
    os.makedirs(output_dir, exist_ok=True)

    try:
        logger.info("[1/7] 创建演示文件...")
        create_demo_files(demo_dir)

        logger.info("[2/7] 初始化评估器...")
        assessor = DocumentQualityAssessor()

        logger.info("[3/7] 执行文档质量评估...")
        result = assessor.assess_directory(demo_dir)

        logger.info("[4/7] 评估结果摘要:")
        info = result['assessment_info']
        logger.info("  来源: %s  总文件: %d  待确认: %d  待审核: %d",
                    info['source'], info['total_files'],
                    result['pending_confirmation_count'], result['pending_review_count'])

        logger.info("[5/7] 各模块详情:")
        summary = result['summary']
        for section_name, section_content in summary.items():
            logger.info("\n【%s】\n%s", section_name, section_content)

        logger.info("[6/7] 生成报告...")
        report_files = assessor.generate_report(result, output_dir)
        for fmt, path in report_files.items():
            logger.info("  %s: %s (%s bytes)", fmt.upper(), path, f"{os.path.getsize(path):,}")

        logger.info("[7/7] 待确认/待审核:")
        if result['pending_confirmation']:
            logger.info("  待确认 %d 项:", len(result['pending_confirmation']))
            for i, item in enumerate(result['pending_confirmation'][:5], 1):
                logger.info("    %d. %s", i, item)
        if result['pending_review']:
            logger.info("  待审核 %d 项:", len(result['pending_review']))
            for i, item in enumerate(result['pending_review'][:5], 1):
                logger.info("    %d. %s | %s | %s", i, item.get('file_name', '?'),
                            item.get('info_type', '?'), item.get('context', '?'))

        logger.info("=" * 80)
        logger.info("✅ 演示完成!")
        logger.info("=" * 80)

        return 0

    except Exception:
        logger.exception("演示过程中发生错误")
        return 1

    finally:
        try:
            shutil.rmtree(demo_dir)
            logger.info("演示目录已清理: %s", demo_dir)
        except Exception:
            logger.warning("清理演示目录失败: %s", demo_dir)


if __name__ == '__main__':
    sys.exit(run_demo())
