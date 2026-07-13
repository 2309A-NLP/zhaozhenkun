# -*- coding: utf-8 -*-
# 工单编号：人工智能NLP-Agent数字人项目-17-教育Agent任务工单-教学场景功能分析及智能备课
# 模块：核心路由 - 系统状态与用户认证接口

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from auth import auth_service
from config import get_settings
from knowledge_base import knowledge_base_service
from schemas import LoginRequest

router = APIRouter()


@router.get("/api/v1/system/info", tags=["系统"], summary="获取系统基础信息")
async def root():
    """系统根路径 - 返回服务基本信息"""
    return {
        "app": "教育Agent智能备课系统",
        "version": "1.0.0",
        "work_order": get_settings().WORK_ORDER_ID[:50],
        "status": "running",
        "docs": "/docs",
    }


@router.get("/health", tags=["系统"])
async def health_check():
    """健康检查接口 - 返回各服务组件状态"""
    kb_stats = knowledge_base_service.get_statistics()
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "knowledge_base": {"status": "ok", "documents": kb_stats["total_documents"]},
            "ai_model": {"status": "ok", "model": get_settings().DEEPSEEK_MODEL},
            "multimodal": {"status": "ok", "model": get_settings().QWEN_MODEL},
        },
    }


@router.post("/api/v1/auth/login", tags=["认证"], summary="用户登录")
async def login(req: LoginRequest):
    """用户登录接口 - 通过POST body验证用户名密码并返回JWT令牌"""
    user = auth_service.authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    token = auth_service.create_access_token(user)
    return {
        "code": 200,
        "message": "登录成功",
        "data": {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": get_settings().JWT_EXPIRE_MINUTES * 60,
            "user_info": {
                "user_id": user["user_id"],
                "username": user["username"],
                "role": user["role"],
                "display_name": user["display_name"],
            },
        },
    }


@router.post("/api/v1/auth/demo-login", tags=["认证"], summary="演示账号免密登录")
async def demo_login():
    """演示账号免密登录接口 - 直接签发教师演示账号令牌"""
    user = auth_service.get_demo_user("teacher01")
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="演示账号不存在")
    token = auth_service.create_access_token(user)
    return {
        "code": 200,
        "message": "演示登录成功",
        "data": {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": get_settings().JWT_EXPIRE_MINUTES * 60,
            "user_info": {
                "user_id": user["user_id"],
                "username": user["username"],
                "role": user["role"],
                "display_name": user["display_name"],
            },
        },
    }


@router.get("/api/v1/auth/me", tags=["认证"], summary="获取当前用户信息")
async def get_current_user(current_user: dict = Depends(auth_service.get_current_user)):
    """获取当前用户信息 - 从JWT令牌解析用户身份"""
    return {"code": 200, "data": current_user}
