# -*- coding: utf-8 -*-
"""
PDF页面截图提取模块 — 从专利PDF中提取指定页面保存为图片。

功能说明：
- 从IMDR专利PDF中提取Group 2/3问题引用的页面
- 将PDF页面渲染为高分辨率PNG图片
- 支持自动创建缓存目录，避免重复提取
- 兼容Windows路径（使用tempfile获取临时目录备选）

用法:
  from pdf_extractor import extract_page_as_image
  img_path = extract_page_as_image(pdf_path, page_num=7, output_dir="./images")
"""
import logging  # 导入logging模块，用于结构化日志输出

logger = logging.getLogger(__name__)  # 获取当前模块的logger
import os  # 导入os模块，用于路径和目录操作
import tempfile  # 导入tempfile，用于跨平台临时目录
from pathlib import Path  # 导入Path类，用于跨平台路径操作
import re  # 导入re模块，用于从问题文本中提取页码


def extract_page_as_image(pdf_path, page_num, output_dir, dpi=120):
    """
    从PDF中提取指定页面并保存为PNG图片。

    参数:
        pdf_path: PDF文件的完整路径
        page_num: 页码（从1开始，如第7页=7）
        output_dir: 图片输出目录
        dpi: 图片分辨率（默认200，越大越清晰但文件越大）

    返回:
        保存的图片路径，失败返回None
    """
    try:
        import fitz  # PyMuPDF库，用于渲染PDF页面

        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

        # 生成图片文件名，格式：PDF文件名_页码.png
        pdf_name = Path(pdf_path).stem  # 去掉扩展名的PDF文件名
        image_name = f"{pdf_name}_p{page_num}.png"
        image_path = os.path.join(output_dir, image_name)

        # 如果图片已存在，直接返回（避免重复提取）
        if os.path.exists(image_path):
            return image_path

        # 打开PDF文档
        doc = fitz.open(pdf_path)

        # 检查页码是否有效
        if page_num < 1 or page_num > len(doc):
            logger.warning(f"  ⚠️ 页码越界: {page_num} (文档共{len(doc)}页)")
            doc.close()
            return None

        # 获取指定页面（PyMuPDF从0开始索引）
        page = doc[page_num - 1]

        # 渲染页面为高分辨率图像
        # matrix参数控制渲染分辨率（dpi/72）
        pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))

        # 保存为PNG图片
        pix.save(image_path)
        doc.close()

        # 打印提取信息
        file_size = os.path.getsize(image_path)
        logger.info(f"  🖼️  提取图片: {image_name} ({file_size // 1024}KB, 第{page_num}页)")

        return image_path

    except ImportError:
        logger.error("  ❌ 需要安装PyMuPDF: pip install PyMuPDF")
        return None
    except Exception as e:
        logger.error(f"  ❌ 图片提取失败: {e}")
        return None


def extract_page_from_text(pdf_base_dir, document_name, question_text, output_dir, dpi=200):
    """
    从问题文本和文档名中自动提取图片路径。

    参数:
        pdf_base_dir: PDF文件所在目录
        document_name: 文档名（如 "CN100342976C.pdf"）
        question_text: 问题文本（从中提取页码）
        output_dir: 图片输出目录
        dpi: 分辨率

    返回:
        图片路径，失败返回None
    """
    # 从问题文本中提取页码（如"第7页" → 7）
    page_match = re.search(r'第\s*(\d+)\s*页', question_text)
    if not page_match:
        return None  # 不需要图片的问题

    page_num = int(page_match.group(1))  # 提取的页码

    # 构建PDF完整路径
    pdf_path = os.path.join(pdf_base_dir, document_name)

    # 检查PDF是否存在
    if not os.path.exists(pdf_path):
        logger.warning(f"  ⚠️ PDF不存在: {pdf_path}")
        return None

    # 提取页面图片
    return extract_page_as_image(pdf_path, page_num, output_dir, dpi)


def get_pdf_directory():
    """
    获取PDF文档目录。
    优先使用项目内的patents/目录，如果不存在则报提示。

    返回:
        PDF目录路径
    """
    from pathlib import Path
    base_dir = Path(__file__).resolve().parent
    pdf_dir = base_dir / "patents"

    if not pdf_dir.exists():
        logger.warning(f"  ⚠️ PDF目录不存在: {pdf_dir}")
        logger.info(f"  💡 请将原始PDF复制到该目录，或修改config.py中的PDF_DIR")
        logger.info(f"  📂 原始PDF位置: 工单/RAG 新工单/14-17附件/original_problems/original_problems/documents/")
        # 创建空目录
        pdf_dir.mkdir(parents=True, exist_ok=True)

    return str(pdf_dir)
