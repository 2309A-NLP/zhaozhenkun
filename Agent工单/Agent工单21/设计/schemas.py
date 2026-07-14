"""文件功能：定义素材、训练、会话、数字人任务等核心数据结构。"""

from __future__ import annotations  # 启用延后类型注解支持。

from dataclasses import asdict  # 把数据类转换为字典。
from dataclasses import dataclass  # 定义结构化数据对象。
from dataclasses import field  # 定义带默认值工厂的字段。
from datetime import datetime  # 生成时间戳。
from typing import Any  # 描述通用字段类型。
from uuid import uuid4  # 生成唯一主键。


def now_iso() -> str:  # 生成统一格式的当前时间戳。
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"  # 返回 UTC 字符串。


def new_id(prefix: str) -> str:  # 生成带前缀的业务主键。
    return f"{prefix}_{uuid4().hex[:12]}"  # 返回紧凑唯一主键。


@dataclass(slots=True)  # 定义素材对象。
class AssetRecord:  # 保存上传素材的元数据。
    asset_id: str = field(default_factory=lambda: new_id("asset"))  # 保存素材主键。
    name: str = ""  # 保存素材名称。
    asset_type: str = "text"  # 保存素材类型。
    file_name: str = ""  # 保存原始文件名。
    file_path: str = ""  # 保存本地文件路径。
    content_text: str = ""  # 保存解析后的文本内容。
    tags: list[str] = field(default_factory=list)  # 保存素材标签列表。
    summary: str = ""  # 保存素材摘要。
    created_at: str = field(default_factory=now_iso)  # 保存创建时间。
    updated_at: str = field(default_factory=now_iso)  # 保存更新时间。

    def to_dict(self) -> dict[str, Any]:  # 转换为字典结构。
        return asdict(self)  # 返回完整字典。


@dataclass(slots=True)  # 定义数字人画像对象。
class PersonaRecord:  # 保存数字人的基础配置。
    persona_id: str = field(default_factory=lambda: new_id("persona"))  # 保存数字人主键。
    name: str = "默认数字人"  # 保存数字人名称。
    description: str = "基于上传素材构建的个人数字人。"  # 保存数字人描述。
    voice_style: str = "专业、自然、简洁"  # 保存语气风格。
    motion_style: str = "自然"  # 保存动作风格。
    avatar_image_asset_id: str = ""  # 保存头像素材引用。
    knowledge_asset_ids: list[str] = field(default_factory=list)  # 保存知识素材列表。
    ultralight_dataset_dir: str = ""  # 保存真实 Ultralight 训练数据目录。
    ultralight_checkpoint_path: str = ""  # 保存真实 Ultralight 训练权重路径。
    created_at: str = field(default_factory=now_iso)  # 保存创建时间。
    updated_at: str = field(default_factory=now_iso)  # 保存更新时间。

    def to_dict(self) -> dict[str, Any]:  # 转换为字典结构。
        return asdict(self)  # 返回完整字典。


@dataclass(slots=True)  # 定义训练任务对象。
class TrainingJobRecord:  # 保存训练或整理任务状态。
    job_id: str = field(default_factory=lambda: new_id("train"))  # 保存任务主键。
    persona_id: str = ""  # 保存关联数字人主键。
    asset_ids: list[str] = field(default_factory=list)  # 保存参与训练的素材列表。
    status: str = "pending"  # 保存任务状态。
    stage: str = "created"  # 保存当前阶段。
    result_path: str = ""  # 保存训练产物路径。
    message: str = "任务已创建。"  # 保存状态说明。
    created_at: str = field(default_factory=now_iso)  # 保存创建时间。
    updated_at: str = field(default_factory=now_iso)  # 保存更新时间。

    def to_dict(self) -> dict[str, Any]:  # 转换为字典结构。
        return asdict(self)  # 返回完整字典。


@dataclass(slots=True)  # 定义会话消息对象。
class ChatMessageRecord:  # 保存一条会话消息。
    role: str = "user"  # 保存消息角色。
    content: str = ""  # 保存消息内容。
    created_at: str = field(default_factory=now_iso)  # 保存时间戳。

    def to_dict(self) -> dict[str, Any]:  # 转换为字典结构。
        return asdict(self)  # 返回完整字典。


@dataclass(slots=True)  # 定义会话对象。
class ChatSessionRecord:  # 保存完整会话及历史。
    session_id: str = field(default_factory=lambda: new_id("session"))  # 保存会话主键。
    persona_id: str = ""  # 保存关联数字人主键。
    title: str = "新会话"  # 保存会话标题。
    messages: list[ChatMessageRecord] = field(default_factory=list)  # 保存会话消息列表。
    created_at: str = field(default_factory=now_iso)  # 保存创建时间。
    updated_at: str = field(default_factory=now_iso)  # 保存更新时间。

    def to_dict(self) -> dict[str, Any]:  # 转换为字典结构。
        payload = asdict(self)  # 把会话对象转为字典。
        payload["messages"] = [message.to_dict() for message in self.messages]  # 递归转换消息对象。
        return payload  # 返回字典结构。


@dataclass(slots=True)  # 定义数字人输出任务对象。
class AvatarJobRecord:  # 保存数字人响应生成任务。
    avatar_job_id: str = field(default_factory=lambda: new_id("avatar"))  # 保存任务主键。
    persona_id: str = ""  # 保存关联数字人主键。
    session_id: str = ""  # 保存关联会话主键。
    answer_text: str = ""  # 保存问答结果文本。
    script_text: str = ""  # 保存数字人口播脚本。
    output_path: str = ""  # 保存输出文件路径。
    status: str = "pending"  # 保存任务状态。
    message: str = "任务已创建。"  # 保存状态说明。
    created_at: str = field(default_factory=now_iso)  # 保存创建时间。
    updated_at: str = field(default_factory=now_iso)  # 保存更新时间。

    def to_dict(self) -> dict[str, Any]:  # 转换为字典结构。
        return asdict(self)  # 返回完整字典。
