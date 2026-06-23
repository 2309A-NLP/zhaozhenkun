"""
evaluator.py - RAG工单7 核心评估模块（LLM智能评分版）
工单编号: 人工智能NLP-RAG-功能测试及评估
功能: 使用DeepSeek LLM对RAG回答进行智能评分，
  评估维度：相关性、完整性、准确性、流畅性
      基于MiMo API进行LLM智能评分
"""

import logging, json, time, re
from collections import Counter
from config import OUTPUT_DIR, MIMO_API_KEY, MIMO_BASE_URL, EVAL_MODEL, LOG_FMT, LOG_DATEFMT

logging.basicConfig(format=LOG_FMT, datefmt=LOG_DATEFMT, level=logging.INFO)
logger = logging.getLogger("evaluator")
_llm_cache = {}


def tokenize(text):
    """中文分词，用于关键词匹配（参考指标）"""
    tokens = set()
    for phrase in re.findall(r'[\u4e00-\u9fff]+', text):
        for i in range(len(phrase) - 1):
            tokens.add(phrase[i:i+2])
        tokens.update(re.findall(r'[\u4e00-\u9fff]{2,}', phrase))
    tokens.update(re.findall(r'\b[a-zA-Z]+\b', text))
    tokens.update(re.findall(r'\d+', text))
    return tokens


def get_suggestion(issue_type):
    sug = {
        "回答不准确": "增加Top-K或使用Reranker重排",
        "部分准确": "细粒度分块或增加上下文长度",
        "信息缺失": "增大chunk_size避免碎片化",
        "信息不完整": "尝试多轮检索或多源融合",
        "检索相关性不足": "使用混合检索(向量+全文)",
        "表达差异大": "调整DeepSeek temperature值",
    }
    return sug.get(issue_type, "无特定建议")


def llm_score(question, reference, answer):
    """MiMo评估RAG回答4维评分(0-10)，结构化文本解析"""
    key = f"{question[:50]}|{reference[:50]}|{answer[:50]}"
    if key in _llm_cache:
        return _llm_cache[key]

    prompt = f"""评分0-10，标准：8-10优秀 6-7良好 4-5一般 1-3差。逐行输出：
相关性：X   (回答是否紧扣问题)
完整性：X   (是否覆盖关键信息)
准确性：X   (信息是否准确)
流畅性：X   (表达是否通顺)
综合：X     (总体质量)
问题：简述不足

【问题】{question}
【参考答案】{reference[:600]}
【RAG回答】{answer[:600]}"""

    default = {"relevance":5,"completeness":5,"accuracy":5,"fluency":5,"overall":5,"issues":["LLM评分失败"]}
    try:
        from openai import OpenAI
        r = OpenAI(api_key=MIMO_API_KEY, base_url=MIMO_BASE_URL).chat.completions.create(
            model=EVAL_MODEL, messages=[{"role":"user","content":prompt}], temperature=0.1, max_tokens=300)
        msg = r.choices[0].message
        raw = (msg.content or msg.reasoning_content or "").strip()
        # 用正则从结构化文本中提取评分
        def _extract(label, text):
            import re
            m = re.search(rf'{label}[：:]\s*(\d+(?:\.\d+)?)', text)
            return float(m.group(1)) if m else 5
        rel = _extract('相关性', raw)
        com = _extract('完整性', raw)
        acc = _extract('准确性', raw)
        flu = _extract('流畅性', raw)
        ovr = _extract('综合', raw)
        issues = []
        m = re.search(r'问题[：:]\s*(.+)', raw, re.DOTALL)
        if m:
            issues.append(m.group(1).strip()[:50])
        result = {"relevance":rel,"completeness":com,"accuracy":acc,"fluency":flu,"overall":ovr,"issues":issues}
        _llm_cache[key] = result
        return result
    except Exception as e:
        logger.warning(f"LLM评分失败: {e}")
    _llm_cache[key] = default
    return default


class Evaluator:
    """RAG检索质量评估器（LLM智能评分版）"""
    def __init__(self):
        self.results = []
        self.summary = {}

    def evaluate_single(self, q_data, qa_result):
        """评估单个问答对，关键词匹配+LLM智能评分"""
        ref, ans = q_data.get("reference_answer", ""), qa_result.get("answer", "")
        ref_tok, ans_tok = tokenize(ref), tokenize(ans)
        hits = ref_tok & ans_tok
        prec = len(hits) / len(ans_tok) if ans_tok else 0
        rec = len(hits) / len(ref_tok) if ref_tok else 0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0
        sim = __import__("difflib").SequenceMatcher(None, ref, ans).ratio()
        top_score = qa_result.get("source_chunks", [{}])[0].get("score", 0) if qa_result.get("source_chunks") else 0
        sources = list(set(c.get("source_pdf", "") for c in qa_result.get("source_chunks", [])))

        # LLM智能评分
        llm = llm_score(q_data["question"], ref, ans)

        result = {
            "question_id": q_data["id"], "question": q_data["question"],
            "reference_answer": ref, "generated_answer": ans[:500],
            "keyword_f1": round(f1, 4), "keyword_accuracy": round(prec, 4), "keyword_recall": round(rec, 4), "similarity": round(sim, 4),
            "top_score": round(top_score, 4),
            "response_time": qa_result.get("response_time", 0),
            "source_count": len(sources), "source_pdfs": sources,
            "llm_scores": llm,
        }

        # LLM驱动的问题分析
        ov = llm.get("overall", 5)
        issues = []
        if ov < 4: issues.append({"type":"回答质量较差","detail":f"LLM评分{ov}/10","severity":"严重"})
        elif ov < 6: issues.append({"type":"部分准确","detail":f"LLM评分{ov}/10","severity":"中等"})
        elif ov < 8: issues.append({"type":"基本合格","detail":f"LLM评分{ov}/10","severity":"正常"})
        else: issues.append({"type":"回答质量优秀","detail":f"LLM评分{ov}/10","severity":"正常"})
        for d,l in [("completeness","完整性"),("accuracy","准确性")]:
            if llm.get(d,5)<5: issues.append({"type":f"{l}不足","detail":f"LLM评分{llm[d]}/10","severity":"中等"})
        if top_score<0.5: issues.append({"type":"检索相关性不足","detail":f"最高分{top_score:.3f}","severity":"中等"})
        else: issues.append({"type":"检索质量良好","detail":f"最高分{top_score:.3f}","severity":"正常"})
        for iss_text in llm.get("issues",[]):
            if iss_text.strip(): issues.append({"type":"LLM反馈","detail":iss_text,"severity":"轻微"})

        result["analysis"] = issues
        return result

    def evaluate_all(self, questions, qa_results):
        """批量评估所有问答对"""
        self.results = [self.evaluate_single(q, qa_results[i]) for i, q in enumerate(questions) if i < len(qa_results)]
        self._compute_summary()
        return {"item_results": self.results, "summary": self.summary}

    def _compute_summary(self):
        if not self.results:
            self.summary = {"error": "无评估数据"}; return
        f1s = [r["keyword_f1"] for r in self.results]
        overs = [r["llm_scores"]["overall"] for r in self.results]
        rels = [r["llm_scores"]["relevance"] for r in self.results]
        comps = [r["llm_scores"]["completeness"] for r in self.results]
        accs = [r["llm_scores"]["accuracy"] for r in self.results]
        times = [r["response_time"] for r in self.results]
        all_issues = [iss["type"] for r in self.results for iss in r.get("analysis", [])]

        self.summary = {
            "total_questions": len(self.results),
            "avg_keyword_f1": round(sum(f1s) / len(f1s), 4),
            "avg_llm_overall": round(sum(overs) / len(overs), 2),
            "avg_llm_relevance": round(sum(rels) / len(rels), 2),
            "avg_llm_completeness": round(sum(comps) / len(comps), 2),
            "avg_llm_accuracy": round(sum(accs) / len(accs), 2),
            "avg_response_time": round(sum(times) / len(times), 2),
            "high_quality_ratio": round(sum(1 for r in self.results if r["llm_scores"]["overall"]>=7) / len(self.results), 2),
            "issue_statistics": dict(Counter(all_issues).most_common()),
            "typical_problems": [{"issue": t, "count": c, "suggestion": get_suggestion(t)} for t, c in Counter(all_issues).most_common(5)],
        }

    def save_results(self):
        json_path = OUTPUT_DIR / "evaluation_results.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({"item_results": self.results, "summary": self.summary}, f, ensure_ascii=False, indent=2)
        html_path = OUTPUT_DIR / "evaluation_report.html"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(self._build_html())
        logger.info(f"报告已保存")

    def _build_html(self):
        s = self.summary
        rows = "".join(
            f'<div class="item"><h3>Q{r["question_id"]}: {r["question"][:60]}</h3>'
            f'<p><span class="score {"high" if r["llm_scores"]["overall"]>=7 else "medium" if r["llm_scores"]["overall"]>=5 else "low"}">'
            f'LLM={r["llm_scores"]["overall"]}/10</span>'
            f'F1={r["keyword_f1"]:.3f} | 相关{r["llm_scores"]["relevance"]}/10 | 完整{r["llm_scores"]["completeness"]}/10'
            f'<details><summary>详情</summary><p><b>参考答案:</b></p><pre>{r["reference_answer"][:300]}</pre>'
            f'<p><b>RAG回答:</b></p><pre>{r["generated_answer"][:300]}</pre>'
            + "".join(f'<div class="issue {"ok" if i["severity"]=="正常" else ""}">{"✅" if i["severity"]=="正常" else "⚠"} {i["type"]}: {i["detail"]}</div>' for i in r.get("analysis",[]))
            + '</details></p></div>'
            for r in self.results
        )
        issues_row = "".join(f'<li><b>{tp["issue"]}</b> ({tp["count"]}次): {tp["suggestion"]}</li>' for tp in s.get("typical_problems", []))
        tp = __import__("pathlib").Path(__file__).parent / "templates" / "report_template.html"
        tpl = tp.read_text(encoding="utf-8")
        for k, v in [("avg_llm_overall", s.get("avg_llm_overall",0)),("avg_llm_relevance", s.get("avg_llm_relevance",0)),
            ("avg_llm_completeness", s.get("avg_llm_completeness",0)),("avg_llm_accuracy", s.get("avg_llm_accuracy",0)),
            ("avg_keyword_f1", f'{s.get("avg_keyword_f1",0):.3f}'),("high_quality_ratio", f'{s.get("high_quality_ratio",0)*100:.0f}%'),
            ("issues_row", issues_row),("rows", rows),("gen_time", __import__("time").strftime("%Y-%m-%d %H:%M:%S"))]:
            tpl = tpl.replace("{{" + k + "}}", str(v))
        return tpl
