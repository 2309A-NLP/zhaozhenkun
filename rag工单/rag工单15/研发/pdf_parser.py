# -*- coding: utf-8 -*-
"""
PDF解析模块 — OCR提取文本 + 补充知识库。

数据来源：
1. OCR 提取：对 PDF 每页运行 RapidOCR，提取可识别的文字
2. 补充知识库：对纯图纸页（OCR无法提取的图表信息），从专利公开文献补充
3. 两者合并构建知识库

与 v1 的区别：
- v1 (_get_page_desc): 所有页面描述硬编码在代码中
- v2 (本版本): OCR真实提取 + JSON补充文件，数据和代码分离
"""
import logging
import json
import os
from pathlib import Path

logger = logging.getLogger(__name__)
logger.info("pdf_parser 模块加载 (v2: OCR + supplement)")


def _run_ocr(pdf_path):
    """
    对 PDF 每页运行 OCR，提取真实文字。

    返回: pages_data 列表，每个元素包含 page_num, text
    """
    try:
        import fitz
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as e:
        print(f"  ⚠️ OCR 依赖未安装 ({e})，回退到空文本")
        return []

    doc = fitz.open(pdf_path)
    ocr = RapidOCR()
    pages_data = []

    for i in range(len(doc)):
        page = doc[i]
        pix = page.get_pixmap(dpi=200)
        img_path = f"/tmp/ocr_page_{i+1}.png"
        pix.save(img_path)

        result, _ = ocr(img_path)
        text = " ".join([r[1] for r in result]) if result else ""
        pages_data.append({"page_num": i + 1, "text": text})

    doc.close()

    # 清理临时文件
    for i in range(len(pages_data)):
        tmp = f"/tmp/ocr_page_{i+1}.png"
        if os.path.exists(tmp):
            os.remove(tmp)

    return pages_data


def _load_supplement(project_root):
    """
    加载补充知识库 JSON（图纸页面的文字描述）。

    补充知识库用于弥补纯图片页 OCR 无法提取的信息。
    数据来源于专利公开文献，存储在独立的 JSON 文件中。
    """
    supp_path = Path(project_root) / "测试" / "supplement_knowledge.json"
    if not supp_path.exists():
        print(f"  ⚠️ 补充知识库未找到: {supp_path}")
        return {}

    with open(supp_path, encoding="utf-8") as f:
        supplement = json.load(f)

    # 转为按页码索引的字典
    supp_map = {}
    for p in supplement.get("pages", []):
        supp_map[p["page_num"]] = {
            "figure_ref": p.get("figure_ref", ""),
            "description": p.get("description", ""),
            "has_figure": True,
        }

    print(f"  📄 加载补充知识库: {len(supp_map)} 页 (来源: {supplement.get('_source', 'N/A')})")
    return supp_map


def parse_pdf(pdf_path, project_root=None):
    """
    解析 PDF：OCR 提取真实文字 + 补充知识库。

    返回: pages 列表
    """
    print(f"📄 正在解析 PDF (OCR模式): {pdf_path}")

    # Step 1: OCR 提取
    ocr_data = _run_ocr(pdf_path)
    total_chars = sum(p["text"] and len(p["text"]) or 0 for p in ocr_data)
    text_pages = sum(1 for p in ocr_data if p["text"] and len(p["text"]) > 50)
    print(f"  OCR 结果: {len(ocr_data)} 页, {total_chars} 字符, {text_pages} 页有文本")

    # Step 2: 加载补充知识库
    if project_root is None:
        project_root = str(Path(__file__).resolve().parent.parent)
    supplement = _load_supplement(project_root)

    # Step 3: 合并构建页面列表
    pages = []
    for p in ocr_data:
        pn = p["page_num"]
        supp = supplement.get(pn, {})

        page_info = {
            "page_num": pn,
            "ocr_text": p["text"],                       # OCR真实提取的文字
            "has_figure": supp.get("has_figure", False), # 是否含图纸
            "figure_ref": supp.get("figure_ref", ""),    # 图纸编号
            "description": supp.get("description", p["text"][:200] if p["text"] else ""),
            "source": "ocr" if not supp else "ocr+supplement",  # 数据来源标注
        }
        pages.append(page_info)

    # 统计
    ocr_only = sum(1 for p in pages if p["source"] == "ocr")
    combined = sum(1 for p in pages if p["source"] == "ocr+supplement")
    print(f"  ✅ 解析完成: {ocr_only} 页纯OCR, {combined} 页OCR+补充")
    return pages


def build_knowledge_base(pages, output_dir):
    """
    构建知识库：将页面信息转为结构化文本块，保存为 JSON。
    """
    output_path = Path(output_dir) / "knowledge_base.json"
    kb = []

    for p in pages:
        # 构建知识库条目
        # OCR文本为主，补充描述为辅
        if p["source"] == "ocr+supplement":
            # 图纸页：OCR文本(图号) + 补充描述
            content = f"[{p['figure_ref']}] {p['description']}"
        elif p["ocr_text"]:
            content = p["ocr_text"]
        else:
            content = f"第{p['page_num']}页（图片页，文字内容见补充知识库）"

        chunk = {
            "id": f"page_{p['page_num']}",
            "page_num": p["page_num"],
            "content": content,
            "has_figure": p["has_figure"],
            "figure_ref": p["figure_ref"],
            "source": p["source"],  # 数据来源可追溯
        }
        kb.append(chunk)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(kb, f, ensure_ascii=False, indent=2)

    print(f"  ✅ 知识库已保存: {output_path} ({len(kb)} 条)")
    return kb
