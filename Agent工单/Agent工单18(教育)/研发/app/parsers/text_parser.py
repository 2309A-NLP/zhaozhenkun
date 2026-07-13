# -*- coding: utf-8 -*-  # 工单18：指定源码编码为 UTF-8。
"""text_parser.py - 工单18智能助教的文本与表格轻量解析模块。"""  # 工单18：声明当前文件功能。

from __future__ import annotations  # 工单18：启用延迟类型注解。

import csv  # 工单18：导入 CSV 解析模块。
import io  # 工单18：导入内存流模块。


def parse_plain_text(file_bytes: bytes) -> dict:  # 工单18：解析普通文本内容。
    text = file_bytes.decode("utf-8", errors="ignore")  # 工单18：按 UTF-8 容错解码文本。
    return {"content_text": text, "chunks": []}  # 工单18：返回统一结构结果。


def parse_csv_text(file_bytes: bytes) -> dict:  # 工单18：解析 CSV 文本并保留行号信息。
    text = file_bytes.decode("utf-8", errors="ignore")  # 工单18：按 UTF-8 容错解码 CSV。
    rows = list(csv.reader(io.StringIO(text)))  # 工单18：将 CSV 转换为二维表结构。
    lines = []  # 工单18：初始化文本行列表。
    chunks = []  # 工单18：初始化结构化片段列表。
    for row_index, row in enumerate(rows, start=1):  # 工单18：遍历全部表格行。
        values = [str(cell).strip() for cell in row if str(cell).strip()]  # 工单18：清洗并保留非空单元格。
        if not values:  # 工单18：跳过空白行。
            continue  # 工单18：继续处理下一行。
        line = " | ".join(values)  # 工单18：将一行单元格拼接为展示文本。
        lines.append(line)  # 工单18：追加到完整文本列表。
        chunks.append({"content": line, "summary": values[0][:60], "location": {"row": row_index}, "modality": "table"})  # 工单18：写入结构化表格片段。
    return {"content_text": "\n".join(lines), "chunks": chunks}  # 工单18：返回解析结果。


def unsupported_legacy_office(suffix: str) -> dict:  # 工单18：返回旧版 Office 格式不支持说明。
    mapping = {".doc": "docx", ".ppt": "pptx", ".xls": "xlsx"}  # 工单18：定义旧格式到新格式的映射。
    target = mapping.get(suffix, "新格式")  # 工单18：读取建议转换目标格式。
    message = f"当前版本暂不直接解析 {suffix} 文件，请先转换为 {target} 后再上传。"  # 工单18：构造清晰错误说明。
    return {"content_text": message, "chunks": [{"content": message, "summary": message[:60], "location": {"kind": "unsupported"}, "modality": "text"}], "unsupported": True}  # 工单18：返回降级结果。
