# -*- coding: utf-8 -*-  # 工单18：指定源码编码为 UTF-8。
"""document_parser.py - 工单18智能助教的多格式文档解析与统一切块模块。"""  # 工单18：声明当前文件功能。

from __future__ import annotations  # 工单18：启用延迟类型注解。

from pathlib import Path  # 工单18：导入路径处理类。

from app.parsers.docx_parser import parse_docx  # 工单18：导入 DOCX 解析函数。
from app.parsers.image_parser import parse_image  # 工单18：导入图片解析函数。
from app.parsers.pdf_parser import parse_pdf  # 工单18：导入 PDF 解析函数。
from app.parsers.pptx_parser import parse_pptx  # 工单18：导入 PPTX 解析函数。
from app.parsers.text_parser import parse_csv_text  # 工单18：导入 CSV 解析函数。
from app.parsers.text_parser import parse_plain_text  # 工单18：导入普通文本解析函数。
from app.parsers.text_parser import unsupported_legacy_office  # 工单18：导入旧版 Office 降级函数。
from app.parsers.xlsx_parser import parse_xlsx  # 工单18：导入 XLSX 解析函数。

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}  # 工单18：定义图片扩展名集合。
TEXT_SUFFIXES = {".txt", ".md"}  # 工单18：定义普通文本扩展名集合。


def detect_media_kinds(file_name: str, text: str) -> list[str]:  # 工单18：根据文件名和文本内容推断多模态类型。
    suffix = Path(file_name).suffix.lower()  # 工单18：读取文件后缀名。
    media_kinds = ["text"]  # 工单18：默认至少存在文本内容。
    if suffix in IMAGE_SUFFIXES:  # 工单18：判断是否为图像文件。
        media_kinds.append("image")  # 工单18：补充图像标签。
    if suffix in {".csv", ".xlsx", ".xls"} or "|" in text:  # 工单18：判断是否包含表格信息。
        media_kinds.append("table")  # 工单18：补充表格标签。
    if suffix == ".pptx":  # 工单18：将课件单独归类为幻灯片资源。
        media_kinds.append("slide")  # 工单18：补充幻灯片标签。
    if any(symbol in text for symbol in ["∑", "∫", "θ", "α", "β", "公式", "="]):  # 工单18：检查是否存在公式特征。
        media_kinds.append("formula")  # 工单18：补充公式标签。
    return sorted(set(media_kinds))  # 工单18：返回去重后的多模态标签。


def _finalize(parsed: dict) -> dict:  # 工单18：为解析结果补全缺失字段。
    text = parsed.get("content_text", "")  # 工单18：读取完整文本内容。
    chunks = parsed.get("chunks", []) or chunk_text(text)  # 工单18：优先使用结构化片段否则回退基础切块。
    return {"content_text": text, "chunks": chunks, "unsupported": parsed.get("unsupported", False)}  # 工单18：返回标准化解析结果。


def parse_document(file_name: str, file_bytes: bytes, provider: str = "qwen") -> dict:  # 工单18：解析上传文件并输出统一结构。
    suffix = Path(file_name).suffix.lower()  # 工单18：提取文件扩展名。
    if suffix in TEXT_SUFFIXES:  # 工单18：处理纯文本与 Markdown 文件。
        return _finalize(parse_plain_text(file_bytes))  # 工单18：返回文本解析结果。
    if suffix == ".csv":  # 工单18：处理 CSV 表格。
        return _finalize(parse_csv_text(file_bytes))  # 工单18：返回 CSV 解析结果。
    if suffix == ".pdf":  # 工单18：处理 PDF 文档。
        return _finalize(parse_pdf(file_bytes))  # 工单18：返回 PDF 解析结果。
    if suffix == ".docx":  # 工单18：处理 DOCX 文档。
        return _finalize(parse_docx(file_bytes))  # 工单18：返回 DOCX 解析结果。
    if suffix == ".pptx":  # 工单18：处理 PPTX 课件。
        return _finalize(parse_pptx(file_bytes))  # 工单18：返回 PPTX 解析结果。
    if suffix == ".xlsx":  # 工单18：处理 XLSX 表格。
        return _finalize(parse_xlsx(file_bytes))  # 工单18：返回 XLSX 解析结果。
    if suffix in IMAGE_SUFFIXES:  # 工单18：处理图片文件。
        return _finalize(parse_image(file_name, file_bytes, provider=provider))  # 工单18：返回图片解析结果。
    if suffix in {".doc", ".ppt", ".xls"}:  # 工单18：处理旧版 Office 文件。
        return _finalize(unsupported_legacy_office(suffix))  # 工单18：返回旧格式降级结果。
    return _finalize(parse_plain_text(file_bytes))  # 工单18：对其余文本型内容执行兜底解析。


def parse_text_bytes(file_name: str, file_bytes: bytes) -> str:  # 工单18：兼容旧调用方式，仅返回解析后的纯文本。
    return parse_document(file_name, file_bytes).get("content_text", "")  # 工单18：从统一解析结果中提取正文文本。


def chunk_text(text: str, chunk_size: int = 220) -> list[dict]:  # 工单18：将长文本切分为可检索片段。
    clean_lines = [line.strip() for line in text.replace("\r", "").split("\n") if line.strip()]  # 工单18：清洗换行并移除空白行。
    if not clean_lines:  # 工单18：若无有效文本则返回空列表。
        return []  # 工单18：结束空文本切块。
    chunks = []  # 工单18：初始化切块结果列表。
    buffer = []  # 工单18：初始化当前片段缓冲区。
    current_length = 0  # 工单18：初始化当前片段长度计数器。
    for line in clean_lines:  # 工单18：遍历每一行文本。
        current_length += len(line)  # 工单18：累计当前缓冲区文本长度。
        buffer.append(line)  # 工单18：把当前行追加到缓冲区。
        if current_length >= chunk_size:  # 工单18：达到片段阈值后生成切块。
            content = "\n".join(buffer)  # 工单18：拼接当前片段正文。
            chunks.append({"content": content, "summary": buffer[0][:60], "location": {"chunk": len(chunks) + 1}, "modality": "text"})  # 工单18：写入基础片段内容与定位。
            buffer = []  # 工单18：清空缓冲区准备下一段。
            current_length = 0  # 工单18：重置长度计数器。
    if buffer:  # 工单18：处理剩余未输出的末尾文本。
        content = "\n".join(buffer)  # 工单18：拼接最后一段正文。
        chunks.append({"content": content, "summary": buffer[0][:60], "location": {"chunk": len(chunks) + 1}, "modality": "text"})  # 工单18：将剩余文本写入最后一个片段。
    return chunks  # 工单18：返回全部切块结果。
