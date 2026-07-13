# -*- coding: utf-8 -*-  # 工单18：指定源码编码为 UTF-8。
"""pdf_parser.py - 工单18智能助教的 PDF 文本层解析模块。"""  # 工单18：声明当前文件功能。

from __future__ import annotations  # 工单18：启用延迟类型注解。

import io  # 工单18：导入内存流模块。


def parse_pdf(file_bytes: bytes) -> dict:  # 工单18：解析 PDF 并保留页码定位信息。
    from pypdf import PdfReader  # 工单18：仅在解析 PDF 时按需导入依赖。

    reader = PdfReader(io.BytesIO(file_bytes))  # 工单18：从内存流构造 PDF 读取器。
    page_texts = []  # 工单18：初始化页级文本列表。
    chunks = []  # 工单18：初始化结构化片段列表。
    for page_index, page in enumerate(reader.pages, start=1):  # 工单18：遍历全部页面。
        text = (page.extract_text() or "").strip()  # 工单18：提取当前页文本并清洗空白。
        if not text:  # 工单18：对无文本页补充可解释提示。
            text = f"第{page_index}页未提取到文本，可能是扫描页，建议结合视觉模型进一步解析。"  # 工单18：写入扫描页说明。
        page_texts.append(text)  # 工单18：写入完整文本列表。
        chunks.append({"content": text, "summary": text[:60], "location": {"page": page_index}, "modality": "text"})  # 工单18：记录页级结构化片段。
    return {"content_text": "\n\n".join(page_texts), "chunks": chunks}  # 工单18：返回统一解析结果。
