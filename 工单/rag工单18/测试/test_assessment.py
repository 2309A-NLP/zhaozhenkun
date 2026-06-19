#!/usr/bin/env python3
"""
文档质量评估系统测试脚本
Document Quality Assessment System Test Script
"""

import os
import sys
import json
import logging
import tempfile
import shutil
from pathlib import Path

# 添加研发目录到Python路径
project_root = Path(__file__).parent.parent / "研发"
sys.path.insert(0, str(project_root))

from core.assessor import DocumentQualityAssessor
from core.base import ConfigManager

# 日志配置
logger = logging.getLogger("dqa.test")
LOG_DIR = Path(__file__).parent.parent / "logs"


def setup_test_logging(log_file: str = None):
    """测试专用日志配置"""
    os.makedirs(LOG_DIR, exist_ok=True)
    if log_file is None:
        log_file = str(LOG_DIR / "test.log")

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

    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    root.addHandler(fh)

    return logger


def create_test_files(test_dir: str):
    """创建测试文件"""
    os.makedirs(test_dir, exist_ok=True)

    with open(os.path.join(test_dir, 'test.txt'), 'w', encoding='utf-8') as f:
        f.write('这是一个测试文本文件。\n' * 100)

    with open(os.path.join(test_dir, 'test.md'), 'w', encoding='utf-8') as f:
        f.write('# 测试标题\n\n这是测试内容。\n' * 50)

    with open(os.path.join(test_dir, 'test.html'), 'w', encoding='utf-8') as f:
        f.write('<html><body><h1>测试</h1><p>内容</p></body></html>' * 20)

    with open(os.path.join(test_dir, 'sensitive.txt'), 'w', encoding='utf-8') as f:
        f.write('手机号：13800138000\n')
        f.write('邮箱：test@example.com\n')
        f.write('身份证：110101199001011234\n')
        f.write('银行卡：6222021234567890123\n')

    with open(os.path.join(test_dir, 'duplicate1.txt'), 'w', encoding='utf-8') as f:
        f.write('这是重复的内容。\n' * 10)

    with open(os.path.join(test_dir, 'duplicate2.txt'), 'w', encoding='utf-8') as f:
        f.write('这是重复的内容。\n' * 10)

    logger.info("测试文件已创建: %s (%d 个文件)", test_dir, 6)


def test_format_distribution(assessor: DocumentQualityAssessor, test_dir: str):
    """测试格式分布统计"""
    logger.info("=" * 60)
    logger.info("测试: 格式分布统计")

    result = assessor.format_analyzer.analyze(
        assessor.file_scanner.scan_directory(test_dir)
    )

    logger.info("总文件数: %d  格式种类: %d", result['total_files'], result['format_count'])
    for ext, info in result['format_distribution'].items():
        logger.info("  %s: %d 个文件 (%.2f%%)", ext, info['count'], info['percentage'])

    return result


def test_length_distribution(assessor: DocumentQualityAssessor, test_dir: str):
    """测试文档长度分布"""
    logger.info("=" * 60)
    logger.info("测试: 文档长度分布")

    file_paths = assessor.file_scanner.scan_directory(test_dir)
    result = assessor.length_analyzer.analyze(file_paths)

    stats = result['statistics']
    logger.info("总文件数: %d", result['total_files'])
    logger.info("总字符数: %s  平均字符数: %.2f",
                f"{stats.get('total_chars', 0):,}", stats.get('avg_chars', 0))

    pcts = stats.get('percentiles', {})
    logger.info("分位数: %s", ", ".join(f"{k}={v:,.0f}" for k, v in pcts.items()))

    return result


def test_duplicate_detection(assessor: DocumentQualityAssessor, test_dir: str):
    """测试重复检测"""
    logger.info("=" * 60)
    logger.info("测试: 重复检测")

    file_paths = assessor.file_scanner.scan_directory(test_dir)
    result = assessor.duplicate_detector.detect_duplicates(file_paths)

    logger.info("总文件数: %d  重复组: %d  重复文件数: %d",
                result['total_files'], result['duplicate_groups'], result['duplicate_file_count'])

    for i, group in enumerate(result['md5_duplicates'][:3], 1):
        logger.info("  组 %d: %d 个文件 — %s", i, group['count'],
                    ", ".join(os.path.basename(f) for f in group['files'][:2]))

    return result


def test_sensitive_detection(assessor: DocumentQualityAssessor, test_dir: str):
    """测试敏感信息检测"""
    logger.info("=" * 60)
    logger.info("测试: 敏感信息检测")

    file_paths = assessor.file_scanner.scan_directory(test_dir)
    result = assessor.sensitive_detector.detect_sensitive_info(file_paths)

    logger.info("总文件数: %d  含敏感文件: %d  检测总数: %d",
                result['total_files'], result['files_with_sensitive'], result['total_detections'])

    for info_type, count in result['type_distribution'].items():
        logger.info("  %s: %d 处", info_type, count)

    for i, item in enumerate(result['pending_review_list'][:3], 1):
        logger.info("  待审 %d: %s | %s | %s", i, item['file_name'], item['info_type'], item['context'])

    return result


def test_full_assessment(assessor: DocumentQualityAssessor, test_dir: str):
    """测试完整评估"""
    logger.info("=" * 60)
    logger.info("测试: 完整评估流程")

    result = assessor.assess_directory(test_dir)

    info = result['assessment_info']
    logger.info("来源: %s  总文件: %d  待确认: %d  待审核: %d",
                info['source'], info['total_files'],
                result['pending_confirmation_count'], result['pending_review_count'])

    for section_name, section_content in result['summary'].items():
        short = section_content[:300] + "..." if len(section_content) > 300 else section_content
        logger.debug("[%s]\n%s", section_name, short)

    return result


def test_report_generation(assessor: DocumentQualityAssessor, test_dir: str, output_dir: str):
    """测试报告生成"""
    logger.info("=" * 60)
    logger.info("测试: 报告生成")

    result = assessor.assess_directory(test_dir)
    report_files = assessor.generate_report(result, output_dir)

    for fmt, path in report_files.items():
        if os.path.exists(path):
            logger.info("  %s: %s (%s bytes)", fmt.upper(), path, f"{os.path.getsize(path):,}")
        else:
            logger.error("  %s: 生成失败", fmt.upper())

    return report_files


def main():
    setup_test_logging()

    logger.info("=" * 60)
    logger.info("文档质量评估系统 — 单元测试开始")
    logger.info("=" * 60)

    test_dir = tempfile.mkdtemp(prefix='dqa_test_')
    output_dir = os.path.join(test_dir, 'reports')
    os.makedirs(output_dir, exist_ok=True)

    try:
        create_test_files(test_dir)
        assessor = DocumentQualityAssessor()

        test_format_distribution(assessor, test_dir)
        test_length_distribution(assessor, test_dir)
        test_duplicate_detection(assessor, test_dir)
        test_sensitive_detection(assessor, test_dir)
        test_full_assessment(assessor, test_dir)
        test_report_generation(assessor, test_dir, output_dir)

        logger.info("=" * 60)
        logger.info("✅ 所有测试完成!")
        logger.info("=" * 60)

        if os.path.exists(output_dir):
            logger.info("报告目录: %s", output_dir)
            for fname in os.listdir(output_dir):
                logger.info("  - %s", fname)

        return 0

    except Exception:
        logger.exception("测试过程中发生错误")
        return 1

    finally:
        try:
            shutil.rmtree(test_dir)
            logger.info("测试目录已清理: %s", test_dir)
        except Exception:
            logger.warning("清理测试目录失败: %s", test_dir, exc_info=True)


if __name__ == '__main__':
    sys.exit(main())
