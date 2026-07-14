"""文件功能：提供本地 JSON 仓储，统一保存素材、数字人、训练任务和会话数据。"""

from __future__ import annotations  # 启用延后类型注解支持。

import json  # 处理 JSON 持久化。
from pathlib import Path  # 处理文件路径。
from typing import Any  # 描述通用字段类型。

from 设计.schemas import AssetRecord  # 导入素材数据结构。
from 设计.schemas import AvatarJobRecord  # 导入数字人任务数据结构。
from 设计.schemas import ChatMessageRecord  # 导入会话消息结构。
from 设计.schemas import ChatSessionRecord  # 导入会话结构。
from 设计.schemas import PersonaRecord  # 导入数字人画像结构。
from 设计.schemas import TrainingJobRecord  # 导入训练任务结构。
from 设计.schemas import now_iso  # 导入统一时间戳函数。


class JsonRepository:  # 定义通用 JSON 仓储。
    def __init__(self, file_path: Path) -> None:  # 初始化仓储对象。
        self.file_path = file_path  # 保存目标文件路径。
        self.file_path.parent.mkdir(parents=True, exist_ok=True)  # 确保父目录存在。
        if not self.file_path.exists():  # 如果数据文件不存在。
            self.file_path.write_text("[]", encoding="utf-8")  # 初始化为空列表。

    def load_all(self) -> list[dict[str, Any]]:  # 读取全部记录。
        return json.loads(self.file_path.read_text(encoding="utf-8"))  # 解析并返回 JSON 列表。

    def save_all(self, items: list[dict[str, Any]]) -> None:  # 保存全部记录。
        self.file_path.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")  # 写回 JSON 内容。

    def list_items(self) -> list[dict[str, Any]]:  # 返回全部字典记录。
        return self.load_all()  # 调用读取方法返回结果。

    def get_item(self, key_name: str, key_value: str) -> dict[str, Any] | None:  # 按主键查询记录。
        for item in self.load_all():  # 遍历全部记录。
            if item.get(key_name) == key_value:  # 如果匹配指定主键值。
                return item  # 返回目标记录。
        return None  # 未命中时返回空值。

    def upsert_item(self, key_name: str, payload: dict[str, Any]) -> dict[str, Any]:  # 保存或更新单条记录。
        items = self.load_all()  # 读取全部记录。
        target_key = payload[key_name]  # 读取目标主键值。
        for index, item in enumerate(items):  # 遍历已有记录。
            if item.get(key_name) == target_key:  # 如果命中已有记录。
                items[index] = payload  # 用新内容覆盖旧记录。
                self.save_all(items)  # 保存所有记录。
                return payload  # 返回保存结果。
        items.append(payload)  # 追加新记录。
        self.save_all(items)  # 保存所有记录。
        return payload  # 返回保存结果。


class ProjectRepository:  # 定义项目级仓储门面。
    def __init__(self, data_dir: Path) -> None:  # 初始化项目仓储。
        self.assets = JsonRepository(data_dir / "assets.json")  # 初始化素材仓储。
        self.personas = JsonRepository(data_dir / "personas.json")  # 初始化数字人仓储。
        self.training_jobs = JsonRepository(data_dir / "training_jobs.json")  # 初始化训练任务仓储。
        self.chat_sessions = JsonRepository(data_dir / "chat_sessions.json")  # 初始化会话仓储。
        self.avatar_jobs = JsonRepository(data_dir / "avatar_jobs.json")  # 初始化数字人任务仓储。

    def save_asset(self, asset: AssetRecord) -> dict[str, Any]:  # 保存素材记录。
        asset.updated_at = now_iso()  # 刷新更新时间。
        return self.assets.upsert_item("asset_id", asset.to_dict())  # 保存素材并返回结果。

    def save_persona(self, persona: PersonaRecord) -> dict[str, Any]:  # 保存数字人记录。
        persona.updated_at = now_iso()  # 刷新更新时间。
        return self.personas.upsert_item("persona_id", persona.to_dict())  # 保存数字人并返回结果。

    def save_training_job(self, job: TrainingJobRecord) -> dict[str, Any]:  # 保存训练任务记录。
        job.updated_at = now_iso()  # 刷新更新时间。
        return self.training_jobs.upsert_item("job_id", job.to_dict())  # 保存训练任务并返回结果。

    def save_session(self, session: ChatSessionRecord) -> dict[str, Any]:  # 保存会话记录。
        session.updated_at = now_iso()  # 刷新更新时间。
        return self.chat_sessions.upsert_item("session_id", session.to_dict())  # 保存会话并返回结果。

    def save_avatar_job(self, job: AvatarJobRecord) -> dict[str, Any]:  # 保存数字人任务记录。
        job.updated_at = now_iso()  # 刷新更新时间。
        return self.avatar_jobs.upsert_item("avatar_job_id", job.to_dict())  # 保存数字人任务并返回结果。

    def append_message(self, session_id: str, message: ChatMessageRecord) -> dict[str, Any]:  # 向会话中追加消息。
        stored = self.chat_sessions.get_item("session_id", session_id)  # 读取目标会话。
        if stored is None:  # 如果会话不存在。
            session = ChatSessionRecord(session_id=session_id, messages=[message])  # 构建新会话对象。
        else:  # 如果会话已存在。
            messages = [ChatMessageRecord(**item) for item in stored.get("messages", [])]  # 转换已有消息对象。
            messages.append(message)  # 追加新消息。
            session = ChatSessionRecord(  # 重建会话对象。
                session_id=stored["session_id"],  # 保留会话主键。
                persona_id=stored.get("persona_id", ""),  # 保留关联数字人主键。
                title=stored.get("title", "新会话"),  # 保留会话标题。
                messages=messages,  # 使用新的消息列表。
                created_at=stored.get("created_at", now_iso()),  # 保留创建时间。
            )  # 完成会话对象重建。
        return self.save_session(session)  # 保存并返回会话结果。
