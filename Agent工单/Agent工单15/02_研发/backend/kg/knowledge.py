"""
================================================================================
工单编号：人工智能 NLP-Agent 数字人项目-医疗智能体-健康咨询 V1.1
知识图谱模块 —— 基于 medical.json（6143 种疾病）的问答引擎
双后端支持：Neo4j 图数据库（优先） + Python 内存搜索（回退）
================================================================================
"""
import json, re, logging  # 导入：json（JSON解析）、re（正则表达式）、logging（日志记录）
from pathlib import Path  # 导入Path用于文件路径操作
from typing import List, Dict, Optional, Tuple  # 导入类型提示：List、Dict、Optional、Tuple

_log = logging.getLogger("medical_agent.kg")  # 创建模块级日志记录器，标识为"medical_agent.kg"

# medical.json 路径（项目根目录）  # 注释：知识图谱数据文件位于项目根目录
_KG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "medical.json"  # 通过当前文件路径向上4层定位到项目根目录，拼接medical.json路径
_diseases: List[Dict] = []  # 内存缓存列表，存储所有疾病数据字典，类型标注为字典列表

def _load():  # 懒加载函数：首次调用时解析medical.json到内存
    """懒加载：首次调用时解析 medical.json 到内存"""
    global _diseases  # 声明使用全局变量_diseases
    if _diseases: return  # 如果已加载则跳过（已加载则直接返回）
    if _KG_PATH.exists():  # 检查medical.json文件是否存在
        with open(_KG_PATH, encoding="utf-8") as f:  # 以UTF-8编码打开文件
            for line in f:                    # medical.json 是 JSONL 格式（每行一个 JSON）（逐行读取）
                line = line.strip()  # 去除行首尾的空白字符和换行符
                if line:  # 如果行内容非空
                    try: _diseases.append(json.loads(line))  # 尝试解析JSON行并追加到疾病列表
                    except: pass  # 如果某行解析失败则静默跳过（数据损坏行不影响整体加载）
    _log.info("知识图谱加载完成: %d 种疾病", len(_diseases))  # 记录加载完成的日志：已加载的疾病总数

# ============================================================
# 工具：字段值可能是 string/list/dict → 统一转 string
# ============================================================
def _to_str(val) -> str:  # 工具函数：将任意类型值统一转换为字符串（处理string/list/dict）
    if isinstance(val, str): return val  # 如果已经是字符串则直接返回
    if isinstance(val, list): return " ".join(str(v) for v in val)  # 如果是列表则将元素用空格连接为字符串
    if isinstance(val, dict): return " ".join(str(v) for v in val.values())  # 如果是字典则将值用空格连接
    return str(val) if val else ""  # 其他类型转为字符串，None/False等返回空字符串

# 口语症状 → 医学术语映射（提高检索准确率）  # 注释：建立常用口语表达到标准医学术语的映射表
SYMPTOM_MAP = {  # 症状口语-术语映射字典
    "肚子疼":"腹痛","胃疼":"胃痛","头疼":"头痛","头晕":"眩晕",  # 消化道症状和头部症状映射
    "发烧":"发热","咳嗽":"咳嗽","拉肚子":"腹泻","呕吐":"呕吐",  # 全身症状和消化道症状映射
    "胸闷":"胸闷","心慌":"心悸","睡不着":"失眠","没力气":"乏力",  # 心肺和神经系统症状映射
    "皮肤痒":"瘙痒","腰疼":"腰痛","腿疼":"腿痛","脖子疼":"颈痛",  # 皮肤和骨骼肌肉症状映射
}

def _extract_keywords(query: str) -> list:  # 关键词提取函数：从查询中提取关键词，口语症状自动转医学术语
    """从查询中提取关键词，口语症状自动转医学术语"""
    q = query  # 复制查询字符串用于处理
    for k, v in SYMPTOM_MAP.items():  # 遍历口语-术语映射表
        if k in q: q = q.replace(k, v)       # 口语→术语（如果查询中包含口语词则替换为标准术语）
    # 去停用词后用 2-4 gram 提取关键词  # 注释：使用n-gram方法提取关键词
    stop = set('我你需要什么怎么应该可以吗呢的了是有吃药物食物')  # 中文停用词集合（常见无意义高频词）
    keywords = []  # 初始化关键词列表
    for n in [4,3,2]:                         # 优先长词匹配（从4-gram到2-gram，长词匹配精度更高）
        for i in range(len(q)-n+1):  # 遍历字符串，生成所有长度为n的子串
            gram = q[i:i+n]  # 截取长度为n的子串
            if not stop.intersection(set(gram)): keywords.append(gram)  # 如果子串不包含停用词则作为关键词保留
    return list(set(keywords)) or [q]  # 去重返回关键词列表，如果无关键词则返回原始查询

# ============================================================
# 核心：检索 + 问答
# ============================================================
def search_disease(query: str, top_k: int = 3) -> List[Dict]:  # 疾病搜索函数：根据症状/关键词搜索相关疾病
    """根据症状/关键词搜索相关疾病，返回评分排序的疾病列表"""
    _load()  # 确保疾病数据已加载到内存（懒加载）
    keywords = _extract_keywords(query)  # 从查询中提取关键词
    results = []  # 初始化搜索结果列表
    for d in _diseases:  # 遍历所有疾病数据
        score = 0  # 初始化当前疾病的匹配得分
        name = d.get("name","")  # 获取疾病名称
        if name in query: score += 10          # 精确疾病名匹配（查询中直接包含疾病名，加10分）
        all_text = _to_str(d.get("intro","")) + " " + _to_str(d.get("symptom",""))  # 拼接疾病概述和症状文本用于关键词匹配
        for kw in keywords:  # 遍历所有提取的关键词
            if len(kw) >= 2:  # 只处理长度至少为2的关键词（过滤无意义的单字）
                if kw in name: score += 5      # 关键词命中疾病名（加5分，权重高）
                if kw in all_text: score += 2  # 关键词命中描述/症状（加2分，权重较低）
        if score > 0: results.append({"score":score, "disease":d})  # 如果得分大于0则加入候选结果
    results.sort(key=lambda x: x["score"], reverse=True)  # 按评分降序排序（得分高的在前）
    return results[:top_k]  # 返回前top_k个结果

def get_disease_by_name(name: str) -> Optional[Dict]:  # 按精确名称获取疾病完整信息
    """通过精确名称获取疾病"""
    _load()  # 确保数据已加载
    for d in _diseases:  # 遍历所有疾病
        if d.get("name") == name: return d  # 如果名称完全匹配则返回该疾病字典
    return None  # 未找到则返回None

# 问题类型 → 疾病字段映射  # 注释：根据用户问题的关键词确定应查询疾病的哪个字段
# 注意: drug 字段存的是中成药，抗生素/治疗方案在 treat_detail 里  # 注释：字段存储内容说明
FIELD_MAP = {  # 正则模式到(字段名, 中文标签)的映射字典
    "病原体|cause|致病.*原|病因": ("cause","致病病原体"),  # 病因相关→cause字段
    "传播|传染|get_way": ("get_way","传播途径"),  # 传播相关→get_way字段
    "症状|表现|symptom|临床": ("symptom","典型症状"),  # 症状相关→symptom字段
    "诊断|检查|血常规|实验室|检验": ("treat_detail","实验室诊断"),  # 诊断检查相关→treat_detail字段
    "并发症|neopathy": ("neopathy","并发症"),  # 并发症相关→neopathy字段
    "治疗|药|抗生素|首选.*药|吃什么药|用什么药|drug": ("treat_detail","治疗方案"),  # 治疗药物相关→treat_detail字段（注：包含抗生素等）
    "中医|辨证|方剂|方药": ("treat","中医治疗"),  # 中医相关→treat字段
    "预防|隔离|vaccine|prevent": ("prevent","预防措施"),  # 预防相关→prevent字段
    "护理|nursing": ("nursing","护理要点"),  # 护理相关→nursing字段
    "营养|饮食|吃|食物|can_eat|not_eat|忌口|禁忌": ("not_eat","饮食禁忌"),  # 饮食营养相关→not_eat字段
    "科室|挂什么科|cure_dept": ("cure_dept","就诊科室"),  # 就诊科室相关→cure_dept字段
    "intro|介绍|概述|简介|什么是": ("intro","疾病概述"),  # 疾病介绍相关→intro字段
}

def _is_meaningless(val) -> bool:  # 检测知识库返回的数据是否有实质医学内容
    """检测 KB 返回的数据是否有实质内容"""
    s = _to_str(val).strip()  # 将值转为字符串并去除首尾空白
    if len(s) < 10: return True  # 如果长度不足10个字符则认为内容不足
    # 泛泛词汇，没有具体医学数据  # 注释：以下词汇是通用描述，不含具体医学信息
    generic = {'药物治疗','支持性治疗','手术治疗','综合治疗','对症治疗',  # 通用治疗方法名称集合
               '一般治疗','保守治疗','康复治疗','物理治疗'}  # 通用治疗分类名称
    if s in generic or all(w in generic for w in s.replace(' ','').split(';')):  # 如果值完全在通用词汇集合中，或用分号分隔的各项都是通用词汇
        return True  # 无实质内容
    return False  # 有实质内容

def answer_question(question: str, context_disease: str = "") -> Dict:  # 主问答入口函数：接收用户问题和上文疾病名
    """
    主问答入口：优先 Neo4j Cypher 查询 → 回退内存关键词搜索 → LLM 增强回答

    context_disease: 上文讨论的疾病名（用于短追问如"传播途径呢？"）

    返回格式:
      {"found": bool, "disease": str, "reply": str,
       "backend": "neo4j"|"memory",
       "cypher": str|None,   # Neo4j 模式下生成的 Cypher 查询
       "neo4j_result": list|None}  # Neo4j 查询原始结果
    """
    _load()  # 确保疾病数据已加载到内存

    # Step 1: 识别疾病名  # 注释：从用户问题中识别目标疾病名称
    disease_name = None  # 初始化疾病名称为None
    for d in _diseases:  # 遍历所有疾病（6143种）
        if d.get("name", "") in question:  # 检查疾病名称是否直接出现在用户问题中
            disease_name = d["name"]; break  # 如果找到则设置疾病名并跳出循环
    if not disease_name and context_disease:  # 如果问题中未找到疾病名，但有上下文疾病名（如追问场景）
        disease_name = context_disease  # 使用上下文中讨论的疾病名
    if not disease_name:  # 如果仍未找到疾病名
        results = search_disease(question, top_k=1)  # 通过关键词搜索匹配最相关的疾病（取top1）
        if results: disease_name = results[0]["disease"].get("name", "")  # 如果搜索结果非空则取第一个疾病的名称
        else: return {"found": False, "reply": "未找到相关疾病信息。",  # 无匹配疾病，返回未找到结果
                      "backend": "none", "cypher": None, "neo4j_result": None}  # 后端标记为none

    # Step 2: 优先尝试 Neo4j 图数据库查询  # 注释：图数据库查询优先级高于内存搜索
    try:  # 异常捕获：Neo4j连接可能失败
        from kg.neo4j_client import get_neo4j_client  # 延迟导入Neo4j客户端（避免依赖问题影响模块加载）
        neo4j = get_neo4j_client()  # 获取Neo4j客户端单例

        # 生成并执行 Cypher 查询  # 注释：两步：生成Cypher语句→执行查询
        cypher, intent, params = neo4j.generate_cypher(question, disease_name)  # 根据问题和疾病名生成Cypher查询语句、意图类型和参数
        neo4j_result = neo4j.execute_cypher(cypher, params)  # 在Neo4j中执行Cypher查询，获取原始结果

        if neo4j_result:  # 如果Neo4j查询返回了有效结果
            # Neo4j 查询成功，用结果构建回答  # 注释：格式化图数据库结果为自然语言回答
            reply = _format_neo4j_result(intent, neo4j_result, disease_name)  # 将图查询结果格式化为中文回答
            return {  # 返回格式化的回答结果字典
                "found": True, "disease": disease_name, "reply": reply,  # 标记找到疾病、疾病名和回答文本
                "backend": "neo4j" if neo4j.is_connected else "neo4j-offline",  # 根据是否真实连接标记后端类型
                "cypher": cypher, "neo4j_result": neo4j_result,  # 返回生成的Cypher语句和原始查询结果
                "intent": intent  # 返回意图识别结果
            }
    except Exception as e:  # 捕获Neo4j查询异常
        _log.warning("Neo4j 查询失败，回退内存搜索: %s", e)  # 记录警告日志，准备降级到内存搜索

    # Step 3: 回退到内存关键词搜索（原有逻辑）  # 注释：Neo4j不可用时回退到基于内存的关键词匹配
    disease = get_disease_by_name(disease_name)  # 通过精确名称获取疾病完整信息
    if not disease:  # 如果未找到疾病详细信息
        return {"found": False, "reply": f"未找到「{disease_name}」的详细信息。",  # 返回未找到信息的结果
                "backend": "memory", "cypher": None, "neo4j_result": None}  # 后端标记为memory

    reply = _extract_answer(question, disease)  # 根据问题类型从疾病数据中提取对应字段内容
    return {"found": True, "disease": disease_name, "reply": reply,  # 返回找到疾病的结果
            "backend": "memory", "cypher": None, "neo4j_result": None}  # 后端标记为memory

def _extract_answer(question: str, disease: Dict) -> str:  # 根据问题类型从疾病数据中提取对应字段的回答
    """根据问题类型从疾病数据中提取对应的字段内容"""
    for pattern, (field, label) in FIELD_MAP.items():  # 遍历问题类型映射表（正则模式→字段名和中文标签）
        if re.search(pattern, question.lower()):          # 匹配问题类型（使用正则搜索，不区分大小写）
            val = disease.get(field)  # 从疾病字典中获取对应字段的值
            if val and not _is_meaningless(val):  # 如果字段存在且有实质内容
                return f"【{label}】\n{_to_str(val)}"     # 命中！返回格式化的问题：中文标签+字段内容
            elif val and _is_meaningless(val):  # 如果字段存在但内容无实质意义
                return (f"【{label}】\n⚠ 知识库中此疾病的{label}数据不足，"  # 返回数据不足警告
                        f"请基于医学教科书标准给出精确答案。\n现有数据：{_to_str(val)}")  # 附带现有数据供参考
    # 默认返回疾病概述  # 注释：所有模式都未匹配时返回疾病概述作为兜底
    return f"【{disease['name']}】\n{_to_str(disease.get('intro','暂无'))[:500]}"  # 返回疾病名称和概述（截断至500字符）


def _format_neo4j_result(intent: str, result: List[Dict], disease_name: str) -> str:  # 将Neo4j查询结果格式化为人类可读的中文回答
    """
    将 Neo4j/Cypher 查询结果格式化为人类可读的中文回答

    这是工单要求的 "Agent 分析思路" 的一部分:
      生成知识图谱查询语句 cypher → 链接 neo4j 执行 → 获取结果 → 格式化输出
    """
    if not result:  # 如果查询结果为空
        return f"【{disease_name}】\n未找到相关信息。"  # 返回未找到信息的提示

    labels = {  # 意图类型到中文标签的映射字典
        "pathogen": "致病病原体",  # 病原体相关信息
        "transmission": "传播途径",  # 传播途径信息
        "symptom": "典型症状",  # 症状信息
        "diagnosis": "实验室诊断",  # 实验室诊断信息
        "treatment_drug": "治疗方案/药物",  # 治疗药物方案
        "complication": "并发症",  # 并发症信息
        "tcm_treatment": "中医治疗",  # 中医药治疗
        "prevention": "预防/隔离措施",  # 预防隔离措施
        "nursing": "护理要点",  # 护理要点
        "diet": "饮食指导",  # 饮食指导
        "department": "就诊科室",  # 就诊科室
        "overview": "疾病概述",  # 疾病概述
    }
    label = labels.get(intent, "查询结果")  # 根据意图类型获取中文标签，未匹配则默认为"查询结果"

    r = result[0]  # 取第一条记录（Neo4j查询通常返回第一条最相关）
    lines = [f"【{disease_name} - {label}】"]  # 初始化输出行列表：首行为疾病名和查询类别

    if intent == "symptom":  # 如果查询意图是症状
        symptoms = r.get("symptoms", [])  # 获取症状列表
        lines.append("、".join(symptoms) if symptoms else "暂无详细症状数据")  # 用顿号拼接症状列表，无数据则显示提示
    elif intent == "treatment_drug":  # 如果查询意图是治疗药物方案
        drugs = r.get("drugs", [])  # 获取药物列表
        if drugs: lines.append(f"常用药物：{'、'.join(drugs)}")  # 如果有药物数据则列出常用药物
        info = r.get("treatment_info", "")  # 获取治疗方案信息
        if info: lines.append(f"治疗方案：{info}")  # 如果有治疗方案则追加显示
    elif intent == "complication":  # 如果查询意图是并发症
        comps = r.get("complications", [])  # 获取并发症列表
        lines.append("、".join(comps) if comps else "暂无详细并发症数据")  # 拼接并发症或显示无数据提示
    elif intent == "diet":  # 如果查询意图是饮食指导
        can = r.get("can_eat", [])  # 获取宜吃食物列表
        not_eat = r.get("not_eat", [])  # 获取忌吃食物列表
        if can: lines.append(f"✅ 宜吃：{'、'.join(can)}")  # 如果有宜吃数据则显示（带绿色对勾）
        if not_eat: lines.append(f"❌ 忌吃：{'、'.join(not_eat)}")  # 如果有忌吃数据则显示（带红色叉号）
    elif intent == "prevention":  # 如果查询意图是预防措施
        measures = r.get("prevention_measures", [])  # 获取预防措施列表
        lines.append("、".join(measures) if measures else "暂无详细预防措施数据")  # 拼接或显示无数据
    elif intent == "nursing":  # 如果查询意图是护理要点
        points = r.get("nursing_points", [])  # 获取护理要点列表
        lines.append("、".join(points) if points else "暂无详细护理数据")  # 拼接或显示无数据
    elif intent in ("overview",):  # 如果查询意图是疾病概述
        lines.append(r.get("overview", "暂无概述")[:500])  # 显示概述内容（截断至500字符）
    else:  # 其他未明确匹配的意图类型
        # 通用：取第一个非 disease 字段的值  # 注释：兜底策略
        for k, v in r.items():  # 遍历结果中的所有键值对
            if k != "disease" and v:  # 排除disease字段（已在标题显示），找第一个非空字段
                val = "、".join(v) if isinstance(v, list) else str(v)  # 列表用顿号拼接，其他类型转字符串
                lines.append(f"{k}: {val}")  # 追加字段名和值的行
                break  # 只取第一个非disease字段后退出

    return "\n".join(lines)  # 将所有行用换行符连接并返回完整回答
