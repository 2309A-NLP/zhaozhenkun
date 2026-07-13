# 工单20：本文件用于生成本地面试评分、问题解析和总体建议。
# 工单20：导入文本处理工具。
import re  # 工单20：代码语句。

# 工单20：定义积极关键词集合。
POSITIVE_WORDS = ["熟悉", "理解", "经验", "优化", "排查", "评估", "设计", "指标", "流程", "日志"]  # 工单20：代码语句。
# 工单20：定义消极关键词集合。
NEGATIVE_WORDS = ["不太会", "不了解", "没有做过", "忘了", "不清楚", "不会"]  # 工单20：代码语句。

# 工单20：定义复盘所用文本读取函数。
def get_review_transcript(interview: dict) -> str:  # 工单20：代码语句。
    # 工单20：优先使用完整面试记录，其次回退到录音转写文本。
    return (interview.get("full_transcript") or interview.get("audio_text") or "").strip()  # 工单20：代码语句。

# 工单20：定义问题抽取函数。
def extract_questions(interview: dict) -> list:  # 工单20：代码语句。
    # 工单20：优先返回已有问答结构。
    if interview.get("question_answers"):  # 工单20：代码语句。
        return interview.get("question_answers")  # 工单20：代码语句。
    # 工单20：读取复盘所需对话文本。
    transcript = get_review_transcript(interview)  # 工单20：代码语句。
    # 工单20：文本为空时返回空列表。
    if not transcript:  # 工单20：代码语句。
        return []  # 工单20：代码语句。
    # 工单20：初始化结果列表。
    result = []  # 工单20：代码语句。
    # 工单20：按说话人标签切分整段文本。
    segments = re.findall(r"(面试官|学生)：(.*?)(?=(?:面试官|学生)：|$)", transcript, flags=re.S)  # 工单20：代码语句。
    # 工单20：遍历切分后的对话片段。
    for speaker, content in segments:  # 工单20：代码语句。
        # 工单20：清洗当前片段文本。
        text = " ".join(content.strip().split())  # 工单20：代码语句。
        # 工单20：跳过空片段。
        if not text:  # 工单20：代码语句。
            continue  # 工单20：代码语句。
        # 工单20：识别问题片段并创建记录。
        if speaker == "面试官":  # 工单20：代码语句。
            result.append({"question": text, "answer": ""})  # 工单20：代码语句。
        # 工单20：将学生回答补充到上一题。
        elif result:  # 工单20：代码语句。
            result[-1]["answer"] = text  # 工单20：代码语句。
    # 工单20：返回解析结果。
    return result  # 工单20：代码语句。

# 工单20：定义技术点匹配函数。
def match_points(answer: str, knowledge_points: list) -> list:  # 工单20：代码语句。
    # 工单20：初始化匹配列表。
    matched = []  # 工单20：代码语句。
    # 工单20：遍历知识点做包含判断。
    for point in knowledge_points:  # 工单20：代码语句。
        if point.lower() in answer.lower():  # 工单20：代码语句。
            matched.append(point)  # 工单20：代码语句。
    # 工单20：返回匹配结果。
    return matched  # 工单20：代码语句。

# 工单20：定义单题打分函数。
def score_answer(question: str, answer: str, knowledge_points: list) -> dict:  # 工单20：代码语句。
    # 工单20：初始化基础分。
    score = 60  # 工单20：代码语句。
    # 工单20：统计积极表达数量。
    score += sum(4 for word in POSITIVE_WORDS if word in answer)  # 工单20：代码语句。
    # 工单20：扣除消极表达影响。
    score -= sum(8 for word in NEGATIVE_WORDS if word in answer)  # 工单20：代码语句。
    # 工单20：抽取命中的技术点。
    matched = match_points(answer, knowledge_points)  # 工单20：代码语句。
    # 工单20：按命中技术点补充分数。
    score += min(len(matched) * 5, 20)  # 工单20：代码语句。
    # 工单20：按回答长度补充分数。
    score += min(len(re.findall(r"[一-鿿A-Za-z0-9]", answer)) // 18, 10)  # 工单20：代码语句。
    # 工单20：限制分数范围。
    final_score = max(35, min(score, 98))  # 工单20：代码语句。
    # 工单20：生成优点文本。
    strengths = "、".join(matched[:3]) or "表达较完整"  # 工单20：代码语句。
    # 工单20：生成改进文本。
    improvements = "建议补充技术细节、指标和落地案例" if len(matched) < 2 else "建议增加更具体的项目结果与复盘深度"  # 工单20：代码语句。
    # 工单20：返回单题评分结果。
    return {  # 工单20：代码语句。
        "question": question,  # 工单20：代码语句。
        "answer": answer,  # 工单20：代码语句。
        "score": final_score,  # 工单20：代码语句。
        "comment": f"命中技术点：{strengths}。{improvements}。",  # 工单20：代码语句。
        "matched_points": matched,  # 工单20：代码语句。
    }  # 工单20：代码语句。

# 工单20：定义等级函数。
def level_of(score: float) -> str:  # 工单20：代码语句。
    # 工单20：根据分数输出等级。
    if score >= 90:  # 工单20：代码语句。
        return "优秀"  # 工单20：代码语句。
    if score >= 80:  # 工单20：代码语句。
        return "良好"  # 工单20：代码语句。
    if score >= 70:  # 工单20：代码语句。
        return "合格"  # 工单20：代码语句。
    return "待提升"  # 工单20：代码语句。

# 工单20：定义对话优化函数。
def optimize_transcript(interview: dict) -> str:  # 工单20：代码语句。
    # 工单20：提取问题列表。
    question_rows = extract_questions(interview)  # 工单20：代码语句。
    # 工单20：无问答时回退到复盘文本。
    if not question_rows:  # 工单20：代码语句。
        transcript = get_review_transcript(interview)  # 工单20：代码语句。
        # 工单20：文本为空时返回占位内容。
        if not transcript.strip():  # 工单20：代码语句。
            return "暂无可优化的面试对话。"  # 工单20：代码语句。
        # 工单20：返回轻量优化文本。
        return transcript.replace("我认为", "我的思路是").replace("我会先", "我的第一步会")  # 工单20：代码语句。
    # 工单20：初始化优化结果列表。
    optimized_lines = []  # 工单20：代码语句。
    # 工单20：遍历问题答案对。
    for item in question_rows:  # 工单20：代码语句。
        # 工单20：读取问题文本。
        question = item.get("question", "").strip()  # 工单20：代码语句。
        # 工单20：读取回答文本。
        answer = item.get("answer", "").strip()  # 工单20：代码语句。
        # 工单20：拼接优化版问题行。
        optimized_lines.append(f"面试官：{question}")  # 工单20：代码语句。
        # 工单20：拼接优化版回答行。
        optimized_lines.append(f"学生：我的结构化回答是，{answer.replace('我认为', '我的思路是').replace('我会先', '我的第一步会')}")  # 工单20：代码语句。
    # 工单20：返回优化后的完整对话。
    return "\n".join(optimized_lines)  # 工单20：代码语句。

# 工单20：定义总体复盘生成函数。
def build_review(interview: dict, knowledge_points: list) -> dict:  # 工单20：代码语句。
    # 工单20：提取问题列表。
    question_rows = extract_questions(interview)  # 工单20：代码语句。
    # 工单20：生成每题评分结果。
    analyses = [score_answer(item.get("question", ""), item.get("answer", ""), knowledge_points) for item in question_rows]  # 工单20：代码语句。
    # 工单20：计算平均分。
    average_score = round(sum(item["score"] for item in analyses) / len(analyses), 1) if analyses else 60.0  # 工单20：代码语句。
    # 工单20：构造总体评价文本。
    overall_comment = f"本次面试整体表现为{level_of(average_score)}，回答有一定结构，建议继续强化案例细节与结果表达。"  # 工单20：代码语句。
    # 工单20：构造自我介绍点评文本。
    self_intro_comment = "自我介绍能够覆盖方向和项目经历，建议增加个人亮点、量化结果和岗位匹配度。"  # 工单20：代码语句。
    # 工单20：构造改进建议列表。
    suggestions = [  # 工单20：代码语句。
        "回答技术问题时优先给出结论，再补充流程、指标和结果。",  # 工单20：代码语句。
        "每个项目准备一个可量化成果，避免回答停留在概念层。",  # 工单20：代码语句。
        "针对岗位核心技术点做专项复盘，形成自己的答题模板。",  # 工单20：代码语句。
    ]  # 工单20：代码语句。
    # 工单20：返回完整复盘结构。
    return {  # 工单20：代码语句。
        "overall_score": average_score,  # 工单20：代码语句。
        "overall_level": level_of(average_score),  # 工单20：代码语句。
        "overall_comment": overall_comment,  # 工单20：代码语句。
        "self_intro_comment": self_intro_comment,  # 工单20：代码语句。
        "suggestions": suggestions,  # 工单20：代码语句。
        "question_analysis": analyses,  # 工单20：代码语句。
        "optimized_transcript": optimize_transcript(interview),  # 工单20：代码语句。
        "original_transcript": get_review_transcript(interview),  # 工单20：代码语句。
    }  # 工单20：代码语句。
