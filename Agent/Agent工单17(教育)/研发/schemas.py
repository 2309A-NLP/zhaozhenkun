# -*- coding: utf-8 -*-
# 工单编号：人工智能NLP-Agent数字人项目-17-教育Agent任务工单-教学场景功能分析及智能备课
# 模块：API请求体模型 - FastAPI POST body参数定义
# 创建时间：2025年6月
# 作者：Agent智能备课系统开发组

from pydantic import BaseModel, Field  # Pydantic数据验证
from typing import Optional, Any, Dict, List  # 可选类型


class LoginRequest(BaseModel):
    """登录请求体 - 使用POST body传递用户名密码，避免密码出现在URL日志中"""
    username: str = Field(..., min_length=3, max_length=50, description="用户登录名")  # 用户名
    password: str = Field(..., min_length=6, max_length=100, description="用户密码")  # 密码


class GenerateRequest(BaseModel):
    """备课生成请求体 - 使用POST body传递课程信息，支持复杂参数"""
    course_name: str = Field(..., min_length=2, description="课程名称")  # 课程名
    chapter: str = Field(..., description="章节名称")  # 章节
    grade_level: str = Field(..., description="适用年级")  # 年级
    subject: str = Field(..., description="学科")  # 学科
    teaching_objectives: str = Field(..., min_length=10, description="教学目标")  # 教学目标
    class_hours: int = Field(default=1, ge=1, le=20, description="课时数")  # 课时
    content_types: str = Field(default="lesson_plan,exercise", description="内容类型(逗号分隔)")  # 内容类型
    use_kb: bool = Field(default=True, description="是否启用知识库")  # 是否用RAG
    key_points: str = Field(default="", description="教学重点")  # 教学重点
    difficult_points: str = Field(default="", description="教学难点")  # 教学难点
    additional_instructions: str = Field(default="", description="额外指令")  # 额外指令


class ImproveRequest(BaseModel):
    """内容优化请求体"""
    content_text: str = Field(..., min_length=10, description="原始内容")  # 原始内容
    improvement_request: str = Field(..., min_length=5, description="改进要求")  # 改进要求


class SearchRequest(BaseModel):
    """知识库检索请求体"""
    query: str = Field(..., min_length=1, description="检索关键词")  # 检索词
    max_results: int = Field(default=10, ge=1, le=50, description="最大返回数")  # 最大结果
    resource_type: str = Field(default="", description="资源类型过滤")  # 类型过滤


class UploadRequest(BaseModel):
    """资源上传请求体"""
    title: str = Field(..., min_length=1, description="资源标题")  # 标题
    content: str = Field(..., min_length=10, description="资源内容")  # 内容
    resource_type: str = Field(default="school_based", description="资源类型")  # 类型
    tags: str = Field(default="", description="标签(逗号分隔)")  # 标签
    source_url: str = Field(default="", description="来源URL")  # 来源URL


class ExportRequest(BaseModel):
    """导出请求体"""
    content_json: str = Field(..., description="内容JSON字符串")  # 内容JSON
    title: str = Field(default="教学内容", description="导出标题")  # 标题
    export_format: str = Field(default="markdown", description="导出格式(逗号分隔)")  # 导出格式


class CompareRequest(BaseModel):
    """版本对比请求体"""
    version_id_a: str = Field(..., description="版本A的ID")  # 版本A
    version_id_b: str = Field(..., description="版本B的ID")  # 版本B


class UpdateContentRequest(BaseModel):
    """更新内容请求体"""
    raw_content: str = Field(..., min_length=1, description="更新后的原始内容")
    structured_content: Optional[Dict[str, Any]] = Field(default=None, description="结构化内容")
    change_summary: str = Field(default="手动编辑", description="变更摘要")


class CloneContentRequest(BaseModel):
    """克隆内容请求体"""
    title: str = Field(default="", description="克隆后的标题")


class CreateCollaborationSessionRequest(BaseModel):
    """创建协同会话请求体"""
    content_id: str = Field(..., description="内容ID")
