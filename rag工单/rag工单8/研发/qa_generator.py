"""
qa_generator.py - RAG工单8 DeepSeek问答生成模块
工单编号: 人工智能NLP-RAG-基于Graph RAG 实现金融问答
功能: 基于检索到的上下文（向量或图谱增强），使用DeepSeek
      API生成金融年报相关问题的回答
"""

import logging, json, time
from config import MIMO_API_KEY, MIMO_BASE_URL, MIMO_MODEL, \
    LOG_FMT, LOG_DATEFMT

logging.basicConfig(format=LOG_FMT, datefmt=LOG_DATEFMT, level=logging.INFO)
logger = logging.getLogger("qa_generator")


class QAGenerator:
    """基于DeepSeek的金融问答生成器"""

    def __init__(self):
        self.client = None

    def _get_client(self):
        """延迟初始化OpenAI客户端(MiMo)"""
        if self.client is None:
            from openai import OpenAI
            self.client = OpenAI(api_key=MIMO_API_KEY, base_url=MIMO_BASE_URL)
        return self.client

    def generate(self, question, context_chunks, use_graph=False, lang="zh"):
        """
        根据检索到的上下文生成回答（支持中英文双语）
        Args:
            question: 用户问题字符串
            context_chunks: 检索到的上下文块列表
            use_graph: 是否使用了图谱增强(仅影响回答描述)
            lang: 语言选择 "zh"=中文 "en"=English
        Returns:
            dict: {"answer": 回答文本, "response_time": 耗时秒,
                   "model": 模型名, "sources": [源文件列表]}
        """
        client = self._get_client()
        # 组装上下文
        context = ""
        sources = set()
        for i, chunk in enumerate(context_chunks):
            text = chunk.get("text", chunk.get("content", ""))[:800]
            context += f"[{i+1}] {text}\n\n"
            src = chunk.get("source_pdf", "")
            if src:
                sources.add(src)

        mode_desc = "知识图谱增强检索" if use_graph else "向量检索"
        # 根据语言切换prompt（多语言支持需求）
        if lang == "en":
            user_prompt = f"""Please answer the following question based on the reference materials.

Reference Materials:
{context}

Question: {question}

Requirements:
1. Answer only based on the information in the reference materials
2. If the reference materials are insufficient, clearly state so
3. Use concise and professional financial analysis language
4. Cite source numbers when referencing specific data

Answer:"""
        else:
            user_prompt = f"""请根据以下参考资料回答问题。

参考资料:
{context}

问题: {question}

要求:
1. 仅基于参考资料中的信息回答
2. 如果参考资料不足以回答问题，请明确说明
3. 使用简洁专业的金融分析语言
4. 引用相关数据时标注来源编号

回答:"""

        t0 = time.time()
        try:
            resp = client.chat.completions.create(
                model=MIMO_MODEL,
                messages=[{"role": "user", "content": user_prompt}],
                temperature=0.3,
                max_tokens=1500,
            )
            msg = resp.choices[0].message
            answer = (msg.content or msg.reasoning_content or "【无响应】").strip()
            response_time = round(time.time() - t0, 2)
        except Exception as e:
            logger.error(f"问答生成失败: {e}")
            answer = f"抱歉，回答生成失败: {str(e)}"
            response_time = round(time.time() - t0, 2)

        return {
            "answer": answer,
            "response_time": response_time,
            "model": "mimo-v2.5-pro",
            "mode": mode_desc,
            "sources": list(sources),
        }


if __name__ == "__main__":
    """单独测试问答生成功能"""
    qa = QAGenerator()
    test_context = [
        {"text": "平安银行2019年实现营业收入1379.58亿元，同比增长18.2%",
         "source_pdf": "平安银行2019年报"},
        {"text": "零售业务净利润占比超过60%，成为收入贡献支柱",
         "source_pdf": "平安银行2019年报"},
    ]
    result = qa.generate("平安银行2019年营收情况如何？", test_context)
    print(f"回答: {result['answer'][:200]}...")
    print(f"耗时: {result['response_time']}s")
