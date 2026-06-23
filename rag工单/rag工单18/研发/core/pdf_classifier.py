"""
PDF页面类型识别模块
PDF Page Type Classification Module
"""

import os
from typing import Dict, List, Any, Tuple
from .base import ConfigManager, logger

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    logger.warning("pdfplumber未安装，PDF分类功能将不可用。请运行: pip install pdfplumber")


class PDFClassifier:
    """PDF分类器"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.scan_page_char_threshold = config.get('pdf_classification.scan_page_char_threshold', 50)
        self.scan_pdf_ratio_threshold = config.get('pdf_classification.scan_pdf_ratio_threshold', 0.7)
        self.mixed_pdf_ratio_min = config.get('pdf_classification.mixed_pdf_ratio_min', 0.3)
        self.mixed_pdf_ratio_max = config.get('pdf_classification.mixed_pdf_ratio_max', 0.7)
        self.max_pending_confirmation = config.get('pdf_classification.max_pending_confirmation', 100)
    
    def classify_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """
        分类PDF文件类型
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            分类结果字典
        """
        if not PDFPLUMBER_AVAILABLE:
            return self._get_error_result(pdf_path, "pdfplumber未安装")
        
        if not os.path.exists(pdf_path):
            return self._get_error_result(pdf_path, "文件不存在")
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                if total_pages == 0:
                    return self._get_error_result(pdf_path, "PDF文件为空")
                
                scan_pages = 0
                text_pages = 0
                page_details = []
                
                for i, page in enumerate(pdf.pages):
                    try:
                        # 提取文本
                        text = page.extract_text() or ""
                        char_count = len(text.strip())
                        
                        # 判断页面类型
                        is_scan_page = char_count < self.scan_page_char_threshold
                        
                        if is_scan_page:
                            scan_pages += 1
                            page_type = "scan"
                        else:
                            text_pages += 1
                            page_type = "text"
                        
                        page_details.append({
                            'page_number': i + 1,
                            'char_count': char_count,
                            'page_type': page_type,
                            'is_scan': is_scan_page
                        })
                        
                    except Exception as e:
                        logger.warning(f"处理PDF页面时出错: {pdf_path}, 页面 {i+1}, 错误: {e}")
                        page_details.append({
                            'page_number': i + 1,
                            'char_count': 0,
                            'page_type': "unknown",
                            'is_scan': True,
                            'error': str(e)
                        })
                        scan_pages += 1
                
                # 计算扫描页比例
                scan_ratio = scan_pages / total_pages if total_pages > 0 else 0
                
                # 确定PDF类型
                if scan_ratio >= self.scan_pdf_ratio_threshold:
                    pdf_type = "scan"
                elif scan_ratio <= self.mixed_pdf_ratio_min:
                    pdf_type = "text"
                else:
                    pdf_type = "mixed"
                
                # 判断是否需要人工确认
                needs_confirmation = (
                    self.mixed_pdf_ratio_min < scan_ratio < self.scan_pdf_ratio_threshold
                )
                
                result = {
                    'file_path': pdf_path,
                    'file_name': os.path.basename(pdf_path),
                    'total_pages': total_pages,
                    'scan_pages': scan_pages,
                    'text_pages': text_pages,
                    'scan_ratio': round(scan_ratio, 4),
                    'pdf_type': pdf_type,
                    'needs_confirmation': needs_confirmation,
                    'page_details': page_details,
                    'classification_confidence': self._calculate_confidence(scan_ratio)
                }
                
                logger.info(f"PDF分类完成: {pdf_path} -> {pdf_type} (扫描页比例: {scan_ratio:.2%})")
                return result
                
        except Exception as e:
            logger.error(f"处理PDF文件时出错: {pdf_path}, 错误: {e}")
            return self._get_error_result(pdf_path, str(e))
    
    def _calculate_confidence(self, scan_ratio: float) -> str:
        """计算分类置信度"""
        if scan_ratio >= 0.9 or scan_ratio <= 0.1:
            return "high"
        elif scan_ratio >= 0.7 or scan_ratio <= 0.3:
            return "medium"
        else:
            return "low"
    
    def _get_error_result(self, pdf_path: str, error_msg: str) -> Dict[str, Any]:
        """获取错误结果"""
        return {
            'file_path': pdf_path,
            'file_name': os.path.basename(pdf_path),
            'error': error_msg,
            'pdf_type': "unknown",
            'needs_confirmation': True,
            'classification_confidence': "none"
        }
    
    def classify_multiple_pdfs(self, pdf_paths: List[str]) -> Dict[str, Any]:
        """
        批量分类PDF文件
        
        Args:
            pdf_paths: PDF文件路径列表
            
        Returns:
            批量分类结果
        """
        results = []
        pending_confirmation = []
        
        for pdf_path in pdf_paths:
            result = self.classify_pdf(pdf_path)
            results.append(result)
            
            if result.get('needs_confirmation', False):
                pending_confirmation.append(result)
        
        # 统计各类型数量
        type_counter = {}
        for result in results:
            pdf_type = result.get('pdf_type', 'unknown')
            type_counter[pdf_type] = type_counter.get(pdf_type, 0) + 1
        
        # 限制待确认列表数量
        if len(pending_confirmation) > self.max_pending_confirmation:
            pending_confirmation = pending_confirmation[:self.max_pending_confirmation]
        
        summary = {
            'total_pdfs': len(results),
            'type_distribution': type_counter,
            'pending_confirmation_count': len(pending_confirmation),
            'pending_confirmation_list': pending_confirmation,
            'classification_results': results
        }
        
        logger.info(f"批量PDF分类完成: {len(results)} 个文件")
        return summary
    
    def get_classification_summary(self, classification_result: Dict[str, Any]) -> str:
        """获取分类结果摘要"""
        if not classification_result or classification_result.get('total_pdfs', 0) == 0:
            return "没有PDF文件需要分类"
        
        summary_lines = [
            f"PDF分类结果摘要:",
            f"总PDF文件数: {classification_result['total_pdfs']}",
            "",
            "类型分布:"
        ]
        
        for pdf_type, count in classification_result['type_distribution'].items():
            percentage = round(count / classification_result['total_pdfs'] * 100, 2)
            summary_lines.append(f"  {pdf_type}: {count} 个文件 ({percentage}%)")
        
        if classification_result['pending_confirmation_count'] > 0:
            summary_lines.append(f"\n待确认文件: {classification_result['pending_confirmation_count']} 个")
            summary_lines.append("（需要人工确认的文件已添加到待确认列表）")
        
        return "\n".join(summary_lines)