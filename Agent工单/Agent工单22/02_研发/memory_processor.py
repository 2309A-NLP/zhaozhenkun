#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==============================================================================
02_研发 — 记忆处理器
==============================================================================
整合信息提取、记忆存储、摘要生成、相关性检索四大功能。
是连接 LLM + mem0 的核心编排模块。
模型: deepseek-v4-flash (LLM) + mem0 REST API (记忆存储)
==============================================================================
"""

import json  # JSON 序列化
import time  # 性能监控计时
from typing import Optional, Dict, Any, List, Tuple  # 类型注解

# 导入自建模块
from llm_client import DeepSeekClient  # DeepSeek LLM 客户端
from memory_client import MemoryClient  # mem0 API 客户端
from extractor import InformationExtractor  # 信息提取器

# 导入设计模块和优化配置
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DESIGN_DIR = os.path.join(BASE_DIR, "..", "01_设计")
OPTIMIZE_DIR = os.path.join(BASE_DIR, "..", "05_优化")
for import_path in (DESIGN_DIR, OPTIMIZE_DIR):
    if import_path not in sys.path:
        sys.path.insert(0, import_path)

from prompts import get_prompt  # 提示词注册表
from schemas import DOMAIN_CONFIG, ALL_SCHEMAS  # 领域配置与 schema
from config import retrieval_config, monitor, deduplicate_memories  # 优化配置


class MemoryProcessor:
    """记忆处理器 — 整合提取/存储/摘要/检索/带记忆对话的核心引擎。"""

    def __init__(self, llm_client: DeepSeekClient = None,
                 memory_client: MemoryClient = None):
        """初始化：传入 LLM 和记忆客户端实例，或自动创建。"""
        self.llm = llm_client or DeepSeekClient()
        self.memory = memory_client or MemoryClient()
        self.extractor = InformationExtractor(self.llm)

        # 内存缓存：存储每个用户的记忆摘要，减少重复 API 调用
        self._summary_cache: Dict[str, str] = {}

    def _get_agent_id(self, domain: str) -> str:
        """获取领域对应的 agent_id，用于 mem0 领域隔离。"""
        config = DOMAIN_CONFIG.get(domain, {})
        return config.get("agent_id", f"{domain}_agent")

    def _get_domain_schema(self, domain: str) -> Dict[str, Any]:
        """获取领域 schema。"""
        return ALL_SCHEMAS.get(domain, {})

    @staticmethod
    def _coerce_field_value(expected_type: str, value: Any) -> Any:
        """按 schema 类型做最小强制转换。"""
        if value is None:
            return None

        if expected_type == "string":
            if isinstance(value, str):
                return value.strip() or None
            if isinstance(value, (int, float, bool)):
                return str(value)
            if isinstance(value, list):
                joined = "、".join(str(item) for item in value if item not in (None, ""))
                return joined or None
            if isinstance(value, dict):
                return json.dumps(value, ensure_ascii=False)

        if expected_type == "list":
            if isinstance(value, list):
                return [item for item in value if item not in (None, "", [], {})]
            if isinstance(value, str):
                return [value.strip()] if value.strip() else []
            if isinstance(value, dict):
                return [value] if value else []
            return [value]

        if expected_type == "dict":
            if isinstance(value, dict):
                return value
            if isinstance(value, str) and value.strip():
                return {"description": value.strip()}
            return {}

        return value

    @staticmethod
    def _matches_type(expected_type: str, value: Any) -> bool:
        """检查值是否匹配 schema 类型。"""
        if value is None:
            return True
        if expected_type == "string":
            return isinstance(value, str)
        if expected_type == "list":
            return isinstance(value, list)
        if expected_type == "dict":
            return isinstance(value, dict)
        return True

    def _normalize_medical_fields(self, extracted: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
        """将医疗提取结果映射到医疗 schema。"""
        diagnosis_history = extracted.get("diagnosis_history") or []
        new_diagnosis = extracted.get("new_diagnosis")
        if new_diagnosis:
            diagnosis_history.append({"diagnosis": new_diagnosis})

        medication_records = extracted.get("medication_records") or []
        for item in extracted.get("medications_changed", []) or []:
            if isinstance(item, dict):
                medication_records.append({
                    "drug": item.get("drug", ""),
                    "action": item.get("action", ""),
                    "detail": item.get("detail", ""),
                })

        follow_up_notes = extracted.get("follow_up_notes") or []
        follow_up_needed = extracted.get("follow_up_needed")
        if isinstance(follow_up_needed, dict) and follow_up_needed.get("required"):
            follow_up_notes.append({
                "suggested_date": follow_up_needed.get("suggested_date"),
                "note": "建议复诊",
            })

        health_goals = extracted.get("health_goals") or extracted.get("health_goals_mentioned")
        allergies = extracted.get("allergies") or extracted.get("allergy_updates")

        return {
            "patient_id": extracted.get("patient_id") or user_id,
            "chief_complaint": extracted.get("chief_complaint"),
            "diagnosis_history": diagnosis_history,
            "medication_records": medication_records,
            "follow_up_notes": follow_up_notes,
            "health_goals": health_goals,
            "allergies": allergies,
            "vital_signs": extracted.get("vital_signs"),
        }

    def _normalize_tourism_fields(self, extracted: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
        """将文旅提取结果映射到文旅 schema。"""
        companion_info = extracted.get("companion_info")
        if not companion_info and extracted.get("travel_companions"):
            companion_info = {"description": extracted.get("travel_companions")}

        seasonal_preference = extracted.get("seasonal_preference")
        if not seasonal_preference and extracted.get("seasonal_pref"):
            seasonal_preference = [extracted.get("seasonal_pref")]

        return {
            "user_id": extracted.get("user_id") or user_id,
            "preferred_destinations": extracted.get("preferred_destinations") or extracted.get("destination_interests"),
            "activity_preferences": extracted.get("activity_preferences") or extracted.get("activity_likes"),
            "travel_history": extracted.get("travel_history"),
            "budget_preference": extracted.get("budget_preference") or extracted.get("budget_level"),
            "companion_info": companion_info,
            "seasonal_preference": seasonal_preference,
            "dietary_constraints": extracted.get("dietary_constraints") or extracted.get("dietary_needs"),
        }

    def _normalize_education_fields(self, extracted: Dict[str, Any], user_id: Optional[str]) -> Dict[str, Any]:
        """将教育提取结果映射到教育 schema。"""
        topics_covered = extracted.get("topics_covered") or []
        if isinstance(topics_covered, str):
            topics_covered = [topics_covered]

        course_progress = extracted.get("course_progress")
        if not course_progress and topics_covered:
            course_progress = {
                topic: {"status": "discussed", "correct_answers": extracted.get("correct_answers", 0)}
                for topic in topics_covered if isinstance(topic, str) and topic.strip()
            }

        interaction_history = extracted.get("interaction_history") or []
        if topics_covered or extracted.get("correct_answers") or extracted.get("incorrect_topics"):
            interaction_history.append({
                "topics": topics_covered,
                "correct_answers": extracted.get("correct_answers", 0),
                "incorrect_topics": extracted.get("incorrect_topics") or [],
                "attention_observations": extracted.get("attention_observations"),
            })

        return {
            "student_id": extracted.get("student_id") or user_id,
            "course_progress": course_progress,
            "knowledge_graph": extracted.get("knowledge_graph"),
            "weak_points": extracted.get("weak_points") or extracted.get("incorrect_topics"),
            "learning_style": extracted.get("learning_style") or extracted.get("learning_style_clues"),
            "interaction_history": interaction_history,
            "study_goals": extracted.get("study_goals") or extracted.get("study_goals_mentioned"),
            "attention_span": extracted.get("attention_span") or extracted.get("attention_observations"),
        }

    def normalize_extracted_info(self, domain: str, extracted: Dict[str, Any],
                                 user_id: Optional[str] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """按领域 schema 归一化提取结果，并返回软校验信息。"""
        schema = self._get_domain_schema(domain)
        fields = schema.get("fields", {})

        normalizers = {
            "medical": self._normalize_medical_fields,
            "tourism": self._normalize_tourism_fields,
            "education": self._normalize_education_fields,
        }
        candidate = normalizers.get(domain, lambda data, uid: data)(extracted or {}, user_id)

        normalized = {}
        invalid_fields = []
        for field_name, field_info in fields.items():
            if field_name not in candidate:
                continue

            expected_type = field_info.get("type", "string")
            coerced = self._coerce_field_value(expected_type, candidate.get(field_name))
            if not self._matches_type(expected_type, coerced):
                invalid_fields.append(field_name)
                continue

            if coerced not in (None, "", [], {}):
                normalized[field_name] = coerced

        missing_required = [
            field_name for field_name, field_info in fields.items()
            if field_info.get("required") and field_name not in normalized
        ]
        partial = bool(missing_required or invalid_fields or extracted.get("_error"))

        validation = {
            "missing_required": missing_required,
            "invalid_fields": invalid_fields,
            "normalized_fields": list(normalized.keys()),
            "partial": partial,
        }
        return normalized, validation

    def _get_retention_days(self, domain: str, normalized: Dict[str, Any]) -> int:
        """根据领域和核心字段给出保留天数。"""
        retention = self._get_domain_schema(domain).get("retention", {})
        default_days = retention.get("default_days", 365)

        if domain == "medical" and normalized.get("allergies") and retention.get("critical_days"):
            return retention.get("critical_days", default_days)
        if domain == "tourism" and normalized.get("travel_history") and retention.get("history_days"):
            return retention.get("history_days", default_days)
        if domain == "education" and normalized.get("weak_points") and retention.get("weak_points_days"):
            return retention.get("weak_points_days", default_days)
        return default_days

    def _build_memory_metadata(self, domain: str, normalized: Dict[str, Any],
                               validation: Dict[str, Any], metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """构建写入 mem0 的增强元数据。"""
        merged = dict(metadata or {})
        merged["memory_system"] = {
            "domain": domain,
            "schema_version": "v1",
            "normalized_fields": validation.get("normalized_fields", []),
            "missing_required": validation.get("missing_required", []),
            "invalid_fields": validation.get("invalid_fields", []),
            "partial": validation.get("partial", False),
            "retention_days": self._get_retention_days(domain, normalized),
        }
        return merged

    @staticmethod
    def messages_have_memory_context(messages: List[Dict[str, Any]]) -> bool:
        """粗略判断消息中是否已经注入历史记忆。"""
        markers = (
            "【该用户的历史记忆",
            "历史记忆（共",
            "以下是与当前对话相关的历史信息",
        )
        for message in messages or []:
            if message.get("role") != "system":
                continue
            content = message.get("content", "")
            if any(marker in content for marker in markers):
                return True
        return False

    @staticmethod
    def _extract_latest_user_message(messages: List[Dict[str, Any]]) -> str:
        """从消息列表中提取最近一条用户消息。"""
        for message in reversed(messages or []):
            if message.get("role") == "user":
                return str(message.get("content", "")).strip()
        return ""

    @staticmethod
    def _domain_chat_base_prompt(domain: str) -> str:
        """获取领域基础 system prompt。"""
        prompts = {
            "medical": "你是一个专业、体贴的医疗助手。请根据患者的历史病历和本次描述，给出专业的诊疗建议。如果缺少关键信息，可以主动追问。",
            "tourism": "你是一个贴心的旅行规划师。请根据用户的历史旅行偏好和本次需求，推荐个性化的旅行方案。",
            "education": "你是一个耐心的辅导老师。请根据学生的学习历史、薄弱点和本次提问，提供有针对性的解答和鼓励。",
        }
        return prompts.get(domain, prompts["medical"])

    @staticmethod
    def _normalize_query_terms(values: Any) -> List[str]:
        """规范化检索关键词列表。"""
        if not values:
            return []
        if isinstance(values, str):
            values = [values]

        normalized = []
        seen = set()
        for value in values:
            text = str(value).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            normalized.append(text)
        return normalized

    def _analyze_retrieval_query(self, domain: str, query: str) -> Dict[str, Any]:
        """用 LLM 将当前问题扩展为更适合检索的关键词。"""
        retrieval_prompt = (
            f"{get_prompt(domain, 'retrieve')}\n\n"
            "补充要求：请直接输出 JSON，并尽量同时给出中文和英文关键词。"
            "如有需要，可额外返回 bilingual_keywords、english_keywords、priority_terms 字段。"
        )
        try:
            raw = self.llm.retrieve_analyze(retrieval_prompt, query, temperature=0.0)
            parsed = InformationExtractor._try_parse_json(raw)
            return parsed if isinstance(parsed, dict) else {}
        except Exception as e:
            print(f"[MemoryProcessor] 检索查询分析失败: {e}")
            return {}

    @staticmethod
    def _memory_result_key(item: Dict[str, Any]) -> str:
        """为检索结果生成稳定去重键。"""
        memory_id = str(item.get("id") or "").strip()
        if memory_id:
            return f"id:{memory_id}"

        memory_text = str(item.get("memory") or item.get("text") or "").strip()
        if memory_text:
            return f"text:{memory_text}"

        return json.dumps(item, ensure_ascii=False, sort_keys=True)

    def _build_retrieval_queries(self, domain: str, query: str) -> List[str]:
        """构建跨语言、多焦点的检索查询集合。"""
        queries = [query]
        plan = self._analyze_retrieval_query(domain, query)
        extra_terms = []

        for field_name in (
            "keywords",
            "focus_areas",
            "preference_layers",
            "bilingual_keywords",
            "english_keywords",
            "priority_terms",
        ):
            extra_terms.extend(self._normalize_query_terms(plan.get(field_name)))

        extra_terms.extend(
            self._normalize_query_terms(DOMAIN_CONFIG.get(domain, {}).get("memory_tags", []))
        )

        unique_terms = []
        seen = {query}
        for term in extra_terms:
            if term in seen:
                continue
            seen.add(term)
            unique_terms.append(term)

        if unique_terms:
            queries.append(" ".join([query] + unique_terms))
            queries.extend(unique_terms)

        return queries[:8]

    def _append_memory_context(self, base_prompt: str, context_prompt: str) -> str:
        """把历史记忆追加到现有 system prompt。"""
        if not context_prompt:
            return base_prompt
        if self.messages_have_memory_context([{"role": "system", "content": base_prompt}]):
            return base_prompt
        return (
            f"{base_prompt}\n\n"
            f"【该用户的历史记忆，请在回复中参考这些信息】\n{context_prompt}\n\n"
            f"请根据以上信息和当前对话，给出连贯、个性化的回复。"
        )

    def build_chat_messages_with_memory(self, domain: str, user_id: str,
                                        messages: List[Dict[str, Any]],
                                        top_k: Optional[int] = None,
                                        memory_query: Optional[str] = None,
                                        inject_memory: bool = True,
                                        memory_injected: bool = False) -> Tuple[List[Dict[str, Any]], str, List[Dict[str, Any]], str]:
        """构造带长期记忆上下文的消息列表。"""
        prepared = [dict(message) for message in (messages or [])]
        if not prepared:
            return prepared, "", [], ""

        if not inject_memory or memory_injected or self.messages_have_memory_context(prepared):
            return prepared, "", [], self._extract_latest_user_message(prepared)

        query = memory_query or self._extract_latest_user_message(prepared)
        if not query:
            return prepared, "", [], ""

        memories = self.retrieve_context(domain, user_id, query, top_k=top_k)
        context_prompt = self.build_context_prompt(memories, domain)

        if prepared and prepared[0].get("role") == "system":
            prepared[0]["content"] = self._append_memory_context(
                prepared[0].get("content", ""),
                context_prompt,
            )
        else:
            prepared.insert(0, {
                "role": "system",
                "content": self._append_memory_context(
                    self._domain_chat_base_prompt(domain),
                    context_prompt,
                )
            })
        return prepared, context_prompt, memories, query

    def chat_with_memory(self, domain: str, user_id: str,
                         messages: List[Dict[str, Any]],
                         top_k: Optional[int] = None,
                         memory_query: Optional[str] = None,
                         inject_memory: bool = True,
                         memory_injected: bool = False,
                         temperature: float = 0.7,
                         max_tokens: int = 2000) -> Dict[str, Any]:
        """执行带记忆注入的对话。"""
        prepared, context_prompt, memories, query = self.build_chat_messages_with_memory(
            domain=domain,
            user_id=user_id,
            messages=messages,
            top_k=top_k,
            memory_query=memory_query,
            inject_memory=inject_memory,
            memory_injected=memory_injected,
        )
        reply = self.llm.chat(prepared, temperature=temperature, max_tokens=max_tokens)
        return {
            "reply": reply,
            "messages": prepared,
            "memory_context": context_prompt,
            "used_memory_count": len(memories),
            "memory_query": query,
        }

    def process_conversation(self, domain: str, user_id: str,
                             conversation: str, run_id: str = None,
                             metadata: Dict = None) -> Dict[str, Any]:
        """处理对话：提取信息 → 生成摘要 → 存储到 mem0（核心写入流程）。"""
        result = {"success": False, "domain": domain, "user_id": user_id}

        try:
            raw_extracted = self.extractor.extract(domain, conversation)
            normalized, validation = self.normalize_extracted_info(domain, raw_extracted, user_id=user_id)
            result["raw_extracted"] = raw_extracted
            result["extracted"] = normalized
            result["validation"] = validation

            history_context = self._summary_cache.get(user_id, "无历史记录")
            summary_prompt = get_prompt(domain, "summarize")
            summary = self.llm.summarize(
                system_prompt=summary_prompt,
                history=history_context,
                conversation=conversation,
                temperature=0.3,
            )
            result["summary"] = summary
            self._summary_cache[user_id] = summary

            storage_text = self._build_storage_text(normalized, summary, conversation)
            agent_id = self._get_agent_id(domain)
            memory_metadata = self._build_memory_metadata(domain, normalized, validation, metadata)
            mem_result = self.memory.create(
                text=storage_text,
                user_id=user_id,
                agent_id=agent_id,
                run_id=run_id,
                metadata=memory_metadata,
            )
            result["memory_result"] = mem_result
            result["metadata"] = memory_metadata
            result["success"] = True

        except Exception as e:
            result["error"] = str(e)
            print(f"[MemoryProcessor] 处理对话失败: {e}")

        return result

    @staticmethod
    def _build_storage_text(extracted: Dict, summary: str, conversation: str) -> str:
        """构建存入 mem0 的文本（提取结果+摘要+原文截断500字）。"""
        parts = []

        clean_extracted = {k: v for k, v in extracted.items() if not k.startswith("_")}
        if clean_extracted:
            parts.append("【关键信息】")
            parts.append(json.dumps(clean_extracted, ensure_ascii=False, indent=2))

        if summary:
            parts.append("【对话摘要】")
            parts.append(summary)

        parts.append("【对话原文】")
        parts.append(conversation[:500])
        return "\n".join(parts)

    def retrieve_context(self, domain: str, user_id: str, query: str,
                         top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """检索与当前查询相关的历史记忆，在新对话开始时调用。"""
        agent_id = self._get_agent_id(domain)
        effective_top_k = top_k if top_k is not None else retrieval_config.default_top_k
        effective_top_k = max(1, min(effective_top_k, retrieval_config.max_top_k))
        start_time = time.time()

        try:
            aggregated = {}
            for search_query in self._build_retrieval_queries(domain, query):
                search_result = self.memory.search(
                    query=search_query,
                    user_id=user_id,
                    agent_id=agent_id,
                )
                for item in search_result.get("results", []):
                    key = self._memory_result_key(item)
                    score = item.get("score") or 0.0
                    existing = aggregated.get(key)
                    if existing is None or score > (existing.get("score") or 0.0):
                        merged = dict(item)
                        merged["matched_queries"] = list(existing.get("matched_queries", [])) if existing else []
                        if search_query not in merged["matched_queries"]:
                            merged["matched_queries"].append(search_query)
                        aggregated[key] = merged
                    elif search_query not in existing.get("matched_queries", []):
                        existing.setdefault("matched_queries", []).append(search_query)

            all_results = sorted(
                aggregated.values(),
                key=lambda item: item.get("score") or 0.0,
                reverse=True,
            )

            filtered_results = []
            for item in all_results:
                score = item.get("score")
                if score is None or score >= retrieval_config.min_score_threshold:
                    filtered_results.append(item)

            if retrieval_config.dedup_enabled and filtered_results:
                filtered_results = list(
                    deduplicate_memories.__wrapped__(
                        tuple(filtered_results),
                        threshold=retrieval_config.dedup_threshold,
                    )
                )

            results = filtered_results[:effective_top_k]
            monitor.record_request((time.time() - start_time) * 1000, success=True, cache_hit=False)
            return results
        except Exception as e:
            monitor.record_request((time.time() - start_time) * 1000, success=False, cache_hit=False)
            print(f"[MemoryProcessor] 检索记忆失败: {e}")
            return []

    def get_all_memories(self, domain: str, user_id: str) -> List[Dict[str, Any]]:
        """获取指定用户在该领域的所有记忆。"""
        agent_id = self._get_agent_id(domain)
        try:
            result = self.memory.list(user_id=user_id, agent_id=agent_id)
            return result.get("results", [])
        except Exception as e:
            print(f"[MemoryProcessor] 获取记忆列表失败: {e}")
            return []

    def reset_user_memory(self, domain: str, user_id: str) -> bool:
        """清空指定用户在该领域的所有记忆（危险操作，仅用于测试）。"""
        agent_id = self._get_agent_id(domain)
        try:
            self.memory.reset(user_id=user_id, agent_id=agent_id)
            self._summary_cache.pop(user_id, None)
            return True
        except Exception as e:
            print(f"[MemoryProcessor] 重置记忆失败: {e}")
            return False

    def build_context_prompt(self, memories: List[Dict], domain: str) -> str:
        """将记忆列表转化为自然语言上下文，可注入智能体的 system prompt。"""
        if not memories:
            return "（无相关历史记忆）"

        config = DOMAIN_CONFIG.get(domain, {})
        domain_name = config.get("domain_name", domain)

        lines = [f"## {domain_name}领域历史记忆（共{len(memories)}条）"]
        lines.append("以下是与当前对话相关的历史信息，请参考这些信息提供个性化服务：\n")

        for i, mem in enumerate(memories, 1):
            memory_text = mem.get("memory", "")
            score = mem.get("score")
            score_str = f" [相关度: {score:.2f}]" if score is not None else ""
            lines.append(f"{i}.{score_str} {memory_text}")

        lines.append("\n请根据以上历史记忆，为用户提供连贯、个性化的回复。")
        return "\n".join(lines)


# ============================================================
# 模块自检
# ============================================================
if __name__ == "__main__":
    proc = MemoryProcessor()
    print("记忆处理器已初始化")

    if not proc.memory.health():
        print("警告: mem0 服务未启动！请先运行: cd ~/mem0-deploy && docker compose up -d")
        exit(1)

    test_domain = "tourism"
    test_user = "test_traveler_001"
    test_conv = """
    用户：我想找个地方去旅游，有什么推荐吗？
    助手：您喜欢什么类型的旅行呢？海边还是山？
    用户：我比较喜欢海边，不喜欢太拥挤的地方。预算大概5000左右。
    助手：明白了，那我推荐三亚或者北海，都是不错的海滨城市。
    用户：三亚不错！我之前去过一次，很喜欢那边的海鲜。
    """

    print(f"\n--- 测试: {test_domain} 记忆写入 ---")
    result = proc.process_conversation(test_domain, test_user, test_conv)
    print(f"  成功: {result['success']}")
    if result.get("summary"):
        print(f"  摘要: {result['summary'][:100]}...")

    print(f"\n--- 测试: {test_domain} 记忆检索 ---")
    memories = proc.retrieve_context(test_domain, test_user, "海边度假推荐")
    print(f"  检索到 {len(memories)} 条记忆")

    context = proc.build_context_prompt(memories, test_domain)
    print(f"\n--- 上下文提示词 ---")
    print(context[:500])

    print(f"\n--- 清理测试数据 ---")
    proc.reset_user_memory(test_domain, test_user)
    print("  清理完成")
