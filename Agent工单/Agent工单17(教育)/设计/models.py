# -*- coding: utf-8 -*-
# 工单编号：人工智能NLP-Agent数字人项目-17-教育Agent任务工单-教学场景功能分析及智能备课
# 模块：数据模型定义 - 定义系统所有核心数据结构
# 创建时间：2025年6月
# 作者：Agent智能备课系统开发组

from __future__ import annotations  # 启用延迟注解求值
from pydantic import BaseModel, Field, validator  # 数据验证库
from typing import List, Optional, Dict, Any  # 类型提示
from datetime import datetime  # 时间处理
from enum import Enum  # 枚举类型


# ==================== 枚举定义 ====================

class ContentType(str, Enum):
    """内容类型枚举 - 定义系统支持生成的教学内容类型"""
    LESSON_PLAN = "lesson_plan"      # 教案类型
    COURSEWARE = "courseware"        # 课件类型
    EXERCISE = "exercise"            # 习题类型
    CASE_STUDY = "case_study"        # 案例类型
    EXAM_PAPER = "exam_paper"        # 试卷类型


class ExportFormat(str, Enum):
    """导出格式枚举 - 定义系统支持的文档导出格式"""
    PDF = "pdf"                      # PDF格式
    DOCX = "docx"                    # Word格式
    PPTX = "pptx"                    # PowerPoint格式
    MARKDOWN = "markdown"            # Markdown格式


class ResourceType(str, Enum):
    """资源类型枚举 - 定义知识库中的资源类型"""
    TEXTBOOK = "textbook"            # 教材资源
    SCHOOL_BASED = "school_based"    # 校本资源
    NETWORK = "network"              # 网络资源
    MULTIMEDIA = "multimedia"        # 多媒体资源


class UserRole(str, Enum):
    """用户角色枚举 - 定义系统用户权限角色"""
    TEACHER = "teacher"              # 教师角色
    ADMIN = "admin"                  # 管理员角色
    STUDENT = "student"              # 学生角色（预留）


# ==================== 用户相关模型 ====================

class UserLoginRequest(BaseModel):
    """用户登录请求模型 - 接收前端登录表单数据"""
    username: str = Field(..., min_length=3, max_length=50, description="用户登录名")  # 用户名，3-50字符
    password: str = Field(..., min_length=6, max_length=100, description="用户密码")  # 密码，6-100字符


class UserInfo(BaseModel):
    """用户信息模型 - 返回给前端的用户基本信息"""
    user_id: str = Field(..., description="用户唯一标识")  # 用户ID
    username: str = Field(..., description="用户登录名")  # 用户名
    role: UserRole = Field(..., description="用户角色")  # 角色
    display_name: str = Field(..., description="显示名称")  # 显示名称
    department: Optional[str] = Field(None, description="所属部门")  # 部门（可选）


class TokenResponse(BaseModel):
    """Token响应模型 - 登录成功后返回JWT令牌"""
    access_token: str = Field(..., description="访问令牌")  # JWT访问令牌
    token_type: str = Field(default="bearer", description="令牌类型")  # 令牌类型
    expires_in: int = Field(..., description="过期时间(秒)")  # 过期时间
    user_info: UserInfo = Field(..., description="用户信息")  # 关联用户信息


# ==================== 课程相关模型 ====================

class CourseBasicInfo(BaseModel):
    """课程基本信息模型 - 教师填写课程的基础信息"""
    course_name: str = Field(..., min_length=2, max_length=200, description="课程名称")  # 课程名
    chapter: str = Field(..., min_length=1, max_length=200, description="章节名称")  # 章节名
    grade_level: str = Field(..., description="适用年级")  # 适用年级
    subject: str = Field(..., description="学科")  # 所属学科
    teaching_objectives: str = Field(..., min_length=10, description="教学目标")  # 教学目标，最少10字
    class_hours: int = Field(default=1, ge=1, le=20, description="课时数")  # 课时数，1-20
    key_points: Optional[str] = Field(None, description="教学重点")  # 教学重点
    difficult_points: Optional[str] = Field(None, description="教学难点")  # 教学难点


class ContentGenerationRequest(BaseModel):
    """内容生成请求模型 - 发送给大模型的内容生成请求"""
    course_info: CourseBasicInfo = Field(..., description="课程基本信息")  # 课程信息
    content_types: List[ContentType] = Field(..., description="需要生成的内容类型列表")  # 内容类型列表
    use_knowledge_base: bool = Field(default=True, description="是否启用知识库检索增强")  # 是否使用RAG
    style_preference: Optional[str] = Field("standard", description="内容风格偏好")  # 风格偏好
    additional_instructions: Optional[str] = Field(None, description="补充指令")  # 补充指令


# ==================== 内容相关模型 ====================

class ResourceReference(BaseModel):
    """资源引用模型 - 记录教案中引用的资源信息"""
    resource_id: str = Field(..., description="资源唯一标识")  # 资源ID
    title: str = Field(..., description="资源标题")  # 资源标题
    resource_type: ResourceType = Field(..., description="资源类型")  # 资源类型
    url: Optional[str] = Field(None, description="资源链接")  # 资源链接
    citation_text: str = Field(..., description="引用文本")  # 引用格式文本


class GeneratedContent(BaseModel):
    """生成内容模型 - 大模型生成的教学内容结构"""
    content_id: str = Field(..., description="内容唯一标识")  # 内容ID
    content_type: ContentType = Field(..., description="内容类型")  # 内容类型
    title: str = Field(..., description="内容标题")  # 内容标题
    raw_content: str = Field(..., description="原始生成内容(Markdown)")  # 原始Markdown内容
    structured_content: Optional[Dict[str, Any]] = Field(None, description="结构化内容")  # 结构化数据
    references: List[ResourceReference] = Field(default_factory=list, description="引用资源列表")  # 引用列表
    generated_at: datetime = Field(default_factory=datetime.now, description="生成时间")  # 生成时间
    model_used: str = Field(default="deepseek-chat", description="使用的模型")  # 使用的模型名称


class ContentVersion(BaseModel):
    """内容版本模型 - 每次编辑保存的版本快照"""
    version_id: str = Field(..., description="版本唯一标识")  # 版本ID
    content_id: str = Field(..., description="关联的内容ID")  # 内容ID
    version_number: int = Field(..., ge=1, description="版本号")  # 版本号，从1开始
    content_snapshot: str = Field(..., description="内容快照")  # 内容快照
    editor_id: str = Field(..., description="编辑者ID")  # 编辑者ID
    change_summary: Optional[str] = Field(None, description="变更摘要")  # 变更说明
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")  # 创建时间


class ExportRequest(BaseModel):
    """导出请求模型 - 内容导出为文档的请求参数"""
    content_ids: List[str] = Field(..., description="要导出的内容ID列表")  # 内容ID列表
    export_format: ExportFormat = Field(..., description="导出格式")  # 导出格式
    include_references: bool = Field(default=True, description="是否包含引用")  # 是否包含引用
    template_id: Optional[str] = Field(None, description="模板ID")  # 文档模板ID


# ==================== 检索相关模型 ====================

class ResourceSearchRequest(BaseModel):
    """资源检索请求模型 - 知识库和网络资源检索"""
    query: str = Field(..., min_length=2, description="检索关键词")  # 检索关键词
    resource_types: Optional[List[ResourceType]] = Field(None, description="资源类型过滤")  # 类型过滤
    max_results: int = Field(default=10, ge=1, le=50, description="最大返回数")  # 最大结果数
    use_semantic_search: bool = Field(default=True, description="是否使用语义搜索")  # 是否语义搜索


class SearchResult(BaseModel):
    """检索结果模型 - 单条检索结果"""
    resource_id: str = Field(..., description="资源ID")  # 资源ID
    title: str = Field(..., description="资源标题")  # 标题
    snippet: str = Field(..., description="内容摘要")  # 内容摘要
    resource_type: ResourceType = Field(..., description="资源类型")  # 资源类型
    relevance_score: float = Field(..., ge=0, le=1, description="相关性分数")  # 相关性分数
    source_url: Optional[str] = Field(None, description="来源URL")  # 来源链接


# ==================== 通用响应模型 ====================

class APIResponse(BaseModel):
    """通用API响应模型 - 统一后端接口返回格式"""
    code: int = Field(default=200, description="状态码")  # HTTP状态码
    message: str = Field(default="success", description="响应消息")  # 响应消息
    data: Optional[Any] = Field(None, description="响应数据")  # 响应数据


class PaginatedResponse(APIResponse):
    """分页响应模型 - 继承通用响应，增加分页信息"""
    total: int = Field(default=0, description="总记录数")  # 总记录数
    page: int = Field(default=1, description="当前页码")  # 当前页
    page_size: int = Field(default=20, description="每页条数")  # 每页大小


# ==================== 协同编辑模型 ====================

class CollaborationSession(BaseModel):
    """协同编辑会话模型 - 多人协同编辑的会话信息"""
    session_id: str = Field(..., description="会话唯一标识")  # 会话ID
    content_id: str = Field(..., description="编辑的内容ID")  # 内容ID
    participants: List[str] = Field(default_factory=list, description="参与者用户ID列表")  # 参与者列表
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")  # 创建时间
    last_activity: datetime = Field(default_factory=datetime.now, description="最后活动时间")  # 最后活动
    is_active: bool = Field(default=True, description="会话是否活跃")  # 是否活跃
