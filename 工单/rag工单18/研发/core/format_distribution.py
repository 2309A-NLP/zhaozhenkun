"""
格式分布统计模块
Format Distribution Statistics Module
"""

import os
from typing import Dict, List, Any
from collections import Counter
from .base import FileScanner, ConfigManager, logger


class FormatDistributionAnalyzer:
    """格式分布统计分析器"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.file_scanner = FileScanner(config)
    
    def analyze(self, file_paths: List[str]) -> Dict[str, Any]:
        """
        分析文件格式分布
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            格式分布统计结果
        """
        if not file_paths:
            logger.warning("没有文件需要分析")
            return self._get_empty_result()
        
        # 统计各格式文件数量
        format_counter = Counter()
        total_files = len(file_paths)
        
        for file_path in file_paths:
            try:
                file_ext = os.path.splitext(file_path)[1].lower()
                format_counter[file_ext] += 1
            except Exception as e:
                logger.warning(f"处理文件格式时出错: {file_path}, 错误: {e}")
                continue
        
        # 计算占比
        format_distribution = {}
        for ext, count in format_counter.items():
            format_distribution[ext] = {
                'count': count,
                'percentage': round(count / total_files * 100, 2)
            }
        
        # 按数量排序
        sorted_formats = dict(sorted(
            format_distribution.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        ))
        
        result = {
            'total_files': total_files,
            'format_distribution': sorted_formats,
            'format_count': len(format_counter),
            'most_common_format': format_counter.most_common(1)[0] if format_counter else None
        }
        
        logger.info(f"格式分布分析完成: {total_files} 个文件，{len(format_counter)} 种格式")
        return result
    
    def _get_empty_result(self) -> Dict[str, Any]:
        """获取空结果"""
        return {
            'total_files': 0,
            'format_distribution': {},
            'format_count': 0,
            'most_common_format': None
        }
    
    def get_format_summary(self, analysis_result: Dict[str, Any]) -> str:
        """获取格式分布摘要文本"""
        if not analysis_result or analysis_result['total_files'] == 0:
            return "没有文件需要分析"
        
        summary_lines = [
            f"格式分布统计摘要:",
            f"总文件数: {analysis_result['total_files']}",
            f"格式种类: {analysis_result['format_count']}",
            "",
            "各格式分布:"
        ]
        
        for ext, info in analysis_result['format_distribution'].items():
            summary_lines.append(f"  {ext}: {info['count']} 个文件 ({info['percentage']}%)")
        
        if analysis_result['most_common_format']:
            ext, count = analysis_result['most_common_format']
            summary_lines.append(f"\n最常见格式: {ext} ({count} 个文件)")
        
        return "\n".join(summary_lines)