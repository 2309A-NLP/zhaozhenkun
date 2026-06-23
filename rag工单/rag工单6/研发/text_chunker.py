"""
text_chunker.py - RAG工单6 文本分块模块
需求: 全文检索基础 — 将PDF文本切块，构建倒排索引
功能: 固定大小分块(带重叠窗口) + 构建倒排索引(中文2字+/英文2字+)
"""

import logging, json, os, re
from collections import defaultdict

# 导入配置
from config import CHUNK_SIZE, CHUNK_OVERLAP, OUTPUT_DIR, PDF_NAMES, LOG_FMT, LOG_DATEFMT

# 设置日志格式
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
    # 使用配置参数
    chunk_size = chunk_size or CHUNK_SIZE
    overlap = overlap or CHUNK_OVERLAP

    # 按换行分割成段落列表
    paragraphs = re.split(r'\n+', text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks = []         # 存储所有块
    current_chunk = ""  # 当前正在构建的块

    # 逐段合并到块中
    for para in paragraphs:
        if len(current_chunk) + len(para) < chunk_size:
            # 当前块还能容纳这段文本
            current_chunk += para + "\n"
        else:
            # 当前块已满，保存到列表
            if current_chunk.strip():
                chunks.append(current_chunk.strip())

            # 新块从上一个块的末尾重叠部分开始
            if overlap > 0 and chunks:
                last = chunks[-1]
                overlap_text = last[-overlap:] if len(last) > overlap else last
                current_chunk = overlap_text + "\n" + para + "\n"
            else:
                current_chunk = para + "\n"

    # 保存最后一块
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    logger.info(f"分块完成: {len(chunks)} 块")
    return [{"content": c, "index": i} for i, c in enumerate(chunks)]


def build_chunks(pdf_result):
    """
    将PDF解析结果中的所有文本切块
    参数:
        pdf_result: pdf_parser的合并结果（包含pages列表）
    返回:
        list: 每个元素包含content, index, source_pdf, page_num
    """
    logger.info("构建文档块...")
    all_chunks = []

    # 逐页处理
    for page in pdf_result["pages"]:
        text = page["text"]
        source = page.get("source_pdf", PDF_NAMES[0])
        pnum = page["page_num"]

        # 切分当前页
        page_chunks = split_text(text)

        # 为每个块添加元数据
        for c in page_chunks:
            all_chunks.append({
                "content": c["content"],
                "index": len(all_chunks),
                "source_pdf": source,
                "page_num": pnum,
            })

    logger.info(f"文档块构建完成: {len(all_chunks)} 块")
    return all_chunks


def build_inverted_index(chunks):
    """
    构建倒排索引（用于全文检索）
    对每个块中的每个词，记录它出现的块索引列表
    参数:
        chunks: 文本块列表
    返回:
        dict: {词: [块索引1, 块索引2, ...], ...}
    """
    logger.info("构建倒排索引...")
    index = defaultdict(list)  # 默认值为空列表

    # 遍历每个块，提取关键词
    for chunk in chunks:
        text = chunk["content"]
        idx = chunk["index"]

        # 用正则提取中文词和英文词
        # 中文：连续2个以上中文字符
        # 英文：连续2个以上字母
        words = set()
        for match in re.finditer(r'[\u4e00-\u9fff]{2,}|[a-zA-Z]{2,}', text):
            word = match.group().lower()
            words.add(word)

        # 记录每个词出现在哪些块中
        for word in words:
            index[word].append(idx)

    logger.info(f"倒排索引构建完成: {len(index)} 个词")
    return dict(index)


def save_chunks(chunks):
    """将分块结果保存到output目录"""
    path = os.path.join(OUTPUT_DIR, "chunks.json")
    data = [{
        "index": c["index"],
        "preview": c["content"][:80] + "...",
        "source_pdf": c["source_pdf"],
        "page_num": c["page_num"],
    } for c in chunks]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"分块结果已保存: {path}")


def save_inverted_index(index):
    """将倒排索引保存到output目录"""
    path = os.path.join(OUTPUT_DIR, "inverted_index.json")
    # 只保存每个词的前100个块索引（避免文件过大）
    trimmed = {k: v[:100] for k, v in index.items()}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(trimmed, f, ensure_ascii=False, indent=2)
    logger.info(f"倒排索引已保存: {path}, 共{len(index)}个词")


if __name__ == "__main__":
    """单独测试分块功能"""
    test = "第一段。第二段。第三段。\n新段落。"
    chunks = split_text(test, chunk_size=20, overlap=5)
    for c in chunks:
        print(f"块 {c['index']}: {c['content'][:40]}")
