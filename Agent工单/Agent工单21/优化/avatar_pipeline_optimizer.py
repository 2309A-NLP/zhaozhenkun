"""文件功能：把长答案整理成适合数字人口播的短句脚本，并推断动作风格。"""

from __future__ import annotations  # 启用延后类型注解支持。


class AvatarPipelineOptimizer:  # 定义数字人脚本优化器。
    def choose_motion_style(self, persona_motion_style: str, answer_text: str) -> str:  # 选择动作风格。
        if "欢迎" in answer_text or "你好" in answer_text:  # 如果答案偏向问候场景。
            return "亲和、自然"  # 返回亲和风格。
        return persona_motion_style or "自然"  # 返回默认或画像动作风格。

    def build_script_lines(self, answer_text: str) -> list[str]:  # 把长答案拆成短句列表。
        normalized = answer_text.replace("。", "。\n").replace("！", "！\n").replace("？", "？\n")  # 按中文句号切分答案。
        lines = [line.strip() for line in normalized.splitlines() if line.strip()]  # 清理并保留非空句子。
        return lines[:8] if lines else [answer_text.strip()]  # 返回适合播报的句子列表。
