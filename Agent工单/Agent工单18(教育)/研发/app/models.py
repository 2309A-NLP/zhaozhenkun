# -*- coding: utf-8 -*-  # 工单18：指定源码编码为 UTF-8。
"""models.py - 工单18智能助教的请求与响应数据模型模块。"""  # 工单18：声明当前文件功能。

from __future__ import annotations  # 工单18：启用延迟类型注解。

from typing import Literal  # 工单18：导入字面量类型定义。

from pydantic import BaseModel  # 工单18：导入基础数据模型类。
from pydantic import ConfigDict  # 工单18：导入模型配置类型。
from pydantic import Field  # 工单18：导入字段约束工具。


class LoginRequest(BaseModel):  # 工单18：定义登录请求模型。
    username: str = Field(..., min_length=3, max_length=32)  # 工单18：定义用户名字段。
    password: str = Field(..., min_length=3, max_length=32)  # 工单18：定义密码字段。


class AskRequest(BaseModel):  # 工单18：定义智能助教提问请求模型。
    model_config = ConfigDict(protected_namespaces=())  # 工单18：关闭 model_ 前缀保护以消除字段命名警告。

    question: str = Field(..., min_length=2, max_length=2000)  # 工单18：定义问题文本字段。
    model_provider: Literal["deepseek", "qwen"] = "deepseek"  # 工单18：定义模型服务商字段。
    top_k: int = Field(6, ge=1, le=10)  # 工单18：定义检索条数字段。
    use_public: bool = True  # 工单18：定义是否启用公共知识库。
    use_private: bool = True  # 工单18：定义是否启用私有知识库。


class TextResourceRequest(BaseModel):  # 工单18：定义文本知识资源上传模型。
    title: str = Field(..., min_length=1, max_length=120)  # 工单18：定义资源标题字段。
    scope: Literal["public", "private"] = "private"  # 工单18：定义知识库范围字段。
    resource_type: Literal["text", "markdown", "table", "image_note", "formula_note"] = "text"  # 工单18：定义资源类型字段。
    content_text: str = Field(..., min_length=1, max_length=40000)  # 工单18：定义资源正文字段。
    source_url: str = Field("", max_length=500)  # 工单18：定义来源链接字段。
    tags: str = Field("", max_length=300)  # 工单18：定义标签字段。


class ResourceQuery(BaseModel):  # 工单18：定义资源列表查询模型。
    scope: Literal["all", "public", "private"] = "all"  # 工单18：定义范围过滤字段。


class ApiEnvelope(BaseModel):  # 工单18：定义统一响应包模型。
    success: bool = True  # 工单18：定义请求成功标记字段。
    message: str = "ok"  # 工单18：定义响应消息字段。
    data: dict = Field(default_factory=dict)  # 工单18：定义响应数据字段。


def split_tags(raw_tags: str) -> list[str]:  # 工单18：定义标签标准化函数。
    items = [item.strip() for item in raw_tags.replace("；", ",").replace("，", ",").split(",")]  # 工单18：切分并清洗标签文本。
    return [item for item in items if item]  # 工单18：返回去空后的标签列表。
