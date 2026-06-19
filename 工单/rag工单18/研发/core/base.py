"""
文档质量评估核心模块
Document Quality Assessment Core Module
"""

import os
import hashlib
import logging
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import yaml
from dataclasses import dataclass, asdict
from datetime import datetime
import json

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class DocumentInfo:
    """文档信息数据类"""
    file_path: str
    file_name: str
    file_extension: str
    file_size: int  # 字节
    char_count: int
    page_count: int
    md5_hash: str
    file_type: str  # 'text', 'scan', 'mixed'
    creation_time: datetime
    modification_time: datetime
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None
    sensitive_info: List[Dict] = None
    tags: List[str] = None
    
    def __post_init__(self):
        if self.sensitive_info is None:
            self.sensitive_info = []
        if self.tags is None:
            self.tags = []


@dataclass
class AssessmentResult:
    """评估结果数据类"""
    total_files: int
    format_distribution: Dict[str, int]
    pdf_type_distribution: Dict[str, int]
    length_statistics: Dict[str, Any]
    duplicate_files: List[Dict]
    sensitive_files: List[Dict]
    pending_confirmation: List[Dict]
    pending_review: List[Dict]
    assessment_time: datetime
    config_used: Dict
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, default=str)


class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """加载配置文件"""
        if self.config_path and os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
            except Exception as e:
                logger.error(f"加载配置文件失败: {e}")
                return self._get_default_config()
        return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            'basic': {
                'supported_formats': ['.pdf', '.docx', '.doc', '.md', '.txt', '.html', '.htm', '.rtf', '.odt'],
                'max_file_size_mb': 100,
                'max_workers': 4
            },
            'pdf_classification': {
                'scan_page_char_threshold': 50,
                'scan_pdf_ratio_threshold': 0.7,
                'mixed_pdf_ratio_min': 0.3,
                'mixed_pdf_ratio_max': 0.7,
                'max_pending_confirmation': 100
            },
            'length_distribution': {
                'length_bins': [0, 100, 500, 1000, 5000, 10000, 50000, 100000, 500000],
                'percentiles': [25, 50, 75, 90, 99]
            },
            'duplicate_detection': {
                'enable_md5': True,
                'enable_simhash': False,
                'simhash_similarity_threshold': 0.85,
                'simhash_hamming_distance': 3,
                'max_pending_conflicts': 50
            },
            'sensitive_detection': {
                'enable_detection': True,
                'detection_types': {
                    'phone': {'enabled': True, 'pattern': '1[3-9]\\d{9}'},
                    'email': {'enabled': True, 'pattern': '[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}'},
                    'id_card': {'enabled': True, 'pattern': '[1-9]\\d{5}(18|19|20)\\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\\d|3[01])\\d{3}[\\dXx]'},
                    'bank_card': {'enabled': False, 'pattern': '[1-9]\\d{15,18}'}
                },
                'context_chars': 20,
                'max_detection_per_file': 50,
                'max_pending_review': 100
            },
            'classification': {
                'tags': {
                    'content_type': ['技术文档', '用户手册', 'API文档', '设计文档', '会议纪要', '研究报告', '培训材料', '其他'],
                    'quality': ['高质量', '中等质量', '低质量', '待评估'],
                    'processing_status': ['待处理', '处理中', '已完成', '有问题']
                }
            },
            'output': {
                'report_formats': ['json', 'html'],
                'report_output_dir': './reports',
                'include_details': True,
                'include_pending_lists': True
            },
            'logging': {
                'level': 'INFO',
                'log_file': './logs/assessment.log',
                'console_output': True
            },
            'progress': {
                'show_progress': True,
                'update_interval': 1,
                'enable_resume': True,
                'checkpoint_file': './checkpoints/progress.json'
            }
        }
    
    def get(self, key_path: str, default=None):
        """获取配置值，支持点分路径"""
        keys = key_path.split('.')
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value


class FileScanner:
    """文件扫描器"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.supported_formats = config.get('basic.supported_formats', [])
        self.max_file_size = config.get('basic.max_file_size_mb', 100) * 1024 * 1024
    
    def scan_directory(self, directory_path: str) -> List[str]:
        """扫描目录，返回所有支持的文件路径"""
        file_paths = []
        
        if not os.path.exists(directory_path):
            logger.error(f"目录不存在: {directory_path}")
            return file_paths
        
        if not os.path.isdir(directory_path):
            logger.error(f"路径不是目录: {directory_path}")
            return file_paths
        
        try:
            for root, dirs, files in os.walk(directory_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    
                    # 检查文件扩展名
                    file_ext = os.path.splitext(file)[1].lower()
                    if file_ext not in self.supported_formats:
                        continue
                    
                    # 检查文件大小
                    try:
                        file_size = os.path.getsize(file_path)
                        if file_size > self.max_file_size:
                            logger.warning(f"文件过大，跳过: {file_path} ({file_size / 1024 / 1024:.2f} MB)")
                            continue
                    except OSError as e:
                        logger.warning(f"无法获取文件大小: {file_path}, 错误: {e}")
                        continue
                    
                    file_paths.append(file_path)
            
            logger.info(f"扫描完成，找到 {len(file_paths)} 个支持的文件")
            return file_paths
            
        except Exception as e:
            logger.error(f"扫描目录失败: {e}")
            return file_paths
    
    def get_file_info(self, file_path: str) -> Optional[Dict]:
        """获取文件基本信息"""
        try:
            stat = os.stat(file_path)
            return {
                'file_path': file_path,
                'file_name': os.path.basename(file_path),
                'file_extension': os.path.splitext(file_path)[1].lower(),
                'file_size': stat.st_size,
                'creation_time': datetime.fromtimestamp(stat.st_ctime),
                'modification_time': datetime.fromtimestamp(stat.st_mtime)
            }
        except Exception as e:
            logger.error(f"获取文件信息失败: {file_path}, 错误: {e}")
            return None