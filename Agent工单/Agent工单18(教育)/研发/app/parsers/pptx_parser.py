# -*- coding: utf-8 -*-  # 工单18：指定源码编码为 UTF-8。
"""pptx_parser.py - 工单18智能助教的 PPTX 结构化解析模块。"""  # 工单18：声明当前文件功能。

from __future__ import annotations  # 工单18：启用延迟类型注解。

import io  # 工单18：导入内存流模块。
import zipfile  # 工单18：导入压缩包处理模块。
from xml.etree import ElementTree as ET  # 工单18：导入 XML 解析模块。

DRAWING_NS = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}  # 工单18：定义 DrawingML 命名空间。


def parse_pptx(file_bytes: bytes) -> dict:  # 工单18：解析 PPTX 幻灯片文本内容。
    archive = zipfile.ZipFile(io.BytesIO(file_bytes))  # 工单18：打开 PPTX 压缩包。
    slide_names = sorted(name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml"))  # 工单18：枚举全部幻灯片 XML 文件。
    slide_texts = []  # 工单18：初始化整份课件文本列表。
    chunks = []  # 工单18：初始化结构化片段列表。
    for slide_index, slide_name in enumerate(slide_names, start=1):  # 工单18：遍历全部幻灯片。
        root = ET.fromstring(archive.read(slide_name))  # 工单18：解析当前幻灯片 XML。
        texts = [(node.text or "").strip() for node in root.findall(".//a:t", DRAWING_NS)]  # 工单18：抽取全部文本节点。
        values = [item for item in texts if item]  # 工单18：过滤空白文本。
        if not values:  # 工单18：为空白页补一条说明。
            values = [f"第{slide_index}页未提取到文本内容。"]  # 工单18：写入空白页提示。
        slide_text = "\n".join(values)  # 工单18：拼接当前幻灯片展示文本。
        slide_texts.append(slide_text)  # 工单18：追加到整份课件文本。
        chunks.append({"content": slide_text, "summary": values[0][:60], "location": {"slide": slide_index}, "modality": "text"})  # 工单18：写入幻灯片级片段。
    return {"content_text": "\n\n".join(slide_texts), "chunks": chunks}  # 工单18：返回 PPTX 解析结果。
