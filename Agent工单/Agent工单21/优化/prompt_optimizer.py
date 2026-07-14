"""文件功能：裁剪上下文长度并整理历史消息，避免提示词冗长失控。"""

from __future__ import annotations  # 启用延后类型注解支持。


class PromptOptimizer:  # 定义提示词优化器。
    def trim_text(self, text: str, max_chars: int) -> str:  # 按最大字符数裁剪文本。
        return text if len(text) <= max_chars else text[: max_chars - 3] + "..."  # 返回裁剪后的文本。

    def format_history(self, messages: list[dict[str, str]], limit: int, max_chars: int) -> str:  # 格式化历史消息。
        lines: list[str] = []  # 初始化历史消息文本列表。
        for message in messages[-limit:]:  # 遍历最近若干条消息。
            role = "用户" if message.get("role") == "user" else "助手"  # 转换消息角色名称。
            content = self.trim_text(message.get("content", ""), max_chars // max(1, limit))  # 裁剪单条消息内容。
            lines.append(f"{role}：{content}")  # 追加格式化后的消息行。
        return "\n".join(lines)  # 返回拼接后的历史消息文本。

    def merge_knowledge(self, assets: list[dict[str, str]], max_chars: int) -> str:  # 合并知识素材内容。
        blocks: list[str] = []  # 初始化知识块列表。
        for asset in assets:  # 遍历相关素材。
            title = asset.get("name", "未命名素材")  # 读取素材标题。
            summary = asset.get("summary") or asset.get("content_text", "")  # 优先使用摘要文本。
            blocks.append(f"[{title}]\n{summary}")  # 追加单条知识块。
        return self.trim_text("\n\n".join(blocks), max_chars)  # 返回裁剪后的知识库文本。
