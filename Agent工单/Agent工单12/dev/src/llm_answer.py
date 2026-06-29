"""
src/llm_answer.py - LLM 答案生成模块
功能: 根据用户原始问题和知识图谱查询结果，调用 LLM 生成自然语言答案。
      使用医疗专业提示词约束，确保回答准确、专业、易懂。
      验收标准: 答案准确率 ≥ 80%，响应时间 < 500ms
工单编号: 人工智能NLP-Agent数字人项目-医疗智能体-健康咨询
"""
import json
import logging
import time

from openai import OpenAI  # OpenAI 兼容客户端

from src.config import LLMConfig  # LLM 配置
from src.models import QueryIntent  # 查询意图

logger = logging.getLogger(__name__)


# ============================================================
# 答案生成系统提示词
# ============================================================

_ANSWER_SYSTEM_PROMPT = """你是一个专业的医疗健康咨询助手。你的任务是根据知识图谱检索结果，
用通俗易懂的语言回答用户的健康咨询问题。

请严格遵守以下规则:
1. 基于提供的图谱数据回答，不要编造信息
2. 如果图谱数据不足以回答问题，请诚实地说明
3. 使用简洁清晰的中文，避免过于专业的术语
4. 答案结构清晰，先给结论再解释
5. 在合适的情况下给出就医建议
6. 始终提醒: "本回答仅供参考，具体诊疗请咨询专业医生"
7. 回答控制在300字以内
8. 如果图谱数据中包含"治疗详情"(treat_detail)字段，请优先从中提取精准信息（如具体药名、剂量、疗程等）"""


class LLMAnswerGenerator:
    """
    基于 LLM 的自然语言答案生成器。

    将图谱查询结果和原始问题组合为 prompt，
    调用 LLM 生成专业、易懂的健康咨询回答。
    """

    def __init__(self, config: LLMConfig):
        """
        初始化答案生成器。

        参数:
            config: LLM 配置
        """
        self.config = config  # LLM 配置
        # OpenAI 客户端延迟初始化（API Key 为空时不创建）
        self._client = None

    def _get_client(self):
        """延迟初始化 OpenAI 客户端（仅在 API Key 有效时创建）。"""
        if self._client is None and self.config.api_key:
            self._client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.api_base,
            )
        return self._client

    def generate(
        self,
        query: str,  # 原始用户问题
        intent: QueryIntent,  # 查询意图
        kg_result: list,  # 图谱查询结果
        fallback_data: str = "",  # 降级查询数据（Neo4j不可用时）
    ) -> str:
        """
        生成自然语言答案。

        将图谱数据格式化为上下文，调用 LLM 生成回答。

        参数:
            query: 用户原始问题
            intent: 解析后的查询意图
            kg_result: Neo4j 图谱查询结果
            fallback_data: 本地降级查询数据

        返回:
            LLM 生成的自然语言答案
        """
        start = time.time()  # 计时开始
        # ---- 步骤1: 构建图谱上下文 ----
        context = self._build_context(kg_result, fallback_data)
        # ---- 步骤2: 构建用户提示词 ----
        user_prompt = (
            f"用户问题: {query}\n"
            f"查询类别: {intent.category}\n"
            f"目标疾病: {intent.disease}\n"
            f"知识图谱检索结果:\n{context}\n\n"
            f"请根据以上信息回答用户的问题。"
        )
        # ---- 步骤3: 调用 LLM ----
        try:
            client = self._get_client()
            if client is None:
                logger.warning("API Key 未设置，使用模板答案")
                return self._build_simple_answer(query, intent, context)
            response = client.chat.completions.create(
                model=self.config.model,  # 模型名称
                messages=[
                    {"role": "system", "content": _ANSWER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=self.config.max_tokens,  # 最大token
                temperature=self.config.temperature,  # 低温度
                stream=False,  # 非流式
            )
            answer = response.choices[0].message.content.strip()
            elapsed = (time.time() - start) * 1000  # 耗时毫秒
            logger.info(f"答案生成: {len(answer)} 字 ({elapsed:.0f}ms)")
            return answer  # 返回生成答案
        except Exception as e:
            # API 调用失败 → 构建简单答案
            logger.error(f"LLM 答案生成失败: {e}")
            return self._build_simple_answer(query, intent, context)

    def _build_context(self, kg_result: list, fallback_data: str) -> str:
        """
        将图谱查询结果格式化为 LLM 可理解的上下文字符串。

        参数:
            kg_result: 图谱查询结果列表
            fallback_data: 本地降级查询数据

        返回:
            格式化的上下文字符串
        """
        # 优先使用图谱结果
        if kg_result and len(kg_result) > 0:
            # 将结果字典列表转为格式化的 JSON 字符串
            result_str = json.dumps(kg_result, ensure_ascii=False, indent=2)
            # 限制上下文长度（避免超出 token 限制，但保留足够信息）
            if len(result_str) > 3000:
                result_str = result_str[:3000] + "...(已截断)"
            return result_str
        # 图谱无结果时使用降级数据
        if fallback_data:
            return fallback_data[:2000]
        # 全部无数据
        return "（未在知识图谱中找到相关数据）"

    def _build_simple_answer(
        self,
        query: str,  # 原始问题
        intent: QueryIntent,  # 查询意图
        context: str,  # 图谱上下文
    ) -> str:
        """
        当 LLM 不可用时，基于图谱数据构建简单答案。

        这是一个容错机制，不依赖 LLM API。

        参数:
            query: 用户问题
            intent: 查询意图
            context: 图谱数据

        返回:
            简单的格式化答案
        """
        category = intent.category  # 查询类别
        disease = intent.disease  # 疾病名称
        # 如果上下文包含有效数据（非空、非"未找到"）
        if context and "未在知识图谱中" not in context:
            # 构建模板答案
            return (
                f"关于「{disease}」的{category}信息如下:\n\n"
                f"{context[:2000]}\n\n"
                f"⚠️ 本回答仅供参考，具体诊疗请咨询专业医生。"
            )
        # 完全无数据时的回复
        return (
            f"抱歉，关于「{disease}」的{category}信息，"
            f"我在知识图谱中暂时没有找到相关数据。\n"
            f"建议您: 1) 核实疾病名称是否正确; "
            f"2) 咨询专业医生获取准确信息。"
        )
