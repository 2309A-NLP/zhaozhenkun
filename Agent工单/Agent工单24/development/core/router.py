"""该文件用于识别业务领域并为问题挑选合适的技能集合。"""

# 导入正则模块，用于识别天数与关键词模式。
import re


# 定义文旅领域关键词集合，用于快速判断问题主题。
TOURISM_KEYWORDS = ("旅游", "景点", "路线", "行程", "攻略", "酒店", "门票", "天气", "文旅")
# 定义教育领域关键词集合，用于快速判断问题主题。
EDUCATION_KEYWORDS = ("教育", "学习", "作业", "题目", "知识点", "课程", "考试", "训练", "讲解", "定律")
# 定义医疗领域关键词集合，用于快速判断问题主题。
MEDICAL_KEYWORDS = ("医疗", "症状", "头痛", "发烧", "咳嗽", "药", "健康", "医院")
# 定义路线类问题模式，用于识别“从A到B怎么走”这类文旅导航需求。
ROUTE_PATTERN = r"从.+到.+(怎么走|怎么去|路线|路程|导航|开车|打车|步行|骑行)"


# 定义领域识别函数，用于按关键词命中情况判断问题类型。
def detect_domain(query: str) -> str:
    # 保存原始问题的低噪声文本。
    text = query.strip().lower()
    # 若命中路线类问题模式，则直接按文旅导航问题处理。
    if re.search(ROUTE_PATTERN, query.strip()):
        return "tourism"
    # 统计文旅领域命中数量。
    tourism_hits = sum(keyword in text for keyword in TOURISM_KEYWORDS)
    # 统计教育领域命中数量。
    education_hits = sum(keyword in text for keyword in EDUCATION_KEYWORDS)
    # 统计医疗领域命中数量。
    medical_hits = sum(keyword in text for keyword in MEDICAL_KEYWORDS)
    # 构造领域得分映射，便于后续统一排序。
    scores = {
        "tourism": tourism_hits,
        "education": education_hits,
        "medical": medical_hits,
    }
    # 取出得分最高的领域名称。
    top_domain = max(scores, key=scores.get)
    # 若所有领域得分都为零，则返回通用领域。
    if scores[top_domain] == 0:
        # 对无明显领域的问题使用通用处理。
        return "general"
    # 返回得分最高的领域结果。
    return top_domain


# 定义技能选择函数，用于根据问题内容挑选技能组合。
def select_skills(domain: str, query: str) -> list[str]:
    # 先默认注入记忆技能，保证每次都有上下文能力。
    skills = ["skill_memory"]
    # 保存便于匹配的低噪声文本。
    text = query.strip().lower()
    # 判断当前问题是否属于明确的路线导航类问题。
    is_route_query = re.search(ROUTE_PATTERN, query.strip()) is not None
    # 判断当前问题是否带有路线规划意图。
    has_route_intent = is_route_query or any(keyword in text for keyword in ("规划路线", "路线规划", "路线", "怎么走", "怎么去", "导航"))
    # 若问题带有总结诉求，则追加摘要技能。
    if any(keyword in text for keyword in ("总结", "概括", "摘要", "梳理")):
        # 添加文本摘要技能。
        skills.append("skill_generate_summary")
    # 若问题含有搜索或实时查询语义，则追加搜索技能。
    if any(keyword in text for keyword in ("搜索", "查询", "最新", "实时", "天气")):
        # 添加通用搜索技能。
        skills.append("skill_web_search")
    # 若问题含有数学表达式或计算语义，则追加计算技能。
    if any(keyword in text for keyword in ("计算", "+", "-", "*", "/")) or re.search(r"\d+\s*[+\-*/]\s*\d+", text):
        # 添加安全计算技能。
        skills.append("skill_calculator")
    # 按不同业务领域追加专属技能。
    if domain == "tourism":
        # 对明确路线问题优先注入路线技能，避免误触发无关景点检索。
        if has_route_intent:
            # 添加路线规划技能。
            skills.append("skill_route_planning")
        # 若问题带有景点信息意图，或不是纯路线导航问题，则添加景点技能。
        if (not is_route_query) or any(keyword in text for keyword in ("景点", "门票", "开放时间", "介绍", "攻略", "游玩")):
            # 添加景点信息技能。
            skills.append("skill_attraction_info")
        # 对天气类问题补充天气技能。
        if "天气" in text or "温度" in text:
            # 添加天气检查技能。
            skills.append("skill_weather_check")
    # 对教育问题进行技能分发。
    if domain == "education":
        # 添加知识点讲解技能。
        skills.append("skill_knowledge_point_explain")
        # 对解题类问题追加习题求解技能。
        if any(keyword in text for keyword in ("题", "解", "求", "证明", "方程")):
            # 添加习题求解技能。
            skills.append("skill_exercise_solver")
        # 对学习规划类问题追加进度跟踪技能。
        if any(keyword in text for keyword in ("计划", "进度", "复习", "安排")):
            # 添加学习进度跟踪技能。
            skills.append("skill_learning_progress_track")
    # 对医疗问题进行技能分发。
    if domain == "medical":
        # 添加健康建议技能。
        skills.append("skill_health_tips_provider")
        # 对症状类问题追加症状分析技能。
        if any(keyword in text for keyword in ("症状", "难受", "头痛", "发烧", "咳嗽", "疼")):
            # 添加症状分析技能。
            skills.append("skill_symptom_analyzer")
        # 对用药类问题追加药品查询技能。
        if any(keyword in text for keyword in ("药", "用量", "副作用", "禁忌")):
            # 添加药品信息技能。
            skills.append("skill_drug_info_query")
    # 使用字典去重并保持原顺序。
    return list(dict.fromkeys(skills))
