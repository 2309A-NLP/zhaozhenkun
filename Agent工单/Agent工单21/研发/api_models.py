"""文件功能：定义 API 层请求与响应所需的数据模型。"""
from __future__ import annotations  # 启用延后类型注解支持。
from pydantic import BaseModel  # 导入基础数据模型类。
from pydantic import Field  # 导入字段定义工具。


class PersonaCreateRequest(BaseModel):  # 定义创建数字人的请求模型。
    name: str = Field(default="默认数字人", min_length=1, max_length=60)  # 保存数字人名称。
    description: str = Field(default="基于上传素材构建的个人数字人。", max_length=500)  # 保存数字人描述。
    voice_style: str = Field(default="专业、自然、简洁", max_length=120)  # 保存数字人口播风格。
    motion_style: str = Field(default="自然", max_length=120)  # 保存数字人动作风格。
    avatar_image_asset_id: str = Field(default="")  # 保存头像素材主键。
    knowledge_asset_ids: list[str] = Field(default_factory=list)  # 保存知识素材主键列表。
    ultralight_dataset_dir: str = Field(default="")  # 保存真实 Ultralight 训练数据目录。
    ultralight_checkpoint_path: str = Field(default="")  # 保存真实 Ultralight 训练权重路径。


class PersonaUpdateRequest(BaseModel):  # 定义更新数字人的请求模型。
    name: str | None = Field(default=None, min_length=1, max_length=60)  # 保存可选的数字人名称。
    description: str | None = Field(default=None, max_length=500)  # 保存可选的数字人描述。
    voice_style: str | None = Field(default=None, max_length=120)  # 保存可选的口播风格。
    motion_style: str | None = Field(default=None, max_length=120)  # 保存可选的动作风格。
    avatar_image_asset_id: str | None = Field(default=None)  # 保存可选的头像素材主键。
    knowledge_asset_ids: list[str] | None = Field(default=None)  # 保存可选的知识素材主键列表。
    ultralight_dataset_dir: str | None = Field(default=None)  # 保存可选的训练数据目录。
    ultralight_checkpoint_path: str | None = Field(default=None)  # 保存可选的训练权重路径。


class TrainingJobCreateRequest(BaseModel):  # 定义创建训练任务的请求模型。
    persona_id: str = Field(min_length=1)  # 保存数字人主键。
    asset_ids: list[str] = Field(default_factory=list)  # 保存参与训练的素材主键列表。


class TrainingJobPreflightRequest(BaseModel):  # 定义训练预检请求模型。
    persona_id: str = Field(min_length=1)  # 保存数字人主键。
    asset_ids: list[str] = Field(default_factory=list)  # 保存待检查素材主键列表。


class ChatRequest(BaseModel):  # 定义问答请求模型。
    persona_id: str = Field(min_length=1)  # 保存数字人主键。
    question: str = Field(min_length=1, max_length=3000)  # 保存用户问题。
    session_id: str = Field(default="")  # 保存会话主键。
    image_asset_id: str = Field(default="")  # 保存图片素材主键。


class AvatarJobCreateRequest(BaseModel):  # 定义数字人生成请求模型。
    persona_id: str = Field(min_length=1)  # 保存数字人主键。
    session_id: str = Field(min_length=1)  # 保存会话主键。
    answer_text: str = Field(min_length=1, max_length=4000)  # 保存待播报答案。


class AvatarJobPreflightRequest(BaseModel):  # 定义数字人任务预检请求模型。
    persona_id: str = Field(min_length=1)  # 保存数字人主键。


class TextAssetCreateRequest(BaseModel):  # 定义文本素材创建请求模型。
    name: str = Field(min_length=1, max_length=120)  # 保存素材名称。
    content_text: str = Field(min_length=1, max_length=10000)  # 保存文本内容。
    tags: list[str] = Field(default_factory=list)  # 保存素材标签列表。
