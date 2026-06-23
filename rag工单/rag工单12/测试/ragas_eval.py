"""
RAGAS 标准评估模块
功能：集成 RAGAS 官方库指标，对 RAG/LightRAG 的问答结果做专业评估
完成：RAGAS faithfulness/answer_relevancy/context_precision/context_recall + LLM 适配
"""
import logging

logger = logging.getLogger(__name__)
import sys, os
# 将项目根目录加入路径，支持从任意子目录导入其他模块
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _sub in ["设计", "研发", "测试", "部署"]:
    _p = os.path.join(_root, _sub)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import json      # 解析评估结果
import numpy as np  # 数值计算
import torch     # GPU 检测

import config    # 全局配置（API密钥、模型路径等）


def _build_ragas_dataset(questions, answers, contexts):
    """
    构建 RAGAS 格式的评估数据集
    参数：
        questions: [{"id": int, "question": str}, ...] 问题列表
        answers:   [{"answer": str, "mode": str}, ...]   回答列表
        contexts:  [str, ...]                            检索上下文字符串列表
    返回：
        dict 包含 question/answer/contexts 三个 key
    """
    dataset = {
        "question": [],   # 问题文本列表
        "answer": [],     # 回答文本列表
        "contexts": [],   # 上下文列表（每个元素是字符串列表）
    }
    for i in range(len(questions)):
        dataset["question"].append(questions[i]["question"])
        dataset["answer"].append(answers[i]["answer"])
        # RAGAS 要求 contexts 是字符串列表（每段上下文一个元素）
        ctx_list = [contexts[i]] if isinstance(contexts[i], str) else contexts[i]
        dataset["contexts"].append(ctx_list)
    return dataset


def _init_ragas_llm():
    """
    初始化 RAGAS 评估用的 LLM 实例
    通过 LangChain ChatOpenAI 适配小米 MiMo API（兼容 OpenAI 格式）
    返回：ChatOpenAI 实例
    """
    from langchain_openai import ChatOpenAI  # LangChain 的 OpenAI 适配器
    return ChatOpenAI(
        model=config.LLM_MODEL,              # MiMo 模型名
        openai_api_key=config.API_KEY,        # API 密钥
        openai_api_base=config.BASE_URL,      # MiMo API 端点
        temperature=0.1,                      # 低温度保证评估一致性
        max_tokens=2048,                      # 评估输出不需要太长
        timeout=config.LLM_TIMEOUT,           # 请求超时
    )


def _init_ragas_embeddings():
    """
    初始化 RAGAS 评估用的嵌入模型
    将本地 BGE-M3 封装为 LangChain 兼容的 Embeddings 接口
    返回：BGEEmbeddings 实例（LangChain Embeddings 子类）
    """
    from langchain_openai import OpenAIEmbeddings  # LangChain 基类
    from sentence_transformers import SentenceTransformer  # BGE-M3 加载器

    class BGEEmbeddings(OpenAIEmbeddings):
        """
        BGE-M3 本地模型 → LangChain Embeddings 接口适配器
        支持 embed_documents（批量）和 embed_query（单条）
        """
        def __init__(self):
            """初始化适配器（父类参数不实际使用）"""
            super().__init__(
                model="bge-m3",                # 模型标识（仅标记）
                openai_api_key="dummy",         # 占位 API key
                openai_api_base="http://localhost:0",  # 占位端点
            )
            self._model = None  # 延迟加载 BGE-M3 模型

        @property
        def model_instance(self):
            """延迟加载并返回 BGE-M3 模型（进程级单例）"""
            if self._model is None:
                self._model = SentenceTransformer(
                    config.BGE_MODEL_PATH,        # 本地 BGE-M3 路径
                    device="cuda",                # GPU 加速
                    trust_remote_code=True        # 允许自定义模型代码
                )
                if torch.cuda.is_available():
                    self._model.half()            # FP16 半精度，显存减半
            return self._model

        def embed_documents(self, texts):
            """
            批量编码文档列表为向量
            参数：texts - 文本列表
            返回：向量列表（每行是一个文本的嵌入）
            """
            return self.model_instance.encode(
                texts,
                normalize_embeddings=True,        # 归一化方便余弦相似度
                show_progress_bar=False           # 评估时不需要进度条
            ).tolist()

        def embed_query(self, text):
            """
            编码单个查询文本为向量
            参数：text - 查询文本
            返回：一维向量列表
            """
            return self.model_instance.encode(
                [text],
                normalize_embeddings=True,
                show_progress_bar=False
            )[0].tolist()

    return BGEEmbeddings()  # 返回适配器实例


def evaluate_with_ragas(questions, rag_answers, lightrag_answers,
                        rag_contexts, lightrag_contexts) -> dict:
    """
    使用 RAGAS 标准指标对比评估 RAG 和 LightRAG
    指标说明：
      - faithfulness: 回答是否忠于检索上下文（反幻觉）
      - answer_relevancy: 回答与问题的相关程度
      - context_precision: 检索到的上下文是否精准（信号噪声比）
      - context_recall: 检索到的上下文是否覆盖全面
    参数：
        questions:        问题列表 [{"id":, "question":}, ...]
        rag_answers:      RAG 模式的回答列表
        lightrag_answers: LightRAG 模式的回答列表
        rag_contexts:     RAG 模式的上下文字符串列表
        lightrag_contexts: LightRAG 模式的上下文字符串列表
    返回：
        {"rag": {...指标...}, "lightrag": {...}, "comparison": {...}}
    """
    print("\n📊 RAGAS 标准评估...")

    try:
        from ragas import evaluate                # RAGAS 主评估函数
        from ragas.metrics import (               # RAGAS 标准指标
            faithfulness,       # 忠实度：回答是否基于上下文
            answer_relevancy,   # 回答相关性：回答是否切题
            context_precision,  # 上下文精准度：检索是否精准
            context_recall,     # 上下文召回率：检索是否全面
        )
        from datasets import Dataset  # HuggingFace datasets 格式



        # 初始化 RAGAS 依赖的 LLM 和 Embeddings
        ragas_llm = _init_ragas_llm()
        ragas_embeddings = _init_ragas_embeddings()

        # 定义使用的指标列表
        metrics = [faithfulness, answer_relevancy, context_precision, context_recall]

        results = {}  # 存储两种模式的评估结果
        for mode, answers, contexts in [
            ("rag", rag_answers, rag_contexts),
            ("lightrag", lightrag_answers, lightrag_contexts)
        ]:
            print(f"  评估 {mode.upper()} 模式...")
            # 构建 RAGAS 数据集
            ds_dict = _build_ragas_dataset(questions, answers, contexts)
            ds = Dataset.from_dict(ds_dict)

            try:
                # 调用 RAGAS 评估
                score = evaluate(
                    ds,
                    metrics=metrics,
                    llm=ragas_llm,
                    embeddings=ragas_embeddings,
                )
                # 提取各指标分数（RAGAS 返回的是 per-question 平均 float）
                results[mode] = {
                    "faithfulness": round(float(score.get("faithfulness", 0) or 0), 3),
                    "answer_relevancy": round(float(score.get("answer_relevancy", 0) or 0), 3),
                    "context_precision": round(float(score.get("context_precision", 0) or 0), 3),
                    "context_recall": round(float(score.get("context_recall", 0) or 0), 3),
                }
                # 计算综合分（四项取平均）
                vals = [v for v in results[mode].values() if v > 0]
                results[mode]["overall"] = round(sum(vals) / len(vals), 3) if vals else 0
                print(f"    ✅ {mode}: overall={results[mode]['overall']:.3f}")
            except Exception as e:
                print(f"    ⚠️ RAGAS {mode} 评估失败: {e}")
                results[mode] = {
                    "faithfulness": 0, "answer_relevancy": 0,
                    "context_precision": 0, "context_recall": 0,
                    "overall": 0, "error": str(e)
                }

        # 计算 RAG vs LightRAG 对比
        rag_o = results.get("rag", {}).get("overall", 0)
        lr_o = results.get("lightrag", {}).get("overall", 0)
        results["comparison"] = {
            "rag_overall": rag_o,
            "lightrag_overall": lr_o,
            "improvement": round(lr_o - rag_o, 3)  # 正值表示 LightRAG 优于 RAG
        }
        return results

    except ImportError as e:
        print(f"  ⚠️ RAGAS 库不可用: {e}")
        return {"error": f"RAGAS import error: {e}"}
    except Exception as e:
        print(f"  ⚠️ RAGAS 评估异常: {e}")
        return {"error": str(e)}
