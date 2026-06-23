# -*- coding: utf-8 -*-
"""
batch_runner.py — 批量问答处理器
功能: 读取question.jsonl，逐题调用NL2SQL处理，写入answer_result.jsonl
      支持断点续传、进度保存、超时跳过、日志追踪
工单编号: 人工智能NLP-Agent数字人项目-基金问答智能体任务
"""
import json
import os
import sys
import time
import signal
import traceback

研发_DIR = os.path.dirname(os.path.abspath(__file__))
if 研发_DIR not in sys.path:
    sys.path.insert(0, 研发_DIR)

from logger import setup_logging, get_logger

# 全局中断标记
_interrupted = False


def signal_handler(sig, frame):
    global _interrupted
    _interrupted = True
    print("\n中断信号收到，将在当前题完成后保存退出...")


signal.signal(signal.SIGINT, signal_handler)

# 进度文件（断点续传）
PROGRESS_FILE = None
OUTPUT_FILE = None
RESULT_DIR = None


def load_progress():
    """读取已完成的题目ID集合。"""
    completed = set()
    if PROGRESS_FILE and os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        completed.add(int(line))
        except Exception:
            pass
    return completed


def save_progress(question_id):
    """追加一条已完成的题目ID。"""
    if PROGRESS_FILE:
        try:
            with open(PROGRESS_FILE, "a", encoding="utf-8") as f:
                f.write(f"{question_id}\n")
        except Exception:
            pass


def append_result(record):
    """追加一条JSON结果到输出文件。"""
    if OUTPUT_FILE:
        try:
            with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass


def save_completed_ids(ids_set):
    """保存全部已完成ID（用于中断时完整保存）。"""
    if PROGRESS_FILE:
        try:
            with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
                for qid in sorted(ids_set):
                    f.write(f"{qid}\n")
        except Exception:
            pass


def run_batch(questions, process_fn, logger, output_dir=None, resume=True):
    """
    批量处理主函数。

    Args:
        questions: list of {"id": int, "question": str}
        process_fn: 处理函数(question_text) -> answer_text
        logger: 日志实例
        output_dir: 输出目录
        resume: 是否断点续传

    Returns:
        dict: {"total": int, "completed": int, "skipped": int, "failed": int, "elapsed": float}
    """
    global _interrupted, PROGRESS_FILE, OUTPUT_FILE, RESULT_DIR

    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(__file__))
    RESULT_DIR = output_dir

    PROGRESS_FILE = os.path.join(output_dir, "batch_progress.txt")
    OUTPUT_FILE = os.path.join(output_dir, "answer_result.jsonl")

    completed = load_progress() if resume else set()
    total = len(questions)
    success = 0
    skipped = 0
    failed = 0
    t0 = time.time()

    logger.info("=" * 55)
    logger.info(f"批量处理开始: {total} 题")
    logger.info(f"输出文件: {OUTPUT_FILE}")
    logger.info(f"已完成的跳过: {len(completed)} 题")
    logger.info("=" * 55)

    for i, q in enumerate(questions):
        if _interrupted:
            save_completed_ids(completed)
            logger.warning(f"用户中断，已保存 {len(completed)} 题进度")
            break

        qid = q["id"]
        question = q["question"]

        # 断点续传：跳过已完成的
        if qid in completed:
            skipped += 1
            continue

        # 处理单题
        logger.info(f"[{i+1}/{total}] ID={qid}: {question[:60]}...")
        t_start = time.time()

        try:
            answer = process_fn(question)
            elapsed = time.time() - t_start

            if answer:
                record = {
                    "id": qid,
                    "question": question,
                    "answer": answer,
                    "elapsed": round(elapsed, 2)
                }
                append_result(record)
                completed.add(qid)
                save_progress(qid)
                success += 1
                logger.info(f"  ✓ 完成 ({elapsed:.1f}s) → {answer[:80]}...")
            else:
                failed += 1
                logger.warning(f"  ✗ 空答案 ({elapsed:.1f}s)")
                # 写入空答案避免断点跳过
                record = {"id": qid, "question": question, "answer": "（未获取到答案）", "elapsed": round(elapsed, 2)}
                append_result(record)
                completed.add(qid)
                save_progress(qid)

        except Exception as e:
            elapsed = time.time() - t_start
            failed += 1
            logger.error(f"  ✗ 异常 ({elapsed:.1f}s): {e}")
            logger.error(traceback.format_exc()[:200])
            # 写入空答案
            record = {"id": qid, "question": question, "answer": f"（处理出错: {e}）", "elapsed": round(elapsed, 2)}
            try:
                append_result(record)
                completed.add(qid)
                save_progress(qid)
            except Exception:
                pass

        # 进度报告
        processed = success + failed
        if processed > 0 and processed % 10 == 0:
            total_elapsed = time.time() - t0
            rate = processed / total_elapsed if total_elapsed > 0 else 0
            eta = (total - len(completed)) / rate if rate > 0 else 0
            logger.info(f"  --- 进度: {processed}/{total-len(completed)} 完成, "
                       f"速率={rate:.1f}题/分, 预计剩余={eta/60:.0f}分钟 ---")

    total_elapsed = time.time() - t0
    logger.info("=" * 55)
    logger.info(f"批量处理完成: 总{total}题, 成功{success}, 跳过{skipped}, 失败{failed}")
    logger.info(f"总耗时: {total_elapsed/60:.1f}分钟")
    logger.info(f"输出文件: {OUTPUT_FILE}")
    logger.info("=" * 55)

    return {
        "total": total,
        "completed": success,
        "skipped": skipped,
        "failed": failed,
        "elapsed": round(total_elapsed, 2),
        "output": OUTPUT_FILE
    }


def load_questions(question_path):
    """从JSONL文件加载所有题目。"""
    questions = []
    if not os.path.exists(question_path):
        raise FileNotFoundError(f"题目文件不存在: {question_path}")
    with open(question_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    q = json.loads(line)
                    questions.append(q)
                except json.JSONDecodeError:
                    pass
    return questions
