"""
text_chunker.py - RAG工单8 文本分块模块
工单编号: 人工智能NLP-RAG-基于Graph RAG 实现金融问答
功能: 将CCF年报PDF文本切分为固定大小的文本块，
      带重叠窗口，供向量化和图谱构建使用
"""

import logging, json
from config import CHUNK_SIZE, CHUNK_OVERLAP, OUTPUT_DIR, LOG_FMT, LOG_DATEFMT

logging.basicConfig(format=LOG_FMT, datefmt=LOG_DATEFMT, level=logging.INFO)
logger = logging.getLogger("text_chunker")


def split_text_into_chunks(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """
    将长文本按指定大小和重叠窗口切分为多个块
    Args:
        text: 输入文本
        chunk_size: 每块的字符数上限
        overlap: 前后块之间的重叠字符数（保持上下文连贯）
    Returns:
        list: 每个元素为{"text": 块文本, "index": 块索引}
    """
    chunks = []
    start = 0
    index = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append({"text": chunk_text, "index": index})
            index += 1
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def build_chunks(pdf_data):
    """
    将PDF解析结果组装为结构化chunks列表，每块包含元信息
    Args:
        pdf_data: pdf_parser.parse_ccf_pdfs()的返回结果
    Returns:
        list: 每个元素含content(文本内容), index(全局索引),
              source_pdf(来源文件名), page_num(页码)
    """
    chunks = []
    chunk_index = 0
    for page in pdf_data.get("pages", []):
        page_chunks = split_text_into_chunks(page["text"])
        for pc in page_chunks:
            chunks.append({
                "content": pc["text"],
                "index": chunk_index,
                "source_pdf": page.get("source_pdf", ""),
                "page_num": page.get("page_num", 0),
            })
            chunk_index += 1
    logger.info(f"分块完成! 共{len(chunks)}个chunk, "
                f"来自{len(pdf_data.get('pages', []))}页PDF")
    return chunks


def save_chunks(chunks, filename="chunks.json"):
    """将chunks列表序列化为JSON保存到output目录"""
    path = OUTPUT_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    logger.info(f"chunks已保存: {path} (共{len(chunks)}块)")
    return path


def load_chunks(filename="chunks.json"):
    """从output目录加载已保存的chunks"""
    path = OUTPUT_DIR / filename
    if not path.exists():
        logger.warning(f"chunks文件不存在: {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    logger.info(f"已加载{len(chunks)}个chunk: {path}")
    return chunks


def get_chunk_stats(chunks):
    """统计chunk信息：总块数、平均长度、来源分布等"""
    total = len(chunks)
    avg_len = sum(len(c.get("content", "")) for c in chunks) / max(total, 1)
    sources = {}
    for c in chunks:
        src = c.get("source_pdf", "unknown")
        sources[src] = sources.get(src, 0) + 1
    return {"total": total, "avg_length": round(avg_len, 1), "sources": sources}


if __name__ == "__main__":
    """单独测试文本分块功能"""
    test_text = "平安银行2019年度报告。" * 50
    result = split_text_into_chunks(test_text)
    print(f"分块结果: {len(result)}块")
    for c in result[:3]:
        print(f"  块{c['index']}: {c['text'][:50]}...")
