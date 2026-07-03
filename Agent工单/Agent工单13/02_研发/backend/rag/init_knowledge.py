"""
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0
初始化 RAG 知识库 —— 将生成的医学数据集导入向量数据库
"""

import json
import os
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.vector_store import get_vector_store
from config import KNOWLEDGE_DIR

_log = logging.getLogger("medical_agent.rag.init_knowledge")


def load_json_dataset(filepath: str) -> list:
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def init_from_vqa_dataset(data: list):
    vs = get_vector_store()
    docs, metadatas = [], []
    for item in data:
        content = f"问题：{item.get('question', '')}\n回答：{item.get('answer', '')}"
        docs.append(content)
        metadatas.append({
            "source": "VQA数据集", "data_type": "vqa",
            "image_type": item.get("image_type", ""),
            "body_part": item.get("body_part", ""),
            "difficulty": item.get("difficulty", ""),
        })
    if docs:
        count = vs.add_documents(docs, metadatas)
        _log.info("VQA 数据集入库: %d 条", count)
    return len(docs)


def init_from_mrg_dataset(data: list):
    vs = get_vector_store()
    docs, metadatas = [], []
    for item in data:
        content = (
            f"检查项目：{item.get('examination', '')}\n"
            f"临床指征：{item.get('clinical_indication', '')}\n"
            f"检查技术：{item.get('technique', '')}\n"
            f"影像所见：{item.get('findings', '')}\n"
            f"诊断印象：{item.get('impression', '')}\n"
            f"建议：{item.get('recommendations', '')}"
        )
        docs.append(content)
        metadatas.append({
            "source": "MRG数据集", "data_type": "mrg",
            "report_type": item.get("report_type", ""),
            "urgency": item.get("urgency", ""),
        })
    if docs:
        count = vs.add_documents(docs, metadatas)
        _log.info("MRG 数据集入库: %d 条", count)
    return len(docs)


def init_from_rag_dataset(data: list):
    vs = get_vector_store()
    docs, metadatas = [], []
    for item in data:
        docs.append(item.get("content", ""))
        metadatas.append({
            "source": "RAG知识库", "data_type": "rag",
            "category": item.get("category", ""),
            "title": item.get("title", ""),
            "keywords": ",".join(item.get("keywords", [])),
            "source_type": item.get("source_type", ""),
        })
    if docs:
        count = vs.add_documents(docs, metadatas)
        _log.info("RAG 知识库入库: %d 条", count)
    return len(docs)


def init_from_slake(data: list):
    vs = get_vector_store()
    docs, metadatas = [], []
    for item in data:
        question = item.get("question", "")
        answer = item.get("answer", "")
        if question and answer:
            docs.append(f"问题：{question}\n回答：{answer}")
            metadatas.append({
                "source": "SLAKE公开数据集", "data_type": "slake_vqa",
                "modality": item.get("modality", ""),
                "location": item.get("location", ""),
                "content_type": item.get("content_type", ""),
                "answer_type": item.get("answer_type", ""),
            })
    if docs:
        count = vs.add_documents(docs, metadatas)
        _log.info("SLAKE 数据集入库: %d 条", count)
    return len(docs)


def main(data_dir: str = None):
    _log.info("=" * 50)
    _log.info("初始化 RAG 医学知识库")
    _log.info("工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-影像分析 V1.0")
    _log.info("=" * 50)

    total = 0
    if data_dir:
        base = Path(data_dir)
    else:
        base = Path(os.getenv("MEDICAL_DATA_DIR", str(Path(__file__).resolve().parent.parent.parent.parent)))

    synthetic_dir = base / "medical_imaging_dataset"
    public_dir = base / "public_medical_datasets"

    synthetic_files = {
        "vqa_dataset.json": init_from_vqa_dataset,
        "mrg_dataset.json": init_from_mrg_dataset,
        "rag_knowledge_base.json": init_from_rag_dataset,
    }

    for fname, init_func in synthetic_files.items():
        fpath = synthetic_dir / fname
        if fpath.exists():
            _log.info("处理: %s", fname)
            data = load_json_dataset(str(fpath))
            total += init_func(data)
        else:
            _log.warning("文件不存在: %s", fpath)

    slake_dir = public_dir / "SLAKE"
    for fname in ["slake_train.json", "slake_validation.json", "slake_test.json"]:
        fpath = slake_dir / fname
        if fpath.exists():
            _log.info("处理: SLAKE/%s", fname)
            data = load_json_dataset(str(fpath))
            total += init_from_slake(data)

    medqa_path = public_dir / "Medical-Meadow-MedQA" / "medqa_train.json"
    if medqa_path.exists():
        _log.info("处理: MedQA/medqa_train.json")
        data = load_json_dataset(str(medqa_path))
        vs = get_vector_store()
        docs, metadatas = [], []
        for item in data[:5000]:
            inp, outp = item.get("input", ""), item.get("output", "")
            if inp and outp:
                docs.append(f"{inp}\n{outp}")
                metadatas.append({"source": "MedQA公开数据集", "data_type": "medqa"})
        if docs:
            count = vs.add_documents(docs, metadatas)
            total += count
            _log.info("MedQA 数据集入库: %d 条", count)

    _log.info("=" * 50)
    _log.info("知识库初始化完成！共导入 %d 条知识", total)
    _log.info("当前知识库文档数: %d", get_vector_store().count())
    _log.info("=" * 50)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="初始化 RAG 医学知识库")
    parser.add_argument("--data-dir", help="数据目录路径")
    args = parser.parse_args()
    main(data_dir=args.data_dir)
