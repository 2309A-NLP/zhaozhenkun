"""
rag_pipeline.py - RAG工单13 RAG流水线模块（核心需求）
需求: 构建带计时插桩的RAG问答流水线 — 工单"查询处理与增强/检索阶段/上下文组装/LLM生成/后处理"全流程
功能: 1.PDF解析→分块→BGE-M3编码→缓存 2.查询增强→查询嵌入→向量检索→上下文组装→LLM生成→后处理 3.全程计时
"""
import logging
import os, json, fitz, numpy as np  # 需求：文件、JSON、PDF解析、向量计算
from 研发.llm_client import call_llm     # 需求：LLM生成阶段调用MiMo API
import 研发.config as config              # 需求：读取模型路径、分块参数、API配置
from 研发.timer import Timer             # 需求：各阶段计时插桩
from 研发.query_enhancer import enhance_query        # 需求：查询处理与增强阶段
from 研发.post_processor import post_process         # 需求：后处理与响应格式化阶段

logger = logging.getLogger(__name__)
logger.info("RAG流水线模块加载")


# 全局模型单例——需求：避免每次查询重复加载BGE-M3（优化关键，减少8-15s/次）
_MODEL = None  # SentenceTransformer实例，首次调用时懒加载

def _get_model():
    """获取BGE-M3模型（只加载一次）——需求：嵌入阶段的核心优化点"""
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer
        import torch
        _MODEL = SentenceTransformer(config.BGE_MODEL_PATH, device="cuda", trust_remote_code=True)
        _MODEL.half()  # 需求：FP16半精度减少显存占用（RTX5060 8GB）
        _MODEL.max_seq_length = config.ENCODE_KWARGS["max_length"]  # 需求：控制序列长度避免OOM
    return _MODEL


def load_or_build_index(timer=None):
    """加载或构建向量索引（有缓存优先）——需求：离线步骤，避免每次跑都重新解析编码"""
    cache_meta = os.path.join(config.CACHE_DIR, "index_meta.json")
    cache_vec = os.path.join(config.CACHE_DIR, "vectors.npy")
    cache_chunks = os.path.join(config.CACHE_DIR, "chunks.json")
    if os.path.exists(cache_meta) and os.path.exists(cache_vec):
        print("📂 从缓存加载索引...")
        with open(cache_chunks, "r", encoding="utf-8") as f:
            chunks = json.load(f)
        vectors = np.load(cache_vec)
        with open(cache_meta, "r", encoding="utf-8") as f:
            chunk_meta = json.load(f)
        print(f"  ✅ {len(chunks)}块, {vectors.shape}")
        return chunks, vectors, chunk_meta

    print("🔨 构建索引...")
    if timer: timer.start("pdf_parse")
    doc = fitz.open(config.PDF_PATH)          # 需求：PyMuPDF解析PDF（支持中文）
    pages = []
    for pn in range(len(doc)):
        t = doc[pn].get_text().strip()
        if t:
            pages.append({"page": pn + 1, "text": t})
    doc.close()
    print(f"  ✅ PDF: {len(pages)}页")
    if timer: timer.stop("pdf_parse")

    if timer: timer.start("chunking")
    chunks = []
    cid = 0
    for p in pages:
        text = p["text"]
        start = 0
        while start < len(text):
            end = min(start + config.CHUNK_SIZE, len(text))  # 需求：固定长度分块
            chunk = text[start:end].strip()
            if chunk:
                chunks.append({"chunk_id": cid, "page": p["page"], "text": chunk})
                cid += 1
            start += config.CHUNK_SIZE - config.CHUNK_OVERLAP  # 需求：块间重叠保留语义连续性
    print(f"  ✅ 分块: {len(chunks)}块")
    if timer: timer.stop("chunking")

    if timer: timer.start("embedding")
    model = _get_model()
    texts = [c["text"] for c in chunks]
    embeds = model.encode(texts, batch_size=config.ENCODE_KWARGS["batch_size"],
                          show_progress_bar=config.ENCODE_KWARGS["show_progress_bar"],
                          normalize_embeddings=True)  # 需求：BGE-M3编码（1024维，已归一化）
    vectors = np.array(embeds, dtype=np.float32)
    chunk_meta = [{"chunk_id": c["chunk_id"], "page": c["page"]} for c in chunks]
    print(f"  ✅ 编码: {vectors.shape}")
    if timer: timer.stop("embedding")

    os.makedirs(config.CACHE_DIR, exist_ok=True)  # 需求：缓存向量和元数据（下次秒加载）
    np.save(cache_vec, vectors)
    with open(cache_meta, "w", encoding="utf-8") as f:
        json.dump(chunk_meta, f, ensure_ascii=False, indent=2)
    with open(cache_chunks, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)
    return chunks, vectors, chunk_meta


def rag_query(question, chunks, vectors, chunk_meta, timer=None):
    """执行RAG查询（5阶段计时）——需求：工单"查询处理与增强/检索/上下文组装/LLM生成/后处理与响应格式化"全流程"""
    stages = {}

    # Stage 0: 查询处理与增强——需求：工单要求分析此阶段耗时（清洗/关键词/扩展）
    if timer: timer.start("query_enhancement")
    enhanced = enhance_query(question)
    processed_query = enhanced["expanded_query"] if enhanced["needs_expansion"] else enhanced["cleaned_query"]
    if timer: stages["query_enhancement"] = timer.stop("query_enhancement")

    # Stage 1: 查询嵌入——需求：将处理后的查询编码为向量（全局单例模型，不重复加载）
    if timer: timer.start("query_embedding")
    model = _get_model()
    q_vec = model.encode(processed_query, normalize_embeddings=True)
    q_vec = np.array(q_vec, dtype=np.float32)
    if timer: stages["query_embedding"] = timer.stop("query_embedding")

    # Stage 2: 向量检索——需求：余弦相似度暴力搜索Top-K
    if timer: timer.start("vector_search")
    scores = np.dot(vectors, q_vec)        # 已归一化，点积即余弦相似度
    top_k = min(config.VECTOR_TOP_K, len(vectors))
    top_idx = np.argsort(scores)[::-1][:top_k]
    if timer: stages["vector_search"] = timer.stop("vector_search")

    # Stage 3: 上下文组装——需求：检索块拼接为LLM提示词
    if timer: timer.start("context_assembly")
    context_parts = []
    for idx in top_idx:
        c = chunks[idx]
        context_parts.append(f"[来源:第{c['page']}页 相似度{scores[idx]:.3f}]\n{c['text']}")
    context = "\n\n".join(context_parts)
    if timer: stages["context_assembly"] = timer.stop("context_assembly")

    # Stage 4: LLM生成——需求：MiMo API生成答案（通常最慢）
    if timer: timer.start("llm_generation")
    prompt = (f"请基于以下文献内容回答用户问题。\n\n【文献内容】\n{context}\n\n"
              f"【用户问题】\n{processed_query}\n\n请给出准确、简洁的回答：")
    try:
        raw_answer = call_llm(prompt, temperature=config.LLM_TEMPERATURE, max_tokens=config.LLM_MAX_TOKENS)
    except Exception as e:
        raw_answer = f"[生成失败]{e}"
    if timer: stages["llm_generation"] = timer.stop("llm_generation")

    # Stage 5: 后处理与响应格式化——需求：工单要求分析此阶段耗时（格式/截断/参考来源/置信度）
    if timer: timer.start("post_processing")
    post_result = post_process(raw_answer, context_parts)
    final_answer = post_result["formatted_answer"]
    if timer: stages["post_processing"] = timer.stop("post_processing")

    return {
        "answer": final_answer,
        "raw_answer": raw_answer,
        "context": f"检索到{top_k}个文本块",
        "stages": stages,
        "stage_timings": stages,
        "query_enhancement": enhanced,
        "post_processing": post_result,
        "top_pages": list(set(c["page"] for c in [chunks[i] for i in top_idx]))
    }

