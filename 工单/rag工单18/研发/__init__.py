"""
文档质量评估系统
Document Quality Assessment System
"""

__version__ = "1.0.0"
__author__ = "八维文化与产业研究院"

from .core.assessor import DocumentQualityAssessor
from .core.base import ConfigManager
from .api.api import create_app, run_api

__all__ = [
    'DocumentQualityAssessor',
    'ConfigManager',
    'create_app',
    'run_api'
]