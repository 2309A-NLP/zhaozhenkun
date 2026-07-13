"""该文件用于提供基于 JSON 文件的轻量会话记忆能力。"""

# 导入 JSON 模块，用于读写会话历史。
import json
# 导入环境变量模块，用于支持外部指定记忆文件位置。
import os
# 导入路径工具，用于定位项目根目录与记忆文件路径。
from pathlib import Path


# 定义轻量记忆仓库，用于保存每个会话的对话记录。
class JsonMemoryStore:
    # 初始化记忆仓库，并确定底层 JSON 文件路径。
    def __init__(self, file_path: str | None = None) -> None:
        # 定位当前文件所在项目根目录。
        project_root = Path(__file__).resolve().parents[2]
        # 读取外部传入路径或环境变量路径。
        configured_path = file_path or os.getenv("AGENT_MEMORY_FILE", "")
        # 生成最终记忆文件路径。
        self.file_path = Path(configured_path) if configured_path else project_root / "optimization" / "session_memory.json"
        # 确保父目录存在，避免首次写入时报错。
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    # 加载全部记忆数据，若文件不存在则返回空字典。
    def _load(self) -> dict[str, list[dict[str, str]]]:
        # 判断记忆文件是否已经存在。
        if not self.file_path.exists():
            # 若文件不存在，则返回空的会话映射。
            return {}
        # 读取文本内容，便于后续解析 JSON。
        raw_text = self.file_path.read_text(encoding="utf-8").strip()
        # 处理空文件场景，避免 JSON 解析报错。
        if not raw_text:
            # 空文件等价于没有会话记录。
            return {}
        # 将 JSON 文本解析为 Python 字典。
        return json.loads(raw_text)

    # 保存全部记忆数据，用于持久化写回文件。
    def _save(self, payload: dict[str, list[dict[str, str]]]) -> None:
        # 将数据序列化并写回磁盘。
        self.file_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # 读取指定会话的最近若干条记录。
    def recall(self, session_id: str, limit: int = 6) -> list[dict[str, str]]:
        # 加载当前全部会话数据。
        payload = self._load()
        # 取出当前会话列表，若不存在则回退为空列表。
        records = payload.get(session_id, [])
        # 返回最近若干条记录，便于控制提示词长度。
        return records[-limit:]

    # 追加一条对话记录，并立即落盘保存。
    def append(self, session_id: str, role: str, content: str) -> None:
        # 加载当前全部会话数据。
        payload = self._load()
        # 若会话不存在，则先初始化空列表。
        payload.setdefault(session_id, [])
        # 向会话中追加当前角色与内容。
        payload[session_id].append({"role": role, "content": content})
        # 保存更新后的完整会话数据。
        self._save(payload)
