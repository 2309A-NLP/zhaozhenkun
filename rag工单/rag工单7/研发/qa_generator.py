"""
qa_generator.py - RAG工单7 问答生成模块
工单编号: 人工智能NLP-RAG-功能测试及评估
功能: 基于MiMo API生成测试问题的回答，
      使用检索到的CCF年报文本块作为上下文
"""

import logging, json, time

# 导入配置
from config import MIMO_API_KEY, MIMO_BASE_URL, MIMO_MODEL, OUTPUT_DIR, LOG_FMT, LOG_DATEFMT

# 设置日志
logging.basicConfig(format=LOG_FMT, datefmt=LOG_DATEFMT, level=logging.INFO)
logger = logging.getLogger("qa_generator")


def build_prompt(question, retrieved_chunks):
    """
    构建问答提示词
    参数:
        question: 用户问题
        retrieved_chunks: 检索到的文本块列表
    返回:
        str: 完整的提示词
    """
    # 拼接上下文
    context_parts = []
    for i, chunk in enumerate(retrieved_chunks):
        source = chunk.get("source_pdf", "未知来源")
        page = chunk.get("page_num", 0)
        context_parts.append(f"[{i+1}]来源: {source}(第{page}页)\n{chunk['content'][:500]}")

    context = "\n\n".join(context_parts)

    prompt = f"""你是一个金融年报分析助手。请基于以下CCF竞赛年报文档内容回答问题。

【文档内容】
{context}

【问题】
{question}

请基于以上文档内容给出准确、简洁的回答。如果文档中没有足够信息，请如实说明"文档中未找到相关信息"。
"""
    return prompt


class QAGenerator:
    """DeepSeek API问答生成器"""
    def __init__(self):
        self.client = None

    def _ensure_client(self):
        """延迟初始化OpenAI客户端(MiMo API)"""
        if self.client:
            return
        from openai import OpenAI
        self.client = OpenAI(
            api_key=MIMO_API_KEY,
            base_url=MIMO_BASE_URL,
        )

    def generate(self, question, retrieved_chunks):
        """
        生成回答
        参数:
            question: 问题文本
            retrieved_chunks: 检索到的文本块
        返回:
            dict: 包含answer, source_chunks, response_time
        """
        self._ensure_client()
        prompt = build_prompt(question, retrieved_chunks)

        start = time.time()
        try:
            response = self.client.chat.completions.create(
                model=MIMO_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=800,
            )
            msg = response.choices[0].message
            answer = msg.content or msg.reasoning_content or "【无响应内容】"
            elapsed = time.time() - start
            logger.info(f"回答生成完成! 耗时{elapsed:.2f}秒, {len(answer)}字")
        except Exception as e:
            logger.error(f"API调用失败: {e}")
            answer = "【API调用失败】请检查网络连接和API密钥"
            elapsed = time.time() - start

        return {
            "answer": answer,
            "source_chunks": [
                {"source_pdf": c.get("source_pdf"), "page_num": c.get("page_num"), "score": c.get("score", 0)}
                for c in retrieved_chunks
            ],
            "response_time": round(elapsed, 2),
        }

    def generate_batch(self, questions_data):
        """
        批量生成回答
        参数:
            questions_data: [{"question": str, "retrieved_chunks": list}, ...]
        返回:
            list
        """
        results = []
        for qd in questions_data:
            result = self.generate(qd["question"], qd["retrieved_chunks"])
            result["question"] = qd["question"]
            results.append(result)
            logger.info(f"进度: {len(results)}/{len(questions_data)}")
        return results


if __name__ == "__main__":
    """单独测试问答生成"""
    qa = QAGenerator()
    test_chunks = [{
        "content": "平安银行2019年实现营业收入1379亿元，同比增长18.2%",
        "source_pdf": "平安银行_2019_年报.pdf",
        "page_num": 5,
        "score": 0.92,
    }]
    result = qa.generate("平安银行2019年营收多少？", test_chunks)
    print(f"答案: {result['answer'][:200]}")
