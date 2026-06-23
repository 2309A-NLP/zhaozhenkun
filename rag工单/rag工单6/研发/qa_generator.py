"""
qa_generator.py - RAG工单6 问答生成模块
需求: 混合检索+多轮对话 — 调用小米MiMo API生成答案，支持对话历史注入
功能: 构建提示词(含历史上下文) → MiMo API → 置信度评估 → 返回答案
"""
import logging, time, re

from config import MIMO_API_KEY, MIMO_BASE_URL, MIMO_MODEL, MIMO_TIMEOUT, MIMO_MAX_TOKENS, WO_ID, LOG_FMT, LOG_DATEFMT

logging.basicConfig(format=LOG_FMT, datefmt=LOG_DATEFMT, level=logging.INFO)
logger = logging.getLogger("qa_generator")


def build_prompt(question, context, lang="auto", history=""):
    """构建问答提示词，支持对话历史注入"""
    if lang == "auto":
        lang = "zh" if re.search(r'[\u4e00-\u9fff]', question) else "en"
    parts = []
    for i, r in enumerate(context):
        src = f"第{r['page_num']}页" if lang == "zh" else f"Page {r['page_num']}"
        parts.append(f"--- {'上下文' if lang=='zh' else 'Context'} {i+1} ({src}) ---\n{r['content']}")
    ctx_str = "\n\n".join(parts)
    if lang == "zh":
        hist_str = f"\n\n=== 对话历史 ===\n{history}\n" if history else ""
        return (f"你是一个专业的PDF问答助手。根据上下文和历史对话回答问题。\n"
                f"工单编号: {WO_ID}\n要求: 1.只基于上下文回答 2.上下文不足则说明 3.引用页码"
                f"{hist_str}"
                f"\n\n=== 上下文 ===\n{ctx_str}\n\n=== 问题 ===\n{question}\n\n=== 回答 ===")
    else:
        hist_str = f"\n\n=== Chat History ===\n{history}\n" if history else ""
        return (f"You are a PDF Q&A assistant. Answer based on context and history.\n"
                f"Work Order: {WO_ID}\nRules: 1.Answer from context 2.State if insufficient 3.Cite pages"
                f"{hist_str}"
                f"\n\n=== Context ===\n{ctx_str}\n\n=== Question ===\n{question}\n\n=== Answer ===")


def generate_answer(question, context, max_retries=2, use_mimo=True, history=""):
    """
    调用MiMo API生成答案，支持对话历史
    参数: question-问题, context-检索上下文, history-多轮对话历史文本
    返回: {answer, confidence, sources, response_time}
    """
    if use_mimo and not MIMO_API_KEY:
        use_mimo = False
    start = time.time()
    lang = "zh" if re.search(r'[\u4e00-\u9fff]', question) else "en"
    prompt = build_prompt(question, context, lang=lang, history=history)
    sources = [{"page_num": r["page_num"], "score": float(r.get("score", 0)),
                "source_pdf": r.get("source_pdf", "")} for r in context]
    api_key = MIMO_API_KEY if use_mimo else ""
    base_url = MIMO_BASE_URL if use_mimo else ""
    model = MIMO_MODEL if use_mimo else "deepseek-chat"

    for attempt in range(max_retries + 1):
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key, base_url=base_url)
            system = "你是一个专业的PDF问答助手。" if lang == "zh" else "You are a PDF Q&A assistant."
            resp = client.chat.completions.create(
                model=model, timeout=MIMO_TIMEOUT,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": prompt}],
                temperature=0.1, max_tokens=MIMO_MAX_TOKENS,
            )
            raw = resp.choices[0].message.content or ""
            answer = raw.strip()
            if not answer:
                rc = resp.choices[0].message.model_extra or {}
                answer = rc.get("reasoning_content", "").strip() or "模型返回为空"
            if len(answer) < 10 or any(kw in answer[:20] for kw in ["无法", "没有", "不", "抱歉"]):
                conf = "low"
            elif len(context) >= 2:
                conf = "high"
            else:
                conf = "medium"
            return {"question": question, "answer": answer, "confidence": conf,
                    "sources": sources, "response_time": round(time.time() - start, 2)}
        except Exception as e:
            logger.warning(f"MiMo失败 (第{attempt+1}次): {e}")
            if attempt < max_retries:
                time.sleep(2 ** attempt)
    return {"question": question, "answer": "生成答案失败", "confidence": "low",
            "sources": sources, "response_time": round(time.time() - start, 2)}


if __name__ == "__main__":
    ctx = [{"content": "注册资本5,520万元", "page_num": 52, "score": 0.95}]
    r = generate_answer("武汉兴图新科注册资本？", ctx)
    print(f"答案: {r['answer'][:80]}\n置信度: {r['confidence']}\n耗时: {r['response_time']}秒")
