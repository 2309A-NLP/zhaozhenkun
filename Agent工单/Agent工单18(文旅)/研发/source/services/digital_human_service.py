"""工单18：数字人呈现配置服务，负责统一数字人形象、动作状态与展示文案。"""
# 工单18：定义数字人展示配置，便于前端根据状态切换表情与提示。
DIGITAL_HUMAN_CONFIG = {
    "name": "八维文旅导览数字人",
    "avatar_prompt": "中国文旅讲解员风格，蓝色制服，亲和微笑，2D数字人立绘",
    "states": {
        "idle": "待机中，保持自然微笑。",
        "speaking": "正在讲解，配合字幕与音频输出。",
        "wave": "识别到挥手后执行欢迎动作。",
        "thumbs_up": "识别到点赞后执行积极反馈动作。",
        "point": "识别到指向后执行关注目标讲解动作。",
        "smile": "识别到微笑后执行轻松互动动作。",
    },
}

# 工单18：读取数字人配置，供接口返回给前端展示层使用。
def get_digital_human_config() -> dict:
    return DIGITAL_HUMAN_CONFIG
