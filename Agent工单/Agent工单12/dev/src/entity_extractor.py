"""
src/entity_extractor.py - 实体与意图抽取模块
功能: 基于 LLM 从用户自然语言问题中抽取医疗实体和查询意图。
      使用 few-shot prompting 让 LLM 将自由文本问题解析为结构化的
      (疾病名, 查询类别, 关键词) 三元组，作为后续 Cypher 生成的输入。
      验收标准: 准确识别用户 query，精度 ≥ 80%
工单编号: 人工智能NLP-Agent数字人项目-医疗智能体-健康咨询
"""
import json
import logging
import time
from typing import Optional

from openai import OpenAI  # OpenAI 兼容客户端（对接 DeepSeek）

from src.models import QueryIntent  # 查询意图数据模型
from src.config import LLMConfig  # LLM 配置

logger = logging.getLogger(__name__)


# ============================================================
# Few-Shot 示例 — 教 LLM 如何解析医疗问题
# ============================================================

# 查询类别枚举（对应知识图谱中的关系类型）
# 病原体=CAUSE, 传播=GET_WAY, 症状=SYMPTOM, 诊断=DIAGNOSIS,
# 药物=DRUG, 并发症=COMPLICATION, 治疗=TREATMENT,
# 预防=PREVENTION, 护理=NURSING, 饮食=DIET, 科室=DEPT,
# 费用=COST, 周期=PERIOD, 概率=PROB, 概述=INTRO

_EXTRACTION_EXAMPLES = [
    {
        "query": "百日咳的致病病原体是什么？",
        "output": {"disease": "百日咳", "category": "病原体",
                    "keywords": ["病原体", "致病菌"]}
    },
    {
        "query": "百日咳主要通过什么途径传播？",
        "output": {"disease": "百日咳", "category": "传播途径",
                    "keywords": ["传播", "途径"]}
    },
    {
        "query": "百日咳最具特征性的临床表现是什么？",
        "output": {"disease": "百日咳", "category": "症状",
                    "keywords": ["临床表现", "特征", "症状"]}
    },
    {
        "query": "百日咳患者的血常规检查会呈现什么特征？",
        "output": {"disease": "百日咳", "category": "诊断",
                    "keywords": ["血常规", "检查", "特征"]}
    },
    {
        "query": "百日咳西医治疗首选的抗生素是什么？",
        "output": {"disease": "百日咳", "category": "药物",
                    "keywords": ["抗生素", "西医", "首选"]}
    },
    {
        "query": "百日咳最常见的严重并发症是什么？",
        "output": {"disease": "百日咳", "category": "并发症",
                    "keywords": ["并发症", "严重"]}
    },
    {
        "query": "中医治疗痉咳期百日咳的主方是什么？",
        "output": {"disease": "百日咳", "category": "治疗",
                    "keywords": ["中医", "痉咳期", "主方"]}
    },
    {
        "query": "百日咳患者的隔离期应持续多久？",
        "output": {"disease": "百日咳", "category": "预防",
                    "keywords": ["隔离期", "隔离"]}
    },
    {
        "query": "护理百日咳患儿时需特别注意防范什么紧急情况？",
        "output": {"disease": "百日咳", "category": "护理",
                    "keywords": ["护理", "紧急情况", "防范"]}
    },
    {
        "query": "百日咳患者应避免食用哪类食物？",
        "output": {"disease": "百日咳", "category": "饮食",
                    "keywords": ["避免", "食物", "食用"]}
    },
]


# ============================================================
# LLM 实体抽取器
# ============================================================

class EntityExtractor:
    """
    基于 LLM 的医疗实体与查询意图抽取器。

    使用 few-shot prompting 让 LLM 将自然语言问题
    解析为结构化的查询意图。
    """

    def __init__(self, config: LLMConfig):
        """
        初始化抽取器。

        参数:
            config: LLM 配置（API Key、模型、温度等）
        """
        self.config = config  # LLM 配置
        # OpenAI 客户端延迟初始化（API Key 为空时不创建）
        self._client = None
        # 构建系统提示词（包含 few-shot 示例）
        self._system_prompt = self._build_system_prompt()

    def _get_client(self):
        """延迟初始化 OpenAI 客户端（仅在 API Key 有效时创建）。"""
        if self._client is None and self.config.api_key:
            self._client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.api_base,
            )
        return self._client

    def _build_system_prompt(self) -> str:
        """
        构建包含 few-shot 示例的系统提示词。

        提示词明确告诉 LLM 输出格式和类别枚举，
        确保 LLM 返回结构化的 JSON。

        返回:
            完整的系统提示词字符串
        """
        # 将示例格式化为提示词中的模板
        examples_str = json.dumps(_EXTRACTION_EXAMPLES,
                                  ensure_ascii=False, indent=2)
        # 构建完整的系统提示词
        return f"""你是一个医疗信息抽取专家。你的任务是从用户的健康咨询问题中抽取以下信息:
1. disease: 用户询问的疾病名称
2. category: 查询类别，必须从以下枚举中选择:
   - 病原体 (问致病菌/病原体)
   - 传播途径 (问怎么传播/传染)
   - 症状 (问临床表现/症状)
   - 诊断 (问检查/诊断)
   - 药物 (问用什么药/抗生素)
   - 并发症 (问并发症/后遗症)
   - 治疗 (问治疗方法/主方)
   - 预防 (问预防/隔离)
   - 护理 (问护理/注意事项)
   - 饮食 (问吃什么/避免什么)
   - 科室 (问看哪个科)
   - 概述 (问疾病简介/是什么)
   - 费用 (问治疗费用)
   - 周期 (问治疗时长)
   - 概率 (问治愈率)
3. keywords: 问题中的关键术语列表

你必须只返回 JSON 格式，不要输出其他内容。

以下是参考示例:
{examples_str}"""

    def extract(self, query: str) -> QueryIntent:
        """
        从用户问题中提取查询意图。

        调用 LLM 进行实体抽取，返回结构化的 QueryIntent。

        参数:
            query: 用户自然语言问题

        返回:
            解析后的 QueryIntent 对象
        """
        start = time.time()  # 计时开始

        # 如果 LLM 未配置 API Key，使用规则降级
        if not self.config.api_key:
            logger.warning("API Key 未设置，使用规则抽取")
            return self._rule_based_extract(query)

        try:
            # 调用 LLM 进行意图抽取
            client = self._get_client()
            if client is None:
                logger.warning("API Key 未设置，使用规则抽取")
                return self._rule_based_extract(query)
            response = client.chat.completions.create(
                model=self.config.model,  # 模型名称
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": query},
                ],
                max_tokens=self.config.max_tokens,  # 最大生成token
                temperature=self.config.temperature,  # 低温度确保确定性
                stream=False,  # 非流式
            )
            # 提取 LLM 返回的 JSON 文本
            raw = response.choices[0].message.content.strip()
            # 清理可能的 markdown 代码块标记
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1]  # 去掉 ```json
                if raw.endswith("```"):
                    raw = raw[:-3]  # 去掉结尾 ```
            # 解析 JSON
            data = json.loads(raw)
            # 处理 LLM 返回数组而非对象的情况
            if isinstance(data, list):
                data = data[0] if len(data) > 0 else {}
            if not isinstance(data, dict):
                raise ValueError(f"LLM 返回非预期类型: {type(data)}")
            elapsed = (time.time() - start) * 1000  # 耗时毫秒
            logger.info(f"实体抽取: {data.get('disease','')} "
                        f"/{data.get('category','')} ({elapsed:.0f}ms)")
            # 返回结构化的 QueryIntent
            return QueryIntent(
                disease=data.get("disease", ""),
                category=data.get("category", ""),
                raw_query=query,
                keywords=data.get("keywords", []),
            )
        except json.JSONDecodeError as e:
            # JSON 解析失败 → 降级到规则抽取
            logger.warning(f"LLM 返回非 JSON: {raw[:100]}...")
            return self._rule_based_extract(query)
        except Exception as e:
            # API 调用失败 → 降级到规则抽取
            logger.error(f"LLM 调用失败: {e}")
            return self._rule_based_extract(query)

    def _rule_based_extract(self, query: str) -> QueryIntent:
        """
        基于规则的降级抽取（不依赖 LLM）。

        使用关键词匹配从问题中识别疾病名和查询类别。
        用于 LLM 不可用时的容错处理。

        参数:
            query: 用户问题

        返回:
            QueryIntent 对象
        """
        # ---- 步骤1: 尝试从 query 中直接提取疾病名 ----
        disease = ""
        # 常见疾病名列表（从 medical.json 中提取的关键疾病）
        common_diseases = [
            "百日咳", "苯中毒", "大叶性肺炎", "成人呼吸窘迫综合征",
            "糖尿病", "高血压", "冠心病", "哮喘", "肺炎",
            "支气管炎", "肺结核", "肝炎", "胃炎", "阑尾炎",
            "肺癌", "胃癌", "乳腺癌", "白血病", "脑梗塞",
        ]
        # 按长度降序匹配（优先匹配长名称）
        for name in sorted(common_diseases, key=len, reverse=True):
            if name in query:
                disease = name
                break

        # ---- 步骤2: 关键词匹配推断查询类别（得分制，选最佳匹配）- ---
        category = "概述"  # 默认类别
        best_score = 0
        # 类别关键词映射表
        category_keywords = {
            "病原体": ["病原体", "致病菌", "病原菌", "细菌", "病毒", "什么引起的"],
            "传播途径": ["传播", "传染", "感染途径", "飞沫", "怎么得"],
            "症状": ["症状", "表现", "特征", "临床", "什么样"],
            "诊断": ["诊断", "检查", "血常规", "CT", "检测"],
            "药物": ["药", "抗生素", "用药", "吃什么药", "治疗药物", "首选"],
            "并发症": ["并发症", "后遗症", "并发"],
            "治疗": ["治疗", "治法", "主方", "方案", "怎么治", "中医"],
            "预防": ["预防", "隔离", "疫苗", "防护"],
            "护理": ["护理", "照顾", "防范", "紧急", "窒息"],
            "饮食": ["吃", "食", "忌口", "避免", "饮食", "食物"],
            "科室": ["科室", "挂什么科", "看什么科", "哪个科"],
            "费用": ["费用", "多少钱", "价格", "花费"],
            "周期": ["周期", "多久", "多长时间", "疗程"],
            "概率": ["概率", "治愈率", "能治好吗"],
        }
        # 遍历关键词映射，按得分选最佳类别
        for cat, keywords in category_keywords.items():
            score = sum(1 for kw in keywords if kw in query)
            if score > best_score:
                best_score = score
                category = cat

        # ---- 步骤3: 提取关键词 ----
        keywords = [disease] if disease else []
        for kw in ["检查", "治疗", "预防", "护理", "症状", "药物"]:
            if kw in query:
                keywords.append(kw)

        logger.info(f"规则抽取: {disease}/{category} (LLM不可用)")
        # 返回 QueryIntent
        return QueryIntent(
            disease=disease,  # 识别到的疾病名
            category=category,  # 推断的查询类别
            raw_query=query,  # 原始问题
            keywords=keywords,  # 关键词
        )
