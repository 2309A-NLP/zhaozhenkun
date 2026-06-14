"""
数据准备模块 - PDF解析、文本切分、三元组构造
将PDF文档解析为文本块，构造(anchor, positive, negative)三元组，
用于Embedding模型的对比学习微调。支持块内正例采样和跨块难负例采样。
工单编号：人工智能NLP-RAG项目-11-Embeddings模型微调任务V1.0
"""

import logging
import json
import random
from typing import List, Tuple, Dict

import fitz  # PyMuPDF

from config import PDF_PATHS, CHUNK_SIZE, CHUNK_OVERLAP, TRAIN_RATIO, MAX_TRIPLETS
from config import DATA_DIR, ensure_dirs, normalize_path

logger = logging.getLogger(__name__)
logger.info("数据准备模块加载")


def parse_pdf(file_path: str) -> str:
    """使用PyMuPDF解析PDF，提取所有文本内容"""
    doc = fitz.open(file_path)
    num_pages = len(doc)
    texts = []
    for page_num, page in enumerate(doc):
        t = page.get_text()
        if t.strip():
            texts.append(f"[第{page_num+1}页]\n{t}")
    doc.close()
    full = "\n".join(texts)
    print(f"  [解析] {file_path} → {len(full)}字符, {num_pages}页")
    return full


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> List[str]:
    """将长文本按段落切分为重叠块"""
    paragraphs = text.split("\n")
    chunks = []
    cur = ""
    for para in paragraphs:
        if len(cur) + len(para) + 1 <= chunk_size:
            cur = (cur + "\n" + para).strip() if cur else para
        else:
            if cur.strip():
                chunks.append(cur.strip())
            if overlap > 0 and chunks:
                prev = chunks[-1]
                cur = (prev[-overlap:] if len(prev) > overlap else prev) + "\n" + para
            else:
                cur = para
    if cur.strip():
        chunks.append(cur.strip())
    print(f"  [切分] {len(text)}字符 → {len(chunks)}块 (每块≤{chunk_size}字符)")
    return chunks


def build_triplets(chunks: List[str],
                   max_triplets: int = MAX_TRIPLETS) -> List[Dict]:
    """从文本块构造(anchor, positive, negative)三元组"""
    triplets = []
    n = len(chunks)
    if n < 3:
        print("  [警告] 文本块太少，无法构造三元组")
        return triplets

    for i in range(1, n - 1):
        anchor = chunks[i]
        positive = chunks[i - 1]  # 相邻块作为正例
        exclude = set(range(max(0, i - 2), min(n, i + 3)))
        candidates = [j for j in range(n) if j not in exclude]
        if not candidates:
            continue
        far = [j for j in candidates if abs(j - i) > 10]
        neg_idx = random.choice(far) if far else random.choice(candidates)
        triplets.append({"anchor": anchor, "positive": positive,
                         "negative": chunks[neg_idx]})
        if len(triplets) >= max_triplets:
            break
    print(f"  [三元组] 共生成 {len(triplets)} 个")
    return triplets


def split_train_eval(data: List, ratio: float = TRAIN_RATIO) -> Tuple[List, List]:
    """将数据按比例划分为训练集和评估集"""
    shuffled = data[:]
    random.shuffle(shuffled)
    split = int(len(shuffled) * ratio)
    print(f"  [划分] 训练={split} 评估={len(shuffled)-split}")
    return shuffled[:split], shuffled[split:]


def save_dataset(train: List, eval_: List) -> Tuple:
    """保存三元组到JSON文件"""
    ensure_dirs()
    tp = DATA_DIR / "train_triplets.json"
    ep = DATA_DIR / "eval_triplets.json"
    with open(tp, "w", encoding="utf-8") as f:
        json.dump(train, f, ensure_ascii=False, indent=2)
    with open(ep, "w", encoding="utf-8") as f:
        json.dump(eval_, f, ensure_ascii=False, indent=2)
    print(f"  [保存] 训练→{tp} 评估→{ep}")
    return tp, ep


def load_dataset() -> Tuple[List, List]:
    """从已保存JSON加载数据集"""
    tp = DATA_DIR / "train_triplets.json"
    ep = DATA_DIR / "eval_triplets.json"
    train = json.load(open(tp, "r", encoding="utf-8")) if tp.exists() else []
    eval_ = json.load(open(ep, "r", encoding="utf-8")) if ep.exists() else []
    print(f"  [加载] 训练={len(train)} 评估={len(eval_)}")
    return train, eval_


def prepare_training_data() -> Tuple[List, List]:
    """一站式数据准备：PDF解析→切分→三元组→训练/评估划分"""
    train_path, eval_path = DATA_DIR / "train_triplets.json", DATA_DIR / "eval_triplets.json"
    if train_path.exists() and eval_path.exists():
        print("[数据] 已存在，直接加载")
        return load_dataset()

    print("[数据] 开始从PDF生成...")
    all_text = ""
    for pdf in PDF_PATHS:
        all_text += parse_pdf(normalize_path(pdf)) + "\n\n===文档分隔===\n\n"

    chunks = chunk_text(all_text)
    triplets = build_triplets(chunks)
    train, eval_ = split_train_eval(triplets)
    save_dataset(train, eval_)
    return train, eval_


if __name__ == "__main__":
    prepare_training_data()
