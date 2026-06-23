"""
文档质量评估主模块
Document Quality Assessment Main Module
"""

import os
import json
import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
from pathlib import Path

from .base import ConfigManager, FileScanner, AssessmentResult, logger
from .format_distribution import FormatDistributionAnalyzer
from .pdf_classifier import PDFClassifier
from .length_distribution import LengthDistributionAnalyzer
from .duplicate_detection import DuplicateDetector
from .sensitive_detection import SensitiveInfoDetector
from .document_classifier import DocumentClassifier

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False


class DocumentQualityAssessor:
    """文档质量评估器 — 支持进度反馈与中断恢复"""

    def __init__(self, config_path: str = None):
        self.config = ConfigManager(config_path)
        self.file_scanner = FileScanner(self.config)
        self.checkpoint_file = self.config.get('progress.checkpoint_file', './checkpoints/progress.json')
        self.enable_resume = self.config.get('progress.enable_resume', True)
        self.show_progress = self.config.get('progress.show_progress', True)
        self._checkpoint_state = {}

        # 初始化各个分析器
        self.format_analyzer = FormatDistributionAnalyzer(self.config)
        self.pdf_classifier = PDFClassifier(self.config)
        self.length_analyzer = LengthDistributionAnalyzer(self.config)
        self.duplicate_detector = DuplicateDetector(self.config)
        self.sensitive_detector = SensitiveInfoDetector(self.config)
        self.document_classifier = DocumentClassifier(self.config)

        logger.info("文档质量评估器初始化完成")

    def _load_checkpoint(self, directory_path: str) -> Dict[str, Any]:
        """加载中断恢复检查点"""
        if not self.enable_resume:
            return {}
        try:
            if os.path.exists(self.checkpoint_file):
                with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                    cp = json.load(f)
                if cp.get('source') == directory_path:
                    logger.info(f"找到检查点，已完成步骤: {cp.get('completed_steps', [])}")
                    return cp
        except Exception as e:
            logger.warning(f"加载检查点失败: {e}")
        return {}

    def _save_checkpoint(self, directory_path: str, completed_steps: List[str],
                         partial_results: Dict[str, Any]):
        """保存检查点用于中断恢复"""
        try:
            checkpoint_dir = os.path.dirname(self.checkpoint_file)
            if checkpoint_dir:
                os.makedirs(checkpoint_dir, exist_ok=True)
            cp = {
                'source': directory_path,
                'timestamp': datetime.now().isoformat(),
                'completed_steps': completed_steps,
                'partial_results': partial_results
            }
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(cp, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            logger.warning(f"保存检查点失败: {e}")
    
    def assess_directory(self, directory_path: str) -> Dict[str, Any]:
        """
        评估目录中的文档质量 — 支持中断恢复与进度反馈

        Args:
            directory_path: 目录路径

        Returns:
            评估结果
        """
        logger.info(f"开始评估目录: {directory_path}")

        # 尝试加载检查点
        checkpoint = self._load_checkpoint(directory_path)
        completed_steps = checkpoint.get('completed_steps', [])
        results = checkpoint.get('partial_results', {})

        # 1. 扫描文件 (必须重新执行——文件可能变化)
        if 'scan' not in completed_steps:
            file_paths = self.file_scanner.scan_directory(directory_path)
            if not file_paths:
                logger.warning(f"目录中没有支持的文件: {directory_path}")
                return self._get_empty_assessment_result()
            logger.info(f"扫描到 {len(file_paths)} 个文件")
            results['_file_paths'] = file_paths
            completed_steps.append('scan')
            self._save_checkpoint(directory_path, completed_steps, results)
        else:
            file_paths = results.get('_file_paths', [])

        # 进度条
        total_operations = 6
        step_names = ['format_distribution', 'pdf_classification',
                       'length_distribution', 'duplicate_detection',
                       'sensitive_detection', 'document_classification']
        pbar = tqdm(total=total_operations, desc="评估进度", disable=not (self.show_progress and TQDM_AVAILABLE))

        # 2.1 格式分布统计
        if 'format_distribution' not in completed_steps:
            results['format_distribution'] = self.format_analyzer.analyze(file_paths)
            completed_steps.append('format_distribution')
            self._save_checkpoint(directory_path, completed_steps, results)
        pbar.update(1)

        # 2.2 PDF分类
        if 'pdf_classification' not in completed_steps:
            pdf_files = [f for f in file_paths if f.lower().endswith('.pdf')]
            if pdf_files:
                results['pdf_classification'] = self.pdf_classifier.classify_multiple_pdfs(pdf_files)
            else:
                results['pdf_classification'] = {'total_pdfs': 0, 'type_distribution': {}}
            completed_steps.append('pdf_classification')
            self._save_checkpoint(directory_path, completed_steps, results)
        pbar.update(1)

        # 2.3 文档长度分布
        if 'length_distribution' not in completed_steps:
            results['length_distribution'] = self.length_analyzer.analyze(file_paths)
            completed_steps.append('length_distribution')
            self._save_checkpoint(directory_path, completed_steps, results)
        pbar.update(1)

        # 2.4 重复检测
        if 'duplicate_detection' not in completed_steps:
            results['duplicate_detection'] = self.duplicate_detector.detect_duplicates(file_paths)
            completed_steps.append('duplicate_detection')
            self._save_checkpoint(directory_path, completed_steps, results)
        pbar.update(1)

        # 2.5 敏感信息检测
        if 'sensitive_detection' not in completed_steps:
            results['sensitive_detection'] = self.sensitive_detector.detect_sensitive_info(file_paths)
            completed_steps.append('sensitive_detection')
            self._save_checkpoint(directory_path, completed_steps, results)
        pbar.update(1)

        # 2.6 文档分类
        if 'document_classification' not in completed_steps:
            results['document_classification'] = self.document_classifier.batch_classify(file_paths)
            completed_steps.append('document_classification')
            self._save_checkpoint(directory_path, completed_steps, results)
        pbar.update(1)
        pbar.close()

        # 3. 清理内部数据
        results.pop('_file_paths', None)

        # 4. 生成综合评估结果
        assessment_result = self._compile_assessment_result(results, directory_path)

        # 5. 评估完成，清除检查点
        try:
            if os.path.exists(self.checkpoint_file):
                os.remove(self.checkpoint_file)
        except Exception:
            pass

        logger.info("文档质量评估完成")
        return assessment_result
    
    def assess_files(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        评估指定文件的质量
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            评估结果
        """
        logger.info(f"开始评估 {len(file_paths)} 个文件")
        
        # 验证文件存在性
        valid_files = []
        for file_path in file_paths:
            if os.path.exists(file_path):
                valid_files.append(file_path)
            else:
                logger.warning(f"文件不存在: {file_path}")
        
        if not valid_files:
            logger.warning("没有有效的文件需要评估")
            return self._get_empty_assessment_result()
        
        # 执行各项分析
        results = {}
        
        # 格式分布统计
        results['format_distribution'] = self.format_analyzer.analyze(valid_files)
        
        # PDF分类
        pdf_files = [f for f in valid_files if f.lower().endswith('.pdf')]
        if pdf_files:
            results['pdf_classification'] = self.pdf_classifier.classify_multiple_pdfs(pdf_files)
        else:
            results['pdf_classification'] = {'total_pdfs': 0, 'type_distribution': {}}
        
        # 文档长度分布
        results['length_distribution'] = self.length_analyzer.analyze(valid_files)
        
        # 重复检测
        results['duplicate_detection'] = self.duplicate_detector.detect_duplicates(valid_files)
        
        # 敏感信息检测
        results['sensitive_detection'] = self.sensitive_detector.detect_sensitive_info(valid_files)
        
        # 文档分类
        results['document_classification'] = self.document_classifier.batch_classify(valid_files)
        
        # 生成综合评估结果
        assessment_result = self._compile_assessment_result(results, "指定文件")
        
        logger.info("文档质量评估完成")
        return assessment_result
    
    def _compile_assessment_result(self, results: Dict[str, Any], source: str) -> Dict[str, Any]:
        """编译评估结果"""
        # 统计总体信息
        total_files = results['format_distribution'].get('total_files', 0)
        
        # 收集待确认和待审核项目
        pending_confirmation = []
        pending_review = []
        
        # 从PDF分类中收集待确认项
        if 'pdf_classification' in results:
            pending_confirmation.extend(
                results['pdf_classification'].get('pending_confirmation_list', [])
            )
        
        # 从重复检测中收集待确认项
        if 'duplicate_detection' in results:
            pending_confirmation.extend(
                results['duplicate_detection'].get('simhash_similar', [])
            )
        
        # 从敏感信息检测中收集待审核项
        if 'sensitive_detection' in results:
            pending_review.extend(
                results['sensitive_detection'].get('pending_review_list', [])
            )
        
        # 生成评估摘要
        summary = self._generate_summary(results)
        
        assessment_result = {
            'assessment_info': {
                'source': source,
                'assessment_time': datetime.now().isoformat(),
                'total_files': total_files,
                'config_used': self.config.config
            },
            'results': results,
            'summary': summary,
            'pending_confirmation': pending_confirmation,
            'pending_review': pending_review,
            'pending_confirmation_count': len(pending_confirmation),
            'pending_review_count': len(pending_review)
        }
        
        return assessment_result
    
    def _generate_summary(self, results: Dict[str, Any]) -> Dict[str, str]:
        """生成评估摘要"""
        summary = {}
        
        # 格式分布摘要
        if 'format_distribution' in results:
            summary['format_distribution'] = self.format_analyzer.get_format_summary(
                results['format_distribution']
            )
        
        # PDF分类摘要
        if 'pdf_classification' in results:
            summary['pdf_classification'] = self.pdf_classifier.get_classification_summary(
                results['pdf_classification']
            )
        
        # 文档长度分布摘要
        if 'length_distribution' in results:
            summary['length_distribution'] = self.length_analyzer.get_length_summary(
                results['length_distribution']
            )
        
        # 重复检测摘要
        if 'duplicate_detection' in results:
            summary['duplicate_detection'] = self.duplicate_detector.get_duplicate_summary(
                results['duplicate_detection']
            )
        
        # 敏感信息检测摘要
        if 'sensitive_detection' in results:
            summary['sensitive_detection'] = self.sensitive_detector.get_sensitive_summary(
                results['sensitive_detection']
            )
        
        # 文档分类摘要
        if 'document_classification' in results:
            summary['document_classification'] = self.document_classifier.get_classification_summary(
                results['document_classification']
            )
        
        return summary
    
    def _get_empty_assessment_result(self) -> Dict[str, Any]:
        """获取空评估结果"""
        return {
            'assessment_info': {
                'source': '',
                'assessment_time': datetime.now().isoformat(),
                'total_files': 0,
                'config_used': self.config.config
            },
            'results': {},
            'summary': {},
            'pending_confirmation': [],
            'pending_review': [],
            'pending_confirmation_count': 0,
            'pending_review_count': 0
        }
    
    def generate_report(self, assessment_result: Dict[str, Any], output_dir: str = None, formats: List[str] = None) -> Dict[str, str]:
        """
        生成评估报告
        
        Args:
            assessment_result: 评估结果
            output_dir: 输出目录
            formats: 报告格式列表
            
        Returns:
            生成的报告文件路径
        """
        if output_dir is None:
            output_dir = self.config.get('output.report_output_dir', './reports')
        
        if formats is None:
            formats = self.config.get('output.report_formats', ['json', 'html'])
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        
        report_files = {}
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        for format_type in formats:
            try:
                if format_type == 'json':
                    report_path = self._generate_json_report(assessment_result, output_dir, timestamp)
                    report_files['json'] = report_path
                elif format_type == 'html':
                    report_path = self._generate_html_report(assessment_result, output_dir, timestamp)
                    report_files['html'] = report_path
                else:
                    logger.warning(f"不支持的报告格式: {format_type}")
            except Exception as e:
                logger.error(f"生成{format_type}报告失败: {e}")
        
        logger.info(f"报告生成完成: {list(report_files.keys())}")
        return report_files
    
    def _generate_json_report(self, assessment_result: Dict[str, Any], output_dir: str, timestamp: str) -> str:
        """生成JSON报告"""
        report_path = os.path.join(output_dir, f'assessment_report_{timestamp}.json')
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(assessment_result, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"JSON报告已生成: {report_path}")
        return report_path
    
    def _generate_html_report(self, assessment_result: Dict[str, Any], output_dir: str, timestamp: str) -> str:
        """生成HTML报告"""
        report_path = os.path.join(output_dir, f'assessment_report_{timestamp}.html')
        
        # 生成HTML内容
        html_content = self._create_html_content(assessment_result)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"HTML报告已生成: {report_path}")
        return report_path
    
    def _create_html_content(self, assessment_result: Dict[str, Any]) -> str:
        """创建HTML报告内容"""
        info = assessment_result.get('assessment_info', {})
        summary = assessment_result.get('summary', {})
        pending_confirmation = assessment_result.get('pending_confirmation', [])
        pending_review = assessment_result.get('pending_review', [])
        
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>文档质量评估报告</title>
    <style>
        body {{
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            text-align: center;
            border-bottom: 3px solid #007bff;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #007bff;
            margin-top: 30px;
        }}
        .info-section {{
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .summary-section {{
            margin-bottom: 30px;
        }}
        .summary-box {{
            background-color: #e9ecef;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 10px;
            white-space: pre-wrap;
            font-family: monospace;
        }}
        .pending-section {{
            margin-top: 30px;
        }}
        .pending-item {{
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            padding: 10px;
            margin-bottom: 10px;
            border-radius: 5px;
        }}
        .pending-item.warning {{
            background-color: #f8d7da;
            border-color: #f5c6cb;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }}
        th {{
            background-color: #007bff;
            color: white;
        }}
        tr:nth-child(even) {{
            background-color: #f2f2f2;
        }}
        .footer {{
            margin-top: 30px;
            text-align: center;
            color: #666;
            font-size: 14px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>文档质量评估报告</h1>
        
        <div class="info-section">
            <h3>评估基本信息</h3>
            <p><strong>评估来源:</strong> {info.get('source', 'N/A')}</p>
            <p><strong>评估时间:</strong> {info.get('assessment_time', 'N/A')}</p>
            <p><strong>总文件数:</strong> {info.get('total_files', 0)}</p>
        </div>
        
        <div class="summary-section">
            <h2>评估结果摘要</h2>
"""
        
        # 添加各个摘要部分
        for section_name, section_content in summary.items():
            section_title = {
                'format_distribution': '格式分布统计',
                'pdf_classification': 'PDF分类结果',
                'length_distribution': '文档长度分布',
                'duplicate_detection': '重复检测结果',
                'sensitive_detection': '敏感信息检测',
                'document_classification': '文档分类结果'
            }.get(section_name, section_name)
            
            html += f"""
            <h3>{section_title}</h3>
            <div class="summary-box">{section_content}</div>
"""
        
        # 添加待确认部分
        if pending_confirmation:
            html += """
        <div class="pending-section">
            <h2>待确认项目</h2>
"""
            for i, item in enumerate(pending_confirmation[:10], 1):
                html += f"""
            <div class="pending-item">
                <strong>{i}. {item.get('file_name', 'N/A')}</strong><br>
                <small>类型: {item.get('type', 'N/A')} | 相似度: {item.get('similarity', 'N/A')}</small>
            </div>
"""
            if len(pending_confirmation) > 10:
                html += f"<p><em>... 还有 {len(pending_confirmation) - 10} 个待确认项目</em></p>"
            html += "</div>"
        
        # 添加待审核部分
        if pending_review:
            html += """
        <div class="pending-section">
            <h2>待审核项目</h2>
"""
            for i, item in enumerate(pending_review[:10], 1):
                html += f"""
            <div class="pending-item warning">
                <strong>{i}. {item.get('file_name', 'N/A')}</strong><br>
                <small>类型: {item.get('info_type', 'N/A')} | 上下文: {item.get('context', 'N/A')}</small>
            </div>
"""
            if len(pending_review) > 10:
                html += f"<p><em>... 还有 {len(pending_review) - 10} 个待审核项目</em></p>"
            html += "</div>"
        
        html += """
        <div class="footer">
            <p>报告由文档质量评估系统自动生成</p>
        </div>
    </div>
</body>
</html>
"""
        
        return html