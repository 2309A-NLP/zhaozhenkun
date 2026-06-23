"""
pdf_parser.py - RAG工单6 PDF解析模块
需求: 向量检索基础 — 解析招股说明书PDF，提取文本用于后续分块和向量化
功能: 使用PyMuPDF逐页提取文本和图片，过滤小尺寸图片，支持多PDF批量解析
"""
import io
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass, field

import fitz
from config import PROJECT_DIR, PDF_PATHS


@dataclass
class PageData:
    """单页解析结果：页码、文本、图片列表"""
    page_num: int
    text: str
    images: List[Dict] = field(default_factory=list)


@dataclass
class PdfParseResult:
    """完整PDF解析结果：文件名、路径、逐页数据、总页数、合并文本、图片总数"""
    file_name: str
    file_path: str
    pages: List[PageData]
    total_pages: int
    total_text: str
    total_images: int


def extract_images_from_page(page: fitz.Page, min_w: int = 100, min_h: int = 100, min_bytes: int = 10240) -> List[Dict]:
    """从单页提取图片，过滤小尺寸"""
    valid = []
    for img_index, img_info in enumerate(page.get_images(full=True)):
        base = page.parent.extract_image(img_info[0])
        w, h, b = base["width"], base["height"], len(base["image"])
        if w >= min_w and h >= min_h and b >= min_bytes:
            valid.append({
                "index": img_index, "width": w, "height": h,
                "size_bytes": b, "format": base["ext"],
                "bytes": base["image"],
                "filename": f"page{page.number + 1}_img{img_index}.{base['ext']}",
            })
    return valid


def parse_single_pdf(pdf_path: Path, min_w: int = 100, min_h: int = 100, min_bytes: int = 10240) -> PdfParseResult:
    """解析单个PDF，返回结构化结果"""
    doc = fitz.open(str(pdf_path))
    all_pages, text_parts, img_count = [], [], 0
    total_pages = len(doc)
    for pn in range(total_pages):
        page = doc.load_page(pn)
        text = page.get_text()
        text_parts.append(text)
        imgs = extract_images_from_page(page, min_w, min_h, min_bytes)
        img_count += len(imgs)
        all_pages.append(PageData(page_num=pn + 1, text=text, images=imgs))
    doc.close()
    return PdfParseResult(
        file_name=pdf_path.name, file_path=str(pdf_path.resolve()),
        pages=all_pages, total_pages=total_pages,
        total_text="\n".join(text_parts), total_images=img_count,
    )


def parse_all_pdfs(min_w: int = 100, min_h: int = 100, min_bytes: int = 10240) -> Dict[str, PdfParseResult]:
    """解析配置中所有PDF"""
    results = {}
    for pdf_path in PDF_PATHS:
        if not pdf_path.exists():
            print(f"[警告] PDF不存在: {pdf_path}")
            continue
        r = parse_single_pdf(pdf_path, min_w, min_h, min_bytes)
        results[r.file_name] = r
        print(f"[完成] {r.file_name} (共{r.total_pages}页, {r.total_images}张图片)")
    return results


def print_parse_summary(results: Dict[str, PdfParseResult]):
    """打印解析摘要"""
    print("=" * 60 + "\nPDF解析摘要\n" + "=" * 60)
    for name, r in results.items():
        print(f"  文件: {name}\n  页数: {r.total_pages}\n  图片: {r.total_images}\n  文本: {len(r.total_text)}字符\n" + "-" * 60)
    total_p = sum(r.total_pages for r in results.values())
    total_i = sum(r.total_images for r in results.values())
    print(f"  总计: {len(results)}个文件, {total_p}页, {total_i}张图片\n" + "=" * 60)


if __name__ == "__main__":
    print("开始解析PDF文件...")
    print_parse_summary(parse_all_pdfs())
    print("PDF解析全部完成。")
