# -*- coding: utf-8 -*-  # 工单18：指定源码编码为 UTF-8。
"""docx_parser.py - 工单18智能助教的 DOCX 结构化解析模块。"""  # 工单18：声明当前文件功能。

from __future__ import annotations  # 工单18：启用延迟类型注解。

import io  # 工单18：导入内存流模块。
import zipfile  # 工单18：导入压缩包处理模块。
from xml.etree import ElementTree as ET  # 工单18：导入 XML 解析模块。

WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}  # 工单18：定义 Word XML 命名空间。


def _text_of(node: ET.Element) -> str:  # 工单18：提取节点内全部文本。
    values = [text.text or "" for text in node.findall(".//w:t", WORD_NS)]  # 工单18：提取全部文本节点内容。
    return "".join(values).strip()  # 工单18：拼接后返回清洗文本。


def parse_docx(file_bytes: bytes) -> dict:  # 工单18：解析 DOCX 文档正文与表格内容。
    archive = zipfile.ZipFile(io.BytesIO(file_bytes))  # 工单18：打开 DOCX 压缩包。
    xml_bytes = archive.read("word/document.xml")  # 工单18：读取主文档 XML。
    root = ET.fromstring(xml_bytes)  # 工单18：解析 XML 根节点。
    lines = []  # 工单18：初始化完整文本列表。
    chunks = []  # 工单18：初始化结构化片段列表。
    block_index = 0  # 工单18：初始化文档块编号。
    for child in root.iterfind(".//w:body/*", WORD_NS):  # 工单18：遍历正文下的一级块节点。
        tag = child.tag.split("}")[-1]  # 工单18：提取当前节点标签名。
        if tag == "p":  # 工单18：处理普通段落。
            text = _text_of(child)  # 工单18：提取段落文本。
            if not text:  # 工单18：跳过空段落。
                continue  # 工单18：继续处理下一个块。
            block_index += 1  # 工单18：递增块编号。
            lines.append(text)  # 工单18：写入完整文本列表。
            chunks.append({"content": text, "summary": text[:60], "location": {"block": block_index, "kind": "paragraph"}, "modality": "text"})  # 工单18：写入段落片段。
        if tag == "tbl":  # 工单18：处理表格块。
            row_lines = []  # 工单18：初始化当前表格行列表。
            for row_index, row in enumerate(child.findall(".//w:tr", WORD_NS), start=1):  # 工单18：遍历全部表格行。
                cells = [_text_of(cell) for cell in row.findall(".//w:tc", WORD_NS)]  # 工单18：提取当前行全部单元格文本。
                values = [item for item in cells if item]  # 工单18：过滤空白单元格。
                if not values:  # 工单18：跳过空行。
                    continue  # 工单18：继续处理下一行。
                row_line = " | ".join(values)  # 工单18：拼接当前表格行文本。
                row_lines.append(row_line)  # 工单18：记录当前表格行。
                chunks.append({"content": row_line, "summary": values[0][:60], "location": {"block": block_index + 1, "row": row_index, "kind": "table"}, "modality": "table"})  # 工单18：写入表格行片段。
            if row_lines:  # 工单18：仅保留非空表格。
                block_index += 1  # 工单18：递增块编号。
                lines.append("\n".join(row_lines))  # 工单18：将表格整体写入完整文本。
    return {"content_text": "\n\n".join(lines), "chunks": chunks}  # 工单18：返回 DOCX 解析结果。
