"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-健康咨询 V1.0
知识图谱模块 —— 基于 medical.json（6143 种疾病）的问答引擎
================================================================================
"""
import json, re, logging
from pathlib import Path
from typing import List, Dict, Optional

_log = logging.getLogger("medical_agent.kg")

# medical.json 路径（项目根目录）
_KG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "medical.json"
_diseases: List[Dict] = []  # 内存缓存，所有疾病数据

def _load():
    """懒加载：首次调用时解析 medical.json 到内存"""
    global _diseases
    if _diseases: return  # 已加载则跳过
    if _KG_PATH.exists():
        with open(_KG_PATH, encoding="utf-8") as f:
            for line in f:                    # medical.json 是 JSONL 格式（每行一个 JSON）
                line = line.strip()
                if line:
                    try: _diseases.append(json.loads(line))
                    except: pass
    _log.info("知识图谱加载完成: %d 种疾病", len(_diseases))

# ============================================================
# 工具：字段值可能是 string/list/dict → 统一转 string
# ============================================================
def _to_str(val) -> str:
    if isinstance(val, str): return val
    if isinstance(val, list): return " ".join(str(v) for v in val)
    if isinstance(val, dict): return " ".join(str(v) for v in val.values())
    return str(val) if val else ""

# 口语症状 → 医学术语映射（提高检索准确率）
SYMPTOM_MAP = {
    "肚子疼":"腹痛","胃疼":"胃痛","头疼":"头痛","头晕":"眩晕",
    "发烧":"发热","咳嗽":"咳嗽","拉肚子":"腹泻","呕吐":"呕吐",
    "胸闷":"胸闷","心慌":"心悸","睡不着":"失眠","没力气":"乏力",
    "皮肤痒":"瘙痒","腰疼":"腰痛","腿疼":"腿痛","脖子疼":"颈痛",
}

def _extract_keywords(query: str) -> list:
    """从查询中提取关键词，口语症状自动转医学术语"""
    q = query
    for k, v in SYMPTOM_MAP.items():
        if k in q: q = q.replace(k, v)       # 口语→术语
    # 去停用词后用 2-4 gram 提取关键词
    stop = set('我你需要什么怎么应该可以吗呢的了是有吃药物食物')
    keywords = []
    for n in [4,3,2]:                         # 优先长词匹配
        for i in range(len(q)-n+1):
            gram = q[i:i+n]
            if not stop.intersection(set(gram)): keywords.append(gram)
    return list(set(keywords)) or [q]

# ============================================================
# 核心：检索 + 问答
# ============================================================
def search_disease(query: str, top_k: int = 3) -> List[Dict]:
    """根据症状/关键词搜索相关疾病，返回评分排序的疾病列表"""
    _load()
    keywords = _extract_keywords(query)
    results = []
    for d in _diseases:
        score = 0
        name = d.get("name","")
        if name in query: score += 10          # 精确疾病名匹配
        all_text = _to_str(d.get("intro","")) + " " + _to_str(d.get("symptom",""))
        for kw in keywords:
            if len(kw) >= 2:
                if kw in name: score += 5      # 关键词命中疾病名
                if kw in all_text: score += 2  # 关键词命中描述/症状
        if score > 0: results.append({"score":score, "disease":d})
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]

def get_disease_by_name(name: str) -> Optional[Dict]:
    """通过精确名称获取疾病"""
    _load()
    for d in _diseases:
        if d.get("name") == name: return d
    return None

# 问题类型 → 疾病字段映射
FIELD_MAP = {
    "病原体|cause|致病.*原|病因": ("cause","致病病原体"),
    "传播|传染|get_way": ("get_way","传播途径"),
    "症状|表现|symptom|临床": ("symptom","典型症状"),
    "诊断|检查|血常规|实验室": ("treat_detail","实验室诊断"),
    "治疗|药|抗生素|drug|treat": ("drug","治疗药物"),
    "并发症|neopathy": ("neopathy","并发症"),
    "中医|辨证": ("treat","中医治疗"),
    "预防|隔离|vaccine|prevent": ("prevent","预防措施"),
    "护理|nursing": ("nursing","护理要点"),
    "营养|饮食|吃|食物|can_eat|not_eat": ("not_eat","饮食禁忌"),
    "科室|挂什么科|cure_dept": ("cure_dept","就诊科室"),
    "intro|介绍|概述|简介|什么是": ("intro","疾病概述"),
}

def answer_question(question: str, context_disease: str = "") -> Dict:
    """
    主问答入口：识别疾病 → 提取字段 → 返回答案
    context_disease: 上文讨论的疾病名（用于短追问如"传播途径呢？"）
    """
    _load()
    # Step 1: 从问题中找疾病名，找不到则用上下文疾病
    disease_name = None
    for d in _diseases:
        if d.get("name","") in question:
            disease_name = d["name"]; break
    if not disease_name and context_disease:
        disease_name = context_disease  # 短追问使用上下文
    if not disease_name:
        results = search_disease(question, top_k=1)
        if results: disease_name = results[0]["disease"].get("name","")
        else: return {"found":False, "reply":"未找到相关疾病信息。"}

    disease = get_disease_by_name(disease_name)
    if not disease: return {"found":False, "reply":f"未找到「{disease_name}」的详细信息。"}

    reply = _extract_answer(question, disease)
    return {"found":True, "disease":disease_name, "reply":reply}

def _extract_answer(question: str, disease: Dict) -> str:
    """根据问题类型从疾病数据中提取对应的字段内容"""
    for pattern, (field, label) in FIELD_MAP.items():
        if re.search(pattern, question.lower()):          # 匹配问题类型
            val = disease.get(field)
            if val: return f"【{label}】\n{_to_str(val)}" # 命中！返回对应的字段
    # 默认返回疾病概述
    return f"【{disease['name']}】\n{_to_str(disease.get('intro','暂无'))[:500]}"
