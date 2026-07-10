"""工单18：行为识别服务，负责把游客动作映射为可讲解的互动意图。"""
# 工单18：定义行为标签到说明文案的映射，支撑互动问答场景。
BEHAVIOR_MAP = {
    "wave": "游客正在挥手，适合主动问候并引导开始导览。",
    "thumbs_up": "游客做出点赞动作，说明当前体验积极，可推荐热门景点。",
    "point": "游客正在指向某个目标，适合围绕目标景物进行重点讲解。",
    "smile": "游客面带微笑，适合继续轻松讲解并发起互动问答。",
}

# 工单18：根据前端传来的行为标签生成标准化解释结果。
def analyze_behavior(behavior: str) -> dict:
    # 工单18：把空值兜底成unknown，避免接口因为缺字段直接报错。
    normalized = (behavior or "unknown").strip().lower()
    # 工单18：查询行为说明，不存在时给出通用解释。
    summary = BEHAVIOR_MAP.get(normalized, "暂未识别到明确动作，建议数字人继续保持基础讲解并等待游客进一步互动。")
    # 工单18：返回结构化结果，便于后续生成回复文本。
    return {"behavior": normalized, "summary": summary}
