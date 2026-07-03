"""
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
文档加载器 —— 支持 PDF、TXT、DOCX
"""

import os
import logging
from typing import List, Dict, Tuple
from pathlib import Path

_log = logging.getLogger("medical_agent.rag.document_loader")


def load_pdf(file_path: str) -> List[str]:
    """加载 PDF 文件，返回文本块列表"""
    try:
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        chunks = []
        for page in reader.pages:
            text = page.extract_text()
            if text and text.strip():
                # 按段落分块
                paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
                chunks.extend(paragraphs)
        return chunks
    except Exception as e:
        raise RuntimeError(f"PDF 加载失败 {file_path}: {e}")


def load_txt(file_path: str) -> List[str]:
    """加载文本文件，按段落分块"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        chunks = [p.strip() for p in text.split("\n\n") if p.strip()]
        return chunks
    except Exception as e:
        raise RuntimeError(f"TXT 加载失败 {file_path}: {e}")


def load_docx(file_path: str) -> List[str]:
    """加载 Word 文档"""
    try:
        from docx import Document
        doc = Document(file_path)
        chunks = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                chunks.append(text)
        return chunks
    except Exception as e:
        raise RuntimeError(f"DOCX 加载失败 {file_path}: {e}")


def load_document(file_path: str) -> Tuple[List[str], Dict]:
    """
    根据文件类型加载文档

    Returns:
        (文本块列表, 元数据)
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    loaders = {
        ".pdf": load_pdf,
        ".txt": load_txt,
        ".docx": load_docx,
    }

    loader = loaders.get(ext)
    if loader is None:
        raise ValueError(f"不支持的文件格式: {ext}，支持的格式: {list(loaders.keys())}")

    chunks = loader(file_path)

    metadata = {
        "source": path.name,
        "type": ext,
        "size": os.path.getsize(file_path),
        "chunks": len(chunks),
    }

    return chunks, metadata


def load_directory(dir_path: str) -> List[Tuple[List[str], Dict]]:
    """
    加载目录下所有支持的文档

    Returns:
        [(文本块列表, 元数据), ...]
    """
    results = []
    supported_exts = {".pdf", ".txt", ".docx"}

    for root, dirs, files in os.walk(dir_path):
        for fname in files:
            fpath = os.path.join(root, fname)
            ext = Path(fname).suffix.lower()
            if ext in supported_exts:
                try:
                    chunks, meta = load_document(fpath)
                    results.append((chunks, meta))
                except Exception as e:
                    _log.warning("跳过 %s: %s", fname, e)

    return results
