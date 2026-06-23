"""
text_chunker.py - RAG工单7 文本分块模块
工单编号: 人工智能NLP-RAG-功能测试及评估
功能: 将CCF年报PDF文本切分为固定大小的文本块，
      带重叠窗口，供向量化检索使用
"""

import logging, json, os, re

# 导入配置
from config import CHUNK_SIZE, CHUNK_OVERLAP, OUTPUT_DIR, LOG_FMT, LOG_DATEFMT

# 设置日志
logging.basicConfig(format=LOG_FMT, datefmt=LOG_DATEFMT, level=logging.INFO)
logger = logging.getLogger("text_chunker")


def split_text(text, chunk_size=None, overlap=None):
    """
    将长文本按指定大小切块（带重叠窗口）
    参数:
        text: 输入文本
        chunk_size: 每块最大字符数
        overlap: 块间重叠字符数
    返回:
        list: [{"content": str, "index": int}, ...]
    """
    chunk_size = chunk_size or CHUNK_SIZE
    overlap = overlap or CHUNK_OVERLAP

    # 按换行分割成段落列表
    paragraphs = re.split(r'\n+', text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks = []
    current_chunk = ""

    # 逐段合并到块中
    for para in paragraphs:
        if len(current_chunk) + len(para) < chunk_size:
            current_chunk += para + "\n"
        else:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            # 新块带上重叠内容
            if overlap > 0 and chunks:
                last = chunks[-1]
                overlap_text = last[-overlap:] if len(last) > overlap else last
                current_chunk = overlap_text + "\n" + para + "\n"
            else:
                current_chunk = para + "\n"

    # 保存最后一块
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return [{"content": c, "index": i} for i, c in enumerate(chunks)]


def build_chunks(pdf_result):
    """
    将CCF年报的PDF解析结果切块
    参数:
        pdf_result: pdf_parser返回的解析结果
    返回:
        list: 带元数据的文本块列表
    """
    logger.info("构建文档块...")
    all_chunks = []

    for page in pdf_result["pages"]:
        page_text = page["text"]
        source = page.get("source_pdf", "unknown.pdf")
        pnum = page["page_num"]

        # 切分当前页
        page_chunks = split_text(page_text)
        for c in page_chunks:
            all_chunks.append({
                "content": c["content"],
                "index": len(all_chunks),
                "source_pdf": source,
                "page_num": pnum,
            })

    logger.info(f"文档块构建完成: {len(all_chunks)} 块")
    return all_chunks


def save_chunks(chunks):
    """保存分块结果到文件"""
    path = os.path.join(OUTPUT_DIR, "chunks.json")
    data = [{
        "index": c["index"],
        "preview": c["content"][:80] + "..." if len(c["content"]) > 80 else c["content"],
        "source": c["source_pdf"],
        "page": c["page_num"],
    } for c in chunks]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"分块结果已保存: {path}")


if __name__ == "__main__":
    """单独测试分块"""
    test = "第一段。第二段。第三段。\n新段落。"
    chunks = split_text(test, chunk_size=20, overlap=5)
    for c in chunks:
        print(f"块{c['index']}: {c['content'][:40]}")
