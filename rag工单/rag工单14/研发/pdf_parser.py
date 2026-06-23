"""
PDF解析与文本分块模块
功能：读取PDF文件内容，提取每页文本，按配置参数进行智能分块
说明：先尝试直接提取文本，如果为空（扫描件PDF）则自动调用RapidOCR识别
       RapidOCR对中文识别效果远优于Tesseract，适合工业PDF扫描件
"""
import logging
import os                           # 文件路径操作
import fitz                         # PyMuPDF，解析 PDF 的核心库
import re                           # 正则表达式，用于文本清洗和分块
import io                           # 字节流，用于图片转 PIL
import tempfile                      # 跨平台临时文件（Windows兼容）
from PIL import Image               # 图片处理
from rapidocr_onnxruntime import RapidOCR  # 轻量级中文OCR引擎
from config import CHUNK_SIZE, CHUNK_OVERLAP  # 分块参数

logger = logging.getLogger(__name__)
logger.info("pdf_parser 模块加载")

# ======================== 全局OCR引擎单例 ========================
_ocr_engine = None  # 避免每次调用都重新加载模型

def get_ocr_engine() -> RapidOCR:
    """获取OCR引擎（单例模式，只加载一次）"""
    global _ocr_engine
    if _ocr_engine is None:
        print("    ⏳ 加载RapidOCR引擎...")
        _ocr_engine = RapidOCR()
        print("    ✓ OCR引擎就绪")
    return _ocr_engine

def parse_pdf(pdf_path: str) -> list[dict]:
    """
    解析 PDF 文件，提取每页的文本内容
    参数：pdf_path — PDF 文件的路径
    返回：列表，每个元素 {"page": 页码(int), "text": 该页文本(str)}
    """
    # 检查 PDF 文件是否存在
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF文件不存在: {pdf_path}")

    # 用 PyMuPDF 打开 PDF
    doc = fitz.open(pdf_path)
    pages = []  # 存每页的结果

    # 逐页解析
    for page_num in range(doc.page_count):
        page = doc[page_num]               # 获取第 page_num 页
        text = page.get_text()             # 提取页面的全部文本
        text = text.strip()                # 去掉首尾空白

        # 如果 get_text() 返回空，说明是扫描件/图片型PDF，走OCR
        if not text:
            print(f"    ⏳ 第{page_num+1}页为图片型，启动RapidOCR识别...")
            # 获取该页的图片列表
            images = page.get_images(full=True)
            if images:
                # 取第一张图片（通常扫描件每页只有一张图）
                xref = images[0][0]
                base = doc.extract_image(xref)
                img_bytes = base["image"]
                # 保存图片到临时文件（RapidOCR需要文件路径或numpy数组）
                img_path = os.path.join(tempfile.gettempdir(), f"ocr_page_{page_num}.png")
                with open(img_path, "wb") as f:
                    f.write(img_bytes)

                # 调用 RapidOCR 引擎识别
                engine = get_ocr_engine()
                ocr_result, elapse = engine(img_path)

                # 清理临时图片文件
                try:
                    os.remove(img_path)
                except OSError:
                    pass

                # 解析OCR结果：每行是 [bbox, text, confidence]
                if ocr_result:
                    text_lines = [line[1] for line in ocr_result]
                    text = "\n".join(text_lines)
                else:
                    text = ""
                text = text.strip()
                print(f"    ✓ RapidOCR识别完成：{len(text)}字符")
            else:
                print(f"    ⚠ 第{page_num+1}页无图片，跳过")

        # 跳过完全空白的页
        if text:
            # 清洗文本：合并多余换行、去除多余空格
            text = re.sub(r"\n{3,}", "\n\n", text)   # 3个以上换行变2个
            text = re.sub(r" +\n", "\n", text)        # 行尾空格去掉
            pages.append({"page": page_num + 1, "text": text})

    doc.close()  # 关闭 PDF
    return pages

def chunk_text(pages: list[dict]) -> list[dict]:
    """
    将每页文本切分成固定大小的块，块之间带重叠
    参数：pages — parse_pdf 返回的页列表
    返回：列表，每个元素 {"page": 页码, "text": 块文本, "chunk_id": 块编号}
    """
    chunks = []       # 存放所有块
    chunk_id = 0      # 全局块编号

    for page in pages:
        page_num = page["page"]   # 当前页码
        text = page["text"]       # 当前页文本

        # 如果文本长度 <= CHUNK_SIZE，整页作为一个块
        if len(text) <= CHUNK_SIZE:
            chunks.append({
                "page": page_num,
                "text": text,
                "chunk_id": chunk_id,
            })
            chunk_id += 1
            continue

        # 长文本按滑动窗口切分
        start = 0
        while start < len(text):
            # 取 [start, start + CHUNK_SIZE) 区间
            end = start + CHUNK_SIZE

            # 尽量在句子结束处切分（找最近的句号/换行）
            if end < len(text):
                # 在当前块末尾附近找合适的断点
                cut = max(
                    text.rfind("。", start, end),    # 中文句号
                    text.rfind("\n", start, end),    # 换行符
                    text.rfind(". ", start, end),    # 英文句号+空格
                )
                if cut > start:
                    end = cut + 1  # 包含句号本身

            # 取出当前块文本
            chunk_text = text[start:end].strip()
            if chunk_text:  # 只添加非空块
                chunks.append({
                    "page": page_num,
                    "text": chunk_text,
                    "chunk_id": chunk_id,
                })
                chunk_id += 1

            # 窗口滑动，减去重叠部分
            start = end - CHUNK_OVERLAP if end < len(text) else len(text)

    return chunks

def parse_and_chunk(pdf_path: str) -> list[dict]:
    """
    一键完成"解析PDF → 分块"的完整流程
    参数：pdf_path — PDF 文件路径
    返回：分块结果列表（同 chunk_text 返回格式）
    """
    # 第一步：解析 PDF，得到每页文本
    pages = parse_pdf(pdf_path)
    print(f"  ✓ PDF解析完成：共{len(pages)}页")

    # 第二步：对文本进行分块
    chunks = chunk_text(pages)
    print(f"  ✓ 文本分块完成：共{len(chunks)}个块")

    return chunks

# ======================== 独立测试入口 ========================
if __name__ == "__main__":
    # 测试本模块功能
    from config import TEST_PDF_PATH
    chunks = parse_and_chunk(TEST_PDF_PATH)
    # 打印前5个块预览
    for c in chunks[:5]:
        print(f"  块#{c['chunk_id']} | 第{c['page']}页 | {c['text'][:60]}...")
