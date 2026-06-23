"""
PDF 解析模块
功能：使用 PyMuPDF 解析招股说明书 PDF，提取每页文本并追踪来源文件名
完成：支持批量解析多份 PDF，输出带 source_pdf 标记的结构化数据
"""
import logging
import sys, os
# 将项目根目录加入路径，支持从任意子目录导入其他模块
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _sub in ["设计", "研发", "测试", "部署"]:
    _p = os.path.join(_root, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import os       # 文件路径操作
import json     # 保存解析结果到 JSON
import fitz     # PyMuPDF，高性能 PDF 解析库

import config   # 读取 PDF 路径

logger = logging.getLogger(__name__)
logger.info("PDF解析模块加载")

logger = logging.getLogger(__name__)


def parse_pdf(filepath: str) -> list[dict]:
    """
    解析单个 PDF 文件，返回每页的文本内容
    参数：
        filepath: PDF 文件的完整路径
    返回：
        列表，每页 {"page_num": int, "text": str}
    """
    # 检查文件是否存在
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"PDF 文件不存在: {filepath}")

    # 打开 PDF 文档
    doc = fitz.open(filepath)
    pages = []  # 存储所有有内容的页

    # 遍历每一页
    for page_num in range(len(doc)):
        page = doc[page_num]             # 获取当前页对象
        text = page.get_text().strip()   # 提取文本并去首尾空格
        if text:                         # 跳过空白页
            pages.append({
                "page_num": page_num + 1,  # 页码从 1 开始
                "text": text               # 该页完整文本
            })

    doc.close()  # 关闭文档释放资源
    print(f"  ✅ {os.path.basename(filepath)}: 共 {len(pages)} 页有内容")
    return pages


def parse_all_pdfs() -> dict:
    """
    解析配置文件中定义的所有 PDF
    返回：
        dict，key=文件名，value=页面列表
    """
    result = {}
    for filename, filepath in config.PDF_PATHS.items():
        print(f"📄 正在解析: {filename}")
        result[filename] = parse_pdf(filepath)
    return result


def save_parsed_results(pdf_data: dict, output_path: str) -> None:
    """
    将解析结果保存为 JSON 文件（每页带 source_pdf 标记）
    参数：
        pdf_data: parse_all_pdfs 的返回结果
        output_path: 输出文件路径
    """
    serializable = {}
    for filename, pages in pdf_data.items():
        serializable[filename] = [
            {
                "source_pdf": filename,
                "page_num": p["page_num"],
                "text": p["text"]
            }
            for p in pages
        ]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)

    # 统计总页数和总字符数
    total_pages = sum(len(pages) for pages in pdf_data.values())
    total_chars = sum(
        len(p["text"]) for pages in pdf_data.values() for p in pages
    )
    print(f"📊 统计: {total_pages} 页, {total_chars} 字符")


def get_pdf_summary(pdf_data: dict) -> dict:
    """
    获取 PDF 解析结果的摘要统计
    参数：
        pdf_data: parse_all_pdfs 的返回结果
    返回：
        {"total_pages": int, "total_chars": int, "per_pdf": {filename: {"pages": int, "chars": int}}}
    """
    summary = {"total_pages": 0, "total_chars": 0, "per_pdf": {}}
    for fn, pages in pdf_data.items():
        chars = sum(len(p["text"]) for p in pages)
        summary["per_pdf"][fn] = {"pages": len(pages), "chars": chars}
        summary["total_pages"] += len(pages)
        summary["total_chars"] += chars
    return summary


if __name__ == "__main__":
    """命令行测试：解析 PDF 并打印统计"""
    print("🚀 开始解析 PDF...")
    data = parse_all_pdfs()
    summary = get_pdf_summary(data)
    for fn, info in summary["per_pdf"].items():
        print(f"  {fn}: {info['pages']} 页, {info['chars']} 字符")
    print(f"📊 合计: {summary['total_pages']} 页, {summary['total_chars']} 字符")
