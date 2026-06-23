# -*- coding: utf-8 -*-
"""
generator.py — RAG答案生成器
功能：构建RAG提示词 → 调用DeepSeek API → 基于检索上下文生成答案
      包含API重试机制和答案后处理
工单编号：人工智能NLP-Agent数字人项目-招股书数据问答智能体任务
"""

import time  # 计时和重试延迟
import logging  # 日志
import requests  # HTTP请求
import config  # 配置文件
from retriever import search, format_retrieved_context  # 检索器

logger = logging.getLogger(__name__)  # 模块日志器


def call_deepseek(messages, max_retries=None):
    """调用DeepSeek Chat API，返回生成的文本（含重试机制）"""
    if max_retries is None:  # 未指定
        max_retries = config.MAX_RETRIES  # 默认值
    url = f"{config.DEEPSEEK_BASE_URL.rstrip('/')}/chat/completions"  # API端点
    headers = {"Authorization": f"Bearer {config.DEEPSEEK_API_KEY}", "Content-Type": "application/json"}  # 请求头
    payload = {"model": config.DEEPSEEK_MODEL, "messages": messages, "temperature": 0.0,
               "max_tokens": 1536, "top_p": 1.0, "stream": False}  # 请求体
    last_error = None  # 最后一次错误
    for attempt in range(max_retries):  # 重试循环
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=config.API_TIMEOUT)  # 请求
            if resp.status_code == 200:  # 成功
                return resp.json()["choices"][0]["message"]["content"].strip()  # 提取回复
            last_error = f"HTTP {resp.status_code}"  # 记录HTTP错误
        except requests.exceptions.Timeout:  # 超时
            last_error = "超时"  # 记录
        except Exception as e:  # 其他异常
            last_error = str(e)  # 记录
        if attempt < max_retries - 1:  # 还有重试机会
            time.sleep((attempt + 1) * 2)  # 指数退避
    logger.error("API调用失败: %s", last_error)  # 错误日志
    return f"[API调用失败: {last_error}]"  # 返回失败信息


def build_rag_prompt(question, retrieved_chunks, retrieved_metadata, retrieved_scores):
    """构建RAG问答的System+User消息"""
    context = format_retrieved_context(retrieved_chunks, retrieved_metadata, retrieved_scores)  # 格式化上下文
    system_content = """你是一位专业的招股书分析师。你的任务是仔细阅读提供的招股书文本片段，从中找出与用户问题相关的信息，并给出准确、简洁的回答。

## 回答规则
1. 仔细阅读所有提供的文本片段，找到与问题直接相关的信息
2. 如果文本中包含答案，请准确引用原文信息，不要编造
3. 如果文本中只有部分相关信息，说明已知部分，指出缺失的部分
4. 如果所有文本片段都不包含相关信息，明确回答"所提供的招股书文本中未包含该信息"
5. 保留原文中的数字精度（百分比、金额、数量等）
6. 如果涉及人名、公司名、日期，请完整列出"""
    user_content = f"""## 招股书文本片段

{context}

## 用户问题

{question}

请基于以上文本回答问题。"""
    messages = [{"role": "system", "content": system_content}, {"role": "user", "content": user_content}]  # 消息
    return messages  # 返回


def generate_answer(question, vectorizer, chunk_vectors, all_chunks, chunk_metadata, top_k=None, company_map=None):
    """完整的RAG流水线：检索 → 构建Prompt → 调用LLM → 返回答案"""
    if top_k is None:  # 未指定
        top_k = config.TOP_K  # 默认
    # 检索相关文本块
    retrieved_chunks, retrieved_metadata, retrieved_scores = search(
        question, vectorizer, chunk_vectors, all_chunks, chunk_metadata, top_k, company_map=company_map)
    if not retrieved_chunks:  # 没有检索到
        logger.warning("未检索到相关内容: %s", question[:60])  # 警告
        return "未在招股书文本中找到相关信息"  # 返回空
    logger.info("检索到 %d 块，生成答案中...", len(retrieved_chunks))  # 日志
    # 构建Prompt并生成
    messages = build_rag_prompt(question, retrieved_chunks, retrieved_metadata, retrieved_scores)  # 构建
    answer = call_deepseek(messages)  # 调用LLM
    return answer  # 返回


if __name__ == "__main__":  # 测试
    logging.basicConfig(level=logging.INFO, format="%(message)s")  # 日志配置
    from indexer import get_or_build_index  # 索引器
    logger.info("加载索引...")  # 提示
    idx = get_or_build_index(config.PDF_TXT_DIR, config.INDEX_CACHE_DIR, config.CHUNK_SIZE, config.CHUNK_OVERLAP)
    vec, cv, chunks, meta, cmap = idx  # 解包
    q = "湖南长远锂科股份有限公司变更设立时作为发起人的法人有哪些？"  # 测试
    a = generate_answer(q, vec, cv, chunks, meta, company_map=cmap)  # 生成
    logger.info("答案: %s", a[:300])  # 打印
