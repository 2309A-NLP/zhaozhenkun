# -*- coding: utf-8 -*-
# 工单编号：人工智能NLP-Agent数字人项目-17-教育Agent任务工单-教学场景功能分析及智能备课
# 模块：API接口设计 - 定义系统所有RESTful API端点
# 创建时间：2025年6月
# 作者：Agent智能备课系统开发组

from fastapi import APIRouter, Depends, UploadFile, File, Query  # FastAPI路由和依赖注入
from typing import List, Optional  # 类型提示

# =====================================================================
# API设计文档 - 智能备课系统接口规范
# 基础路径：/api/v1
# 认证方式：Bearer Token (JWT)
# 数据格式：JSON
# =====================================================================

# -------------------- 1. 用户认证模块 /api/v1/auth --------------------
# 功能：用户登录、Token刷新、用户信息获取

# POST   /api/v1/auth/login                    # 用户登录，返回JWT令牌
#   Request:  { username: str, password: str }
#   Response: { access_token, token_type, expires_in, user_info }

# POST   /api/v1/auth/refresh                  # 刷新Token
#   Header:   Authorization: Bearer <token>
#   Response: { access_token, expires_in }

# GET    /api/v1/auth/me                        # 获取当前用户信息
#   Header:   Authorization: Bearer <token>
#   Response: { user_id, username, role, display_name }

# POST   /api/v1/auth/logout                   # 用户登出（Token加入黑名单）
#   Header:   Authorization: Bearer <token>


# -------------------- 2. 智能备课模块 /api/v1/lesson-prep --------------------
# 功能：核心智能备课功能，内容生成与编辑

# POST   /api/v1/lesson-prep/generate           # 生成教学内容（调用大模型+知识库）
#   Request:  { course_info: {...}, content_types: [...], use_knowledge_base: bool }
#   Response: { content_id, content_type, title, raw_content, references }

# PUT    /api/v1/lesson-prep/content/{content_id}  # 更新编辑后的内容
#   Request:  { raw_content: str, structured_content: {...} }

# GET    /api/v1/lesson-prep/content/{content_id}  # 获取单个内容详情
#   Response: { content_id, content_type, title, raw_content, references, versions }

# GET    /api/v1/lesson-prep/contents            # 获取内容列表（分页、按类型筛选）
#   Query:    content_type?, page?, page_size?, keyword?
#   Response: { items: [...], total, page, page_size }

# DELETE /api/v1/lesson-prep/content/{content_id}  # 删除指定内容

# POST   /api/v1/lesson-prep/content/{content_id}/clone  # 克隆/复制内容


# -------------------- 3. 知识库与资源检索 /api/v1/knowledge --------------------
# 功能：知识库管理、资源检索与引用

# POST   /api/v1/knowledge/search               # 检索知识库和网络资源
#   Request:  { query, resource_types?, max_results, use_semantic_search }
#   Response: { results: [{resource_id, title, snippet, relevance_score}] }

# POST   /api/v1/knowledge/upload               # 上传教材/资源到知识库
#   Request:  Multipart: file + metadata{ title, resource_type, tags }

# GET    /api/v1/knowledge/resources            # 获取知识库资源列表
#   Query:    resource_type?, page?, page_size?

# DELETE /api/v1/knowledge/resource/{resource_id}  # 删除知识库资源

# POST   /api/v1/knowledge/resource/{resource_id}/cite  # 生成资源引用文本
#   Response: { citation_text, resource_id, title }


# -------------------- 4. 内容导出模块 /api/v1/export --------------------
# 功能：多格式文档导出与推送

# POST   /api/v1/export/convert                 # 将内容导出为指定格式文档
#   Request:  { content_ids, export_format, include_references, template_id? }
#   Response: { download_url, file_name, file_size, format }

# GET    /api/v1/export/download/{file_id}      # 下载导出文件
#   Response: Binary file stream

# POST   /api/v1/export/push                    # 一键推送到教学平台
#   Request:  { content_ids, target_platform, api_endpoint }


# -------------------- 5. 版本管理模块 /api/v1/version --------------------
# 功能：内容版本历史管理

# GET    /api/v1/version/content/{content_id}/versions  # 获取某内容的所有版本
#   Response: { versions: [{version_id, version_number, created_at, editor}] }

# GET    /api/v1/version/{version_id}            # 获取指定版本的快照
#   Response: { version_id, content_snapshot, created_at }

# POST   /api/v1/version/content/{content_id}/restore/{version_id}  # 恢复历史版本
#   Response: { content_id, restored_from_version }

# POST   /api/v1/version/compare                # 对比两个版本差异
#   Request:  { version_id_a, version_id_b }
#   Response: { diff_result: str }


# -------------------- 6. 协同编辑模块 /api/v1/collaboration --------------------
# 功能：多人实时协同编辑（WebSocket）

# WS     /ws/collaboration/{content_id}          # WebSocket连接（协同编辑）
#   Protocol: 连接时发送 { action: "join", user_id, username }
#            编辑时发送 { action: "edit", delta, cursor_position }
#            离开时发送 { action: "leave" }
#            服务端广播 { action: "update", user_id, delta }
#            服务端广播 { action: "cursor", user_id, position }

# POST   /api/v1/collaboration/session/create   # 创建协同编辑会话
#   Request:  { content_id }
#   Response: { session_id, content_id }

# POST   /api/v1/collaboration/session/{session_id}/join  # 加入会话
# POST   /api/v1/collaboration/session/{session_id}/leave  # 离开会话

# GET    /api/v1/collaboration/session/{session_id}/participants  # 获取参与者列表


# -------------------- 7. 多媒体资源模块 /api/v1/media --------------------
# 功能：多媒体文件上传与管理

# POST   /api/v1/media/upload                    # 上传图片/视频/音频
#   Request:  Multipart: file
#   Response: { media_id, url, file_type, file_size }

# GET    /api/v1/media/list                       # 获取已上传的多媒体列表


# =====================================================================
# 接口设计说明：
# 1. 所有接口遵循RESTful风格，使用标准HTTP方法
# 2. 除登录接口外，所有接口需要在Header携带Authorization: Bearer <token>
# 3. 分页接口默认page=1, page_size=20，最大page_size=100
# 4. 所有时间字段使用ISO 8601格式（UTC）
# 5. 错误响应统一格式：{ code: int, message: str, detail: str }
# 6. 大模型生成接口为异步模式，长时间任务返回task_id用于轮询
# =====================================================================
