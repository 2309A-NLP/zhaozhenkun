"""
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
文档加载器 —— 支持 PDF、TXT、DOCX
"""

import os  # 导入操作系统接口模块，用于获取文件大小等操作
import logging  # 导入日志模块，用于记录警告和错误信息
from typing import List, Dict, Tuple  # 导入类型提示：List（列表）、Dict（字典）、Tuple（元组）
from pathlib import Path  # 导入Path用于跨平台文件路径处理

_log = logging.getLogger("medical_agent.rag.document_loader")  # 创建模块级日志记录器，标识为"medical_agent.rag.document_loader"


def load_pdf(file_path: str) -> List[str]:  # PDF文档加载函数：输入文件路径，返回文本段落列表
    """加载 PDF 文件，返回文本块列表"""
    try:  # 异常捕获：处理文件不存在或格式损坏
        from pypdf import PdfReader  # 导入pypdf库的PdfReader类用于读取PDF
        reader = PdfReader(file_path)  # 创建PDF读取器实例，打开指定文件
        chunks = []  # 初始化文本块列表为空
        for page in reader.pages:  # 遍历PDF中的每一页
            text = page.extract_text()  # 从当前页提取文本内容
            if text and text.strip():  # 如果提取的文本存在且去除空白后不为空
                # 按段落分块  # 注释：以双换行为分隔符拆分段落
                paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]  # 按双换行拆分为段落列表，过滤空段落并去除首尾空白
                chunks.extend(paragraphs)  # 将本页的段落追加到总块列表中
        return chunks  # 返回所有页面的文本段落列表
    except Exception as e:  # 捕获所有异常
        raise RuntimeError(f"PDF 加载失败 {file_path}: {e}")  # 抛出运行时错误，包含文件路径和原始错误信息


def load_txt(file_path: str) -> List[str]:  # 文本文件加载函数：输入文件路径，返回文本段落列表
    """加载文本文件，按段落分块"""
    try:  # 异常捕获
        with open(file_path, "r", encoding="utf-8") as f:  # 以UTF-8编码读取文本文件
            text = f.read()  # 读取文件的全部文本内容
        chunks = [p.strip() for p in text.split("\n\n") if p.strip()]  # 按双换行拆分为段落，去除空白并过滤空段
        return chunks  # 返回文本段落列表
    except Exception as e:  # 捕获所有异常
        raise RuntimeError(f"TXT 加载失败 {file_path}: {e}")  # 抛出运行时错误，包含文件路径和错误信息


def load_docx(file_path: str) -> List[str]:  # Word文档加载函数：输入文件路径，返回文本段落列表
    """加载 Word 文档"""
    try:  # 异常捕获
        from docx import Document  # 导入python-docx库的Document类
        doc = Document(file_path)  # 创建Word文档对象，读取指定文件
        chunks = []  # 初始化文本块列表
        for para in doc.paragraphs:  # 遍历文档中的每个段落
            text = para.text.strip()  # 获取段落文本并去除首尾空白
            if text:  # 如果段落文本非空
                chunks.append(text)  # 将非空段落添加到结果列表
        return chunks  # 返回提取的段落列表
    except Exception as e:  # 捕获所有异常
        raise RuntimeError(f"DOCX 加载失败 {file_path}: {e}")  # 抛出运行时错误，包含文件路径和错误信息


def load_document(file_path: str) -> Tuple[List[str], Dict]:  # 通用文档加载函数：根据扩展名自动选择加载器
    """
    根据文件类型加载文档

    Returns:
        (文本块列表, 元数据)
    """
    path = Path(file_path)  # 将文件路径字符串转为Path对象
    ext = path.suffix.lower()  # 提取文件扩展名并转为小写（如".PDF"→".pdf"）

    loaders = {  # 建立文件扩展名到加载函数的映射字典
        ".pdf": load_pdf,  # PDF文件使用load_pdf加载
        ".txt": load_txt,  # TXT文件使用load_txt加载
        ".docx": load_docx,  # DOCX文件使用load_docx加载
    }

    loader = loaders.get(ext)  # 根据扩展名查找对应的加载函数
    if loader is None:  # 如果未找到匹配的加载函数（不支持的文件格式）
        raise ValueError(f"不支持的文件格式: {ext}，支持的格式: {list(loaders.keys())}")  # 抛出值错误，列出支持的格式

    chunks = loader(file_path)  # 调用对应的加载函数处理文件，获取文本段落列表

    metadata = {  # 构建文件元数据字典
        "source": path.name,  # 文件名（含扩展名）作为来源信息
        "type": ext,  # 文件类型（扩展名）
        "size": os.path.getsize(file_path),  # 文件大小（字节数）
        "chunks": len(chunks),  # 提取出的文本段落数量
    }

    return chunks, metadata  # 返回文本段落列表和元数据元组


def load_directory(dir_path: str) -> List[Tuple[List[str], Dict]]:  # 目录批量加载函数：加载目录下所有支持的文档
    """
    加载目录下所有支持的文档

    Returns:
        [(文本块列表, 元数据), ...]
    """
    results = []  # 初始化结果列表，每个元素是(文本块列表, 元数据)元组
    supported_exts = {".pdf", ".txt", ".docx"}  # 定义支持的文件扩展名集合

    for root, dirs, files in os.walk(dir_path):  # 递归遍历目录树：root为当前目录，dirs为子目录列表，files为文件列表
        for fname in files:  # 遍历当前目录下的所有文件
            fpath = os.path.join(root, fname)  # 拼接得到文件的完整路径
            ext = Path(fname).suffix.lower()  # 提取文件扩展名并转小写
            if ext in supported_exts:  # 如果文件扩展名在支持列表中
                try:  # 异常捕获：单个文件加载失败不影响其他文件
                    chunks, meta = load_document(fpath)  # 调用通用加载函数处理文件
                    results.append((chunks, meta))  # 将文本块和元数据追加到结果列表
                except Exception as e:  # 捕获单个文件的加载异常
                    _log.warning("跳过 %s: %s", fname, e)  # 记录警告日志，跳过异常文件继续处理

    return results  # 返回所有成功加载的文档结果列表
