# -*- coding: utf-8 -*-
# 工单编号：人工智能NLP-Agent数字人项目-17-教育Agent任务工单-教学场景功能分析及智能备课
# 模块：数据库设计 - 定义系统所有数据表结构与索引策略
# 创建时间：2025年6月
# 作者：Agent智能备课系统开发组

from sqlalchemy import (Column, Integer, String, Text, Float,     # SQLAlchemy核心字段类型
                        Boolean, DateTime, ForeignKey, Enum,      # 枚举、外键、时间类型
                        JSON, Index, UniqueConstraint)            # JSON字段与索引
from sqlalchemy.ext.declarative import declarative_base           # 声明式基类
from sqlalchemy.orm import relationship                           # ORM关系映射
from sqlalchemy.sql import func                                   # SQL函数
from datetime import datetime                                     # 时间处理
import uuid                                                       # 唯一ID生成

Base = declarative_base()  # 声明式ORM基类


def generate_uuid():
    """生成唯一ID的辅助函数 - 使用UUID4保证全局唯一"""
    return str(uuid.uuid4())  # 返回UUID字符串


# ==================== 用户表 ====================
class User(Base):
    """用户表 - 存储系统所有用户信息"""
    __tablename__ = "users"  # 表名
    __table_args__ = (Index("idx_user_username", "username"),  # 用户名索引（登录查询优化）
                      Index("idx_user_role", "role"))           # 角色索引（权限查询优化）

    user_id = Column(String(64), primary_key=True, default=generate_uuid)  # 用户主键
    username = Column(String(50), unique=True, nullable=False, index=True)  # 登录名，唯一
    password_hash = Column(String(256), nullable=False)  # 密码哈希（bcrypt）
    display_name = Column(String(100), nullable=False)  # 显示名称
    role = Column(String(20), nullable=False, default="teacher")  # 角色：teacher/admin/student
    department = Column(String(100), nullable=True)  # 所属部门
    email = Column(String(200), nullable=True)  # 邮箱
    is_active = Column(Boolean, default=True)  # 账号是否激活
    created_at = Column(DateTime, server_default=func.now())  # 创建时间
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())  # 更新时间


# ==================== 课程信息表 ====================
class Course(Base):
    """课程信息表 - 存储课程基本信息"""
    __tablename__ = "courses"

    course_id = Column(String(64), primary_key=True, default=generate_uuid)  # 课程主键
    teacher_id = Column(String(64), ForeignKey("users.user_id"), nullable=False)  # 教师外键
    course_name = Column(String(200), nullable=False)  # 课程名称
    chapter = Column(String(200), nullable=False)  # 章节名称
    grade_level = Column(String(50), nullable=False)  # 适用年级
    subject = Column(String(100), nullable=False)  # 所属学科
    teaching_objectives = Column(Text, nullable=False)  # 教学目标
    class_hours = Column(Integer, default=1)  # 课时数
    key_points = Column(Text, nullable=True)  # 教学重点
    difficult_points = Column(Text, nullable=True)  # 教学难点
    created_at = Column(DateTime, server_default=func.now())  # 创建时间


# ==================== 生成内容表 ====================
class GeneratedContent(Base):
    """生成内容表 - 存储大模型生成的教案/课件/习题等"""
    __tablename__ = "generated_contents"
    __table_args__ = (Index("idx_content_course", "course_id"),  # 课程维度查询索引
                      Index("idx_content_type", "content_type"),  # 类型维度查询索引
                      Index("idx_content_created", "created_at"))  # 时间维度查询索引

    content_id = Column(String(64), primary_key=True, default=generate_uuid)  # 内容主键
    course_id = Column(String(64), ForeignKey("courses.course_id"), nullable=False)  # 课程外键
    teacher_id = Column(String(64), ForeignKey("users.user_id"), nullable=False)  # 创建教师外键
    content_type = Column(String(30), nullable=False)  # 内容类型：lesson_plan/courseware等
    title = Column(String(500), nullable=False)  # 内容标题
    raw_content = Column(Text, nullable=False)  # Markdown原始内容
    structured_content = Column(JSON, nullable=True)  # 结构化内容数据
    model_used = Column(String(100), default="deepseek-chat")  # 生成使用的模型
    style_preferences = Column(JSON, nullable=True)  # 风格偏好设置
    generation_config = Column(JSON, nullable=True)  # 生成时的配置参数
    is_published = Column(Boolean, default=False)  # 是否已发布
    created_at = Column(DateTime, server_default=func.now())  # 创建时间
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())  # 更新时间


# ==================== 内容版本表 ====================
class ContentVersion(Base):
    """内容版本表 - 存储每次编辑的版本快照，支持历史回溯"""
    __tablename__ = "content_versions"

    version_id = Column(String(64), primary_key=True, default=generate_uuid)  # 版本主键
    content_id = Column(String(64), ForeignKey("generated_contents.content_id"), nullable=False)  # 内容外键
    version_number = Column(Integer, nullable=False)  # 版本号（自增）
    content_snapshot = Column(Text, nullable=False)  # 内容快照
    editor_id = Column(String(64), ForeignKey("users.user_id"), nullable=False)  # 编辑者外键
    change_summary = Column(String(500), nullable=True)  # 变更摘要
    created_at = Column(DateTime, server_default=func.now())  # 创建时间
    __table_args__ = (UniqueConstraint("content_id", "version_number",  # 同一内容版本号唯一
                                       name="uq_content_version"),)


# ==================== 知识库资源表 ====================
class KnowledgeResource(Base):
    """知识库资源表 - 存储校本教材、网络资源等"""
    __tablename__ = "knowledge_resources"
    __table_args__ = (Index("idx_resource_type", "resource_type"),  # 资源类型索引
                      Index("idx_resource_embedding", "embedding_id"))  # 向量ID索引

    resource_id = Column(String(64), primary_key=True, default=generate_uuid)  # 资源主键
    title = Column(String(500), nullable=False)  # 资源标题
    content = Column(Text, nullable=False)  # 资源原始内容
    resource_type = Column(String(30), nullable=False)  # 资源类型
    tags = Column(JSON, nullable=True)  # 标签列表
    source_url = Column(String(1000), nullable=True)  # 来源URL
    uploader_id = Column(String(64), ForeignKey("users.user_id"))  # 上传者外键
    embedding_id = Column(String(64), nullable=True, index=True)  # 向量存储ID（FAISS索引）
    chunk_index = Column(Integer, nullable=True)  # 分块索引（长文本分块）
    metadata_extra = Column(JSON, nullable=True)  # 扩展元数据
    created_at = Column(DateTime, server_default=func.now())  # 创建时间


# ==================== 资源引用表 ====================
class ResourceCitation(Base):
    """资源引用表 - 记录教案中引用的资源关联"""
    __tablename__ = "resource_citations"

    citation_id = Column(String(64), primary_key=True, default=generate_uuid)  # 引用主键
    content_id = Column(String(64), ForeignKey("generated_contents.content_id"), nullable=False)  # 内容外键
    resource_id = Column(String(64), ForeignKey("knowledge_resources.resource_id"), nullable=False)  # 资源外键
    citation_text = Column(String(500), nullable=False)  # 引用格式文本
    position_in_content = Column(Integer, nullable=True)  # 在内容中的位置


# ==================== 导出记录表 ====================
class ExportRecord(Base):
    """导出记录表 - 记录每次文档导出的信息"""
    __tablename__ = "export_records"

    export_id = Column(String(64), primary_key=True, default=generate_uuid)  # 导出主键
    user_id = Column(String(64), ForeignKey("users.user_id"), nullable=False)  # 导出用户外键
    content_ids = Column(JSON, nullable=False)  # 导出内容ID列表
    export_format = Column(String(20), nullable=False)  # 导出格式
    file_path = Column(String(500), nullable=False)  # 服务器文件路径
    file_size = Column(Integer, default=0)  # 文件大小（字节）
    download_count = Column(Integer, default=0)  # 下载次数
    created_at = Column(DateTime, server_default=func.now())  # 创建时间


# ==================== 协同编辑会话表 ====================
class CollaborationSession(Base):
    """协同编辑会话表 - 存储多人协同编辑会话状态"""
    __tablename__ = "collaboration_sessions"

    session_id = Column(String(64), primary_key=True, default=generate_uuid)  # 会话主键
    content_id = Column(String(64), ForeignKey("generated_contents.content_id"), nullable=False)  # 内容外键
    participant_ids = Column(JSON, default=list)  # 参与者用户ID列表
    is_active = Column(Boolean, default=True)  # 会话是否活跃
    created_at = Column(DateTime, server_default=func.now())  # 创建时间
    last_activity = Column(DateTime, server_default=func.now())  # 最后活动时间


# ==================== 向量索引表 (FAISS) ====================
class VectorIndex(Base):
    """向量索引表 - 管理FAISS向量存储的元数据"""
    __tablename__ = "vector_indices"

    index_id = Column(String(64), primary_key=True, default=generate_uuid)  # 索引主键
    index_name = Column(String(200), nullable=False)  # 索引名称
    index_type = Column(String(50), default="faiss_flat")  # 索引类型
    dimension = Column(Integer, default=1024)  # 向量维度（千问text-embedding-v3）
    total_vectors = Column(Integer, default=0)  # 向量总数
    index_file_path = Column(String(500), nullable=False)  # FAISS索引文件路径
    embedding_model = Column(String(100), default="text-embedding-3-small")  # 嵌入模型
    created_at = Column(DateTime, server_default=func.now())  # 创建时间
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())  # 更新时间


# ==================== 数据库设计说明 ====================
# 1. 主键使用UUID字符串，支持分布式部署时的全局唯一性
# 2. JSON字段存储灵活的结构化数据（标签、配置、参与人等）
# 3. 向量索引独立管理，支持FAISS/Milvus等多种向量数据库切换
# 4. 内容与版本分离存储，版本快照支持完整历史回溯
# 5. 所有表包含创建/更新时间，支持审计追溯
# 6. 外键约束保证数据完整性，级联策略在应用层控制
# 7. 索引策略覆盖高频查询场景：用户名、内容类型、时间范围
