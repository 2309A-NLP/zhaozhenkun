"""
文本分块模块
功能：将 PDF 页面文本切分成固定大小的文本块，带来源追踪和重叠策略
完成：支持重叠分块，每个 chunk 记录 chunk_id / source_pdf / page_num / text
"""
import logging

logger = logging.getLogger(__name__)
import sys, os
# 将项目根目录加入路径，支持从任意子目录导入其他模块
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _sub in ["设计", "研发", "测试", "部署"]:
    _p = os.path.join(_root, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import json  # 读写 JSON 缓存

import config  # 分块参数


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    """
    将一段文本切分成多个带重叠的块
    参数：
        text: 原始文本
        chunk_size: 每块最大字符数
        overlap: 块间重叠字符数
    返回：
        字符串列表
    """
    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap  # 减去重叠部分

    return chunks


def chunk_all_pages(pdf_data: dict) -> list[dict]:
    """
    将所有 PDF 的所有页面切分成文本块
    参数：
        pdf_data: parse_all_pdfs 返回的 dict
    返回：
        列表，每项 {"chunk_id", "source_pdf", "page_num", "text"}
    """
    all_chunks = []
    chunk_idx = 0

    for filename, pages in pdf_data.items():
        for page in pages:
            text_chunks = chunk_text(
                page["text"], config.CHUNK_SIZE, config.CHUNK_OVERLAP
            )
            for tc in text_chunks:
                all_chunks.append({
                    "chunk_id": chunk_idx,
                    "source_pdf": filename,
                    "page_num": page["page_num"],
                    "text": tc
                })
                chunk_idx += 1

    return all_chunks


def save_chunks(chunks: list[dict], output_path: str) -> None:
    """将分块结果保存到 JSON"""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)


def load_chunks(cache_path: str) -> list[dict] | None:
    """从缓存加载分块数据（不存在返回 None）"""
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


if __name__ == "__main__":
    """命令行测试：从缓存加载解析结果并切分，打印统计和预览"""
    import os
    cache = os.path.join(config.CACHE_DIR, "parsed_pages.json")
    if not os.path.exists(cache):
        print("❌ 请先运行 pdf_parser.py")
        exit(1)
    with open(cache, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("🚀 开始切分...")
    chunks = chunk_all_pages(data)
    print(f"📊 共 {len(chunks)} 个文本块")

    # 按来源 PDF 统计
    from collections import Counter


    pdf_counts = Counter(c["source_pdf"] for c in chunks)
    for pdf, cnt in pdf_counts.items():
        print(f"   {pdf}: {cnt} 块")

    save_chunks(chunks, config.CHUNKS_CACHE)
    print(f"💾 已保存到: {config.CHUNKS_CACHE}")
    print(f"📋 首个块预览: {chunks[0]['text'][:80]}...")
