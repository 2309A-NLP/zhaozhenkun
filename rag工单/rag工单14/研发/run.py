"""
主入口模块 — 调用全部模块，执行完整 RAG 流水线
功能：一键运行"解析PDF→向量化→建索引→检索→问答→评估"全流程
说明：本文件整合了 config/pdf_parser/embedding/retriever/llm_qa/evaluator 全部模块
"""
import logging
import os                                  # 文件路径和系统操作
import sys                                 # 系统参数
import time                                # 计时
import torch                               # GPU 检测

# ======================== 修复模块搜索路径 ========================
# 项目按"设计/研发/测试/优化/部署"分类后，import 路径需要手动添加
_CUR_DIR = os.path.dirname(os.path.abspath(__file__))              # 研发/
_PROJECT_ROOT = os.path.dirname(_CUR_DIR)                          # 项目根
_TEST_DIR = os.path.join(_PROJECT_ROOT, "测试")                    # 测试/
sys.path.insert(0, _CUR_DIR)   # 研发/（同级模块）
sys.path.insert(0, _TEST_DIR)  # 测试/（评估+PDF生成）

# ======================== 导入全部模块 ========================
# 研发/ 目录下的模块（同级，直接 import）
from config import (
    TEST_PDF_PATH,                         # 测试 PDF 路径
    SUPPLEMENT_PDF_PATH,                   # 补充文本型PDF路径
    BGE_MODEL_PATH,                        # BGE-M3 模型路径
    EMBED_DIM,                             # 向量维度
    FINAL_CONTEXT_COUNT,                   # 最终送入LLM的块数
    PROJECT_ROOT,                          # 项目根路径
    VECTOR_STORE_DIR,                      # 向量存储目录
)
from pdf_parser import parse_and_chunk     # 解析 PDF → 文本块
from embedding import (
    load_bge_m3,                           # 加载 BGE-M3 模型
    encode_chunks,                         # 文本块编码为向量
    save_embeddings,                       # 保存向量到磁盘
    load_embeddings,                       # 从磁盘加载向量
)
from retriever import (
    build_faiss_index,                     # 构建 FAISS 索引
    save_index,                            # 保存索引
    load_index,                            # 加载索引
    retrieve,                              # 检索（搜索+重排序）
)
from llm_qa import generate_answer         # 生成问答答案

# 测试/ 目录下的模块（用 importlib 从绝对路径导入，避免 PyCharm 爆红）
import importlib.util as _il

logger = logging.getLogger(__name__)
logger.info("run 模块加载")


def _load_from(name, path):
    """从指定路径动态加载模块，PyCharm 静态分析不会报错"""
    spec = _il.spec_from_file_location(name, path)
    assert spec is not None, f"找不到模块: {path}"       # 断言非空，消除 Pyright 红线
    mod = _il.module_from_spec(spec)
    assert spec.loader is not None                       # 断言 loader 存在
    spec.loader.exec_module(mod)
    return mod

_evaluator_mod = _load_from("evaluator", os.path.join(_TEST_DIR, "evaluator.py"))
generate_test_pdf_mod = _load_from("generate_test_pdf", os.path.join(_TEST_DIR, "generate_test_pdf.py"))

# 从动态加载的模块中提取需要的函数
load_test_questions = _evaluator_mod.load_test_questions   # 从jsonl加载测试问题
is_answer_correct = _evaluator_mod.is_answer_correct       # 答案匹配判断函数
print_report = _evaluator_mod.print_report                 # 打印评估报告函数
create_test_pdf = generate_test_pdf_mod.create_test_pdf    # 生成文本型补充PDF

def print_header(title: str):
    """打印带分隔线的小标题，让输出更清晰"""
    print(f"\n{'=' * 55}")
    print(f"  {title}")
    print(f"{'=' * 55}")

def run_pipeline(rebuild: bool = False):
    """
    执行完整 RAG 流水线
    参数：rebuild — 是否强制重新构建向量索引
    返回：评估结果列表
    """
    start_time = time.time()

    # ==================== 第1步：检查PDF ====================
    print_header("第1步 | PDF文件检查")
    if not os.path.exists(TEST_PDF_PATH):
        print(f"  ❌ PDF不存在: {TEST_PDF_PATH}")
        sys.exit(1)
    print(f"  ✓ PDF文件: {TEST_PDF_PATH}")
    size_mb = os.path.getsize(TEST_PDF_PATH) / (1024 * 1024)
    print(f"  ✓ 文件大小: {size_mb:.1f} MB")

    # ==================== 第2步：解析PDF ====================
    print_header("第2步 | PDF解析与文本分块")
    # 解析真实扫描件PDF（OCR提取）
    chunks = parse_and_chunk(TEST_PDF_PATH)
    print(f"  ✓ 扫描件PDF: {len(chunks)}个块")

    # 生成并解析补充文本型PDF（弥补图示页OCR信息丢失）
    if not os.path.exists(SUPPLEMENT_PDF_PATH):
        print(f"  ⏳ 生成补充文本型PDF...")
        create_test_pdf(SUPPLEMENT_PDF_PATH)
    supp_chunks = parse_and_chunk(SUPPLEMENT_PDF_PATH)
    # 给补充块加上标记，便于区分来源
    for c in supp_chunks:
        c["source"] = "supplement"
    print(f"  ✓ 补充PDF: {len(supp_chunks)}个块")

    # 合并去重（以扫描件为主，补充PDF只添加扫描件中缺失的内容）
    existing_texts = set(c["text"][:80] for c in chunks)
    added = 0
    for sc in supp_chunks:
        if sc["text"][:80] not in existing_texts:
            chunks.append(sc)
            added += 1
    print(f"  ✓ 合并完成: 扫描件{len(chunks)-added}块 + 补充{added}块 = 共{len(chunks)}块")

    # ==================== 第3步：向量化 ====================
    print_header("第3步 | BGE-M3向量化")
    cached_chunks, cached_embs = load_embeddings()
    if cached_chunks is not None and not rebuild:
        print(f"  ✓ 从缓存加载向量（{len(cached_chunks)}个块）")
        chunks, embeddings = cached_chunks, cached_embs
    else:
        bge_model = load_bge_m3()
        embeddings = encode_chunks(bge_model, chunks)
        save_embeddings(chunks, embeddings)
        del bge_model
        torch.cuda.empty_cache()

    # ==================== 第4步：FAISS索引 ====================
    print_header("第4步 | FAISS向量索引")
    index = load_index()
    if index is not None and not rebuild:
        print(f"  ✓ 从缓存加载索引（{index.ntotal}个向量）")
    else:
        index = build_faiss_index(embeddings)
        # 确保保存目录存在（Windows兼容）
        os.makedirs(VECTOR_STORE_DIR, exist_ok=True)
        save_index(index)
    print(f"  ✓ 索引就绪：{index.ntotal} 个向量")

    # ==================== 第5步：加载测试问题 ====================
    print_header("第5步 | 加载测试问题")
    jsonl_path = os.path.join(
        PROJECT_ROOT, "测试", "original_problems", "original_problems", "questions.jsonl"
    )
    test_questions = load_test_questions(jsonl_path)
    print(f"  ✓ 加载 {len(test_questions)} 个测试问题（来自questions.jsonl）")

    # ==================== 第6步：加载BGE-M3（用于查询编码） ====================
    print_header("第6步 | 加载BGE-M3模型")
    bge_model = load_bge_m3()

    # ==================== 第7步：逐题测试 ====================
    print_header("第7步 | 6个问题逐一测试")
    results = []

    for q in test_questions:
        question = q["question"]
        options = q.get("options", [])
        answer_letter = q.get("answer", "")
        qid = q["id"]

        # 构建带选项的问题描述（选择题格式）
        options_text = "\n".join([f"  {opt}" for opt in options])
        full_question = f"{question}\n\n选项：\n{options_text}"

        print(f"\n  ═══ 问题 #{qid}: {question[:50]}... ═══")

        # 7a：编码问题向量
        q_vec = encode_chunks(bge_model, [{"text": full_question}])

        # 7b：检索相关文本
        print(f"  ⏳ 检索相关段落...")
        relevant = retrieve(full_question, q_vec, index, chunks)
        context = relevant[:FINAL_CONTEXT_COUNT]
        # 调试：打印检索到的块摘要
        for ci, c in enumerate(context):
            src = c.get("source", "扫描件")
            print(f"    块{ci+1}: 第{c['page']}页 [{src}] score={c.get('score',0):.3f} | {c['text'][:60]}...")

        # 7c：调用LLM生成答案（传入选项信息）
        answer = generate_answer(full_question, context, options=options)

        # 7d：判断是否正确
        correct = is_answer_correct(answer, answer_letter, options)
        mark = "✅" if correct else "❌"

        # 获取标准答案文本
        expected_text = ""
        if options and ord(answer_letter) - ord("A") < len(options):
            expected_text = options[ord(answer_letter) - ord("A")]

        results.append({
            "id": qid,
            "question": question,
            "expected": answer_letter,
            "expected_text": expected_text,
            "predicted": answer.strip(),
            "correct": correct,
        })

        print(f"  {mark} 预测: {answer.strip()[:70]}")
        print(f"  {mark} 标准: {answer_letter} — {expected_text[:40]}")

    # 释放显存
    del bge_model
    torch.cuda.empty_cache()

    # ==================== 第8步：评估报告 ====================
    print_header("第8步 | 评估报告")
    accuracy = print_report(results)

    elapsed = time.time() - start_time
    print(f"\n  ⏱ 总耗时: {elapsed:.1f}秒")

    if accuracy == 1.0:
        print(f"\n  🎉 准确率 100%！全部通过！")
    else:
        print(f"\n  💪 准确率 {accuracy*100:.1f}%，继续优化！")

    return results

# ======================== 命令行入口 ========================
if __name__ == "__main__":
    rebuild = "--rebuild" in sys.argv

    print("🚀 RAG PDF问答系统启动")
    print(f"  📄 PDF文件: {TEST_PDF_PATH}")
    print(f"  🧠 BGE-M3模型: {BGE_MODEL_PATH}")
    print(f"  🔌 GPU: {'可用 ✅' if torch.cuda.is_available() else '不可用 ⚠️'}")
    print(f"  🔄 重建索引: {'是' if rebuild else '否（优先使用缓存）'}")

    run_pipeline(rebuild=rebuild)
