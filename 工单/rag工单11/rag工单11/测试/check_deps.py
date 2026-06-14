import logging
logger = logging.getLogger(__name__)
"""检查已安装的依赖"""
pkgs = {
    'transformers': 'transformers',
    'sentence_transformers': 'sentence-transformers',
    'peft': 'peft',
    'fitz': 'pymupdf',  # PyMuPDF 的导入名是 fitz
    'accelerate': 'accelerate',
    'datasets': 'datasets',
}
for import_name, pkg_name in pkgs.items():
    try:
        __import__(import_name)
        print(f'✅ {pkg_name} 已安装')
    except ImportError:
        print(f'❌ {pkg_name} 未安装')
