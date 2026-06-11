"""
问答生成模块（研发层）
功能：基于检索上下文调用 LLM 生成自然语言回答，支持 RAG 和 LightRAG 两种模式
完成：上下文拼接 → prompt 构造 → MiMo API 调用 → 批量生成 + 双模式对比
"""
import logging
import sys, os
# 将项目根目录加入路径，支持从任意子目录导入其他模块
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _sub in ["设计", "研发", "测试", "部署", "优化"]:
    _p = os.path.join(_root, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

from llm_client import call_llm  # 小米 MiMo API 调用
import config                    # 全局配置

logger = logging.getLogger(__name__)
logger.info("问答生成模块加载")

logger = logging.getLogger(__name__)


# 问答生成的系统提示词：指导 LLM 基于检索上下文准确回答
QA_SYSTEM_PROMPT = (
    "你是一个专业的金融文档问答助手。\n"
    "请基于提供的上下文信息，准确回答用户的问题。\n\n"
    "要求：\n"
    "1. 只基于给定的上下文作答，不要编造信息\n"
    "2. 如果上下文不足以回答问题，请明确说'根据提供的上下文，无法找到相关信息'\n"
    "3. 回答要简洁、准确，引用具体数据\n"
    "4. 如果问题涉及多个要点，分点列出"
)


def build_context(results: list[dict]) -> str:
    """
    将检索结果列表拼接成 LLM 可用的格式化上下文
    参数：
        results: [{"source_pdf", "page_num", "text", "score", "source"}, ...]
    返回：
        带编号和来源标注的上下文字符串
    """
    context_parts = []  # 每段上下文的字符串
    for i, r in enumerate(results, 1):
        # 来源标注：PDF文件名 + 页码
        source_info = f"{r.get('source_pdf', '未知')} 第{r.get('page_num', 0)}页"
        text = r.get("text", "")[:500]  # 每段截取前500字符（太长影响 LLM 处理）
        context_parts.append(f"[{i}] 来源: {source_info}\n{text}\n")
    return "\n".join(context_parts)  # 空行分隔各段


def generate_answer(
    question: str,
    context: str,
    mode: str = "RAG"
) -> dict:
    """
    基于检索上下文调用 LLM 生成单个问题的回答
    参数：
        question: 用户提问原文
        context:  拼接好的检索上下文字符串
        mode:     检索模式标识（RAG 或 LightRAG，仅用于返回标记）
    返回：
        {"question": str, "answer": str, "mode": str}
    """
    # 构造完整 prompt：上下文 + 问题
    prompt = (
        f"以下是与问题相关的检索信息：\n\n"
        f"{context}\n\n"
        f"请基于以上信息回答以下问题：\n{question}"
    )
    try:
        # 调用 LLM（温度 0.3 保证回答确定性，不宜太低否则过于机械）
        answer = call_llm(
            prompt=prompt,
            system_prompt=QA_SYSTEM_PROMPT,
            temperature=0.3
        )
    except Exception as e:
        # LLM 调用失败时返回错误信息（不中断批量流程）
        answer = f"[生成回答时出错] {e}"
    return {
        "question": question,  # 原始问题
        "answer": answer,      # LLM 生成的回答
        "mode": mode           # 检索模式
    }


def batch_generate(
    questions: list[dict],
    rag_contexts: list[str],
    lightrag_contexts: list[str]
) -> tuple[list[dict], list[dict]]:
    """
    批量生成 RAG 和 LightRAG 两种模式的全部回答
    参数：
        questions:         [{"id": int, "question": str}, ...] 问题列表
        rag_contexts:      [str, ...] 每题 RAG 检索上下文
        lightrag_contexts: [str, ...] 每题 LightRAG 检索上下文
    返回：
        (rag_answers, lightrag_answers)
        每个是 generate_answer 返回列表
    """
    rag_results = []       # RAG 模式回答列表
    lightrag_results = []  # LightRAG 模式回答列表

    print("🤖 开始批量生成回答...")
    total = len(questions)

    for i in range(total):
        q = questions[i]           # 当前问题
        q_text = q["question"]     # 问题文本
        q_id = q["id"]             # 问题编号
        print(f"  问题 {q_id} ({i+1}/{total})...")

        # RAG 模式：基于纯向量检索上下文生成回答
        rag_ans = generate_answer(q_text, rag_contexts[i], mode="RAG")
        rag_results.append(rag_ans)

        # LightRAG 模式：基于向量+图谱混合检索上下文生成回答
        lr_ans = generate_answer(q_text, lightrag_contexts[i], mode="LightRAG")
        lightrag_results.append(lr_ans)

    print(f"✅ 回答生成完成: RAG={len(rag_results)}条, "
          f"LightRAG={len(lightrag_results)}条")
    return rag_results, lightrag_results
