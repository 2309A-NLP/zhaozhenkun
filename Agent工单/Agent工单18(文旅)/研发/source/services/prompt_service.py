"""工单18：语言与提示词辅助服务，负责规范语言标签、字幕格式和系统提示词。"""
# 工单18：定义支持语言映射，把前端简写转换成模型可理解表述。
LANGUAGE_LABELS = {
    "zh": "中文",
    "en": "英文",
    "ja": "日文",
}

# 工单18：根据语言代码返回展示名称，未命中时默认中文。
def get_language_label(language: str) -> str:
    # 工单18：把空值兜底成中文，保证提示词稳定。
    return LANGUAGE_LABELS.get((language or "zh").strip().lower(), "中文")

# 工单18：统一整理字幕文本，去掉多余空白，提升前端显示效果。
def normalize_subtitle(text: str) -> str:
    # 工单18：按行拆分并清理每行首尾空格。
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    # 工单18：把处理后的内容重新拼成单段字幕文本。
    return " ".join(lines)

# 工单18：为导览场景构建系统提示词，约束风格更贴近文旅讲解。
def build_system_prompt(language: str, scene: str) -> str:
    # 工单18：先把语言代码转为自然语言名称。
    label = get_language_label(language)
    # 工单18：根据场景拼出更明确的角色与输出要求。
    return (
        f"你是文旅智能导览数字人，当前场景是{scene}。"
        f"请使用{label}回答，要求口语化、易懂、适合游客听讲。"
        "如果涉及推荐路线，要给出简短建议；如果涉及图片，请先解释看到什么，再讲文化信息；"
        "输出适合直接展示在字幕区域，不要写多余格式符号。"
    )
