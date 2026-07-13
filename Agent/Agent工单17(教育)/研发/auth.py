# -*- coding: utf-8 -*-
# 工单编号：人工智能NLP-Agent数字人项目-17-教育Agent任务工单-教学场景功能分析及智能备课
# 模块：用户认证模块 - JWT令牌签发、验证、用户身份管理
# 创建时间：2025年6月
# 作者：Agent智能备课系统开发组

import base64
import hashlib
import hmac
import json

try:
    from jose import jwt  # python-jose库，用于JWT令牌的生成和解析
    from jose.exceptions import ExpiredSignatureError, JWTError
except ImportError:
    jwt = None
    ExpiredSignatureError = Exception
    JWTError = Exception
import bcrypt  # Bcrypt库，用于密码的安全哈希
from datetime import datetime, timedelta, timezone  # 时间处理
from typing import Optional, Dict  # 类型提示
from fastapi import HTTPException, Depends, status  # FastAPI异常和依赖注入
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials  # HTTP Bearer认证
from pydantic import BaseModel  # 数据模型

from config import get_settings  # 导入系统配置

# 创建Bearer认证安全方案实例
security_scheme = HTTPBearer(auto_error=False)  # auto_error=False允许匿名访问


class AuthService:
    """认证服务类 - 处理用户注册、登录、Token管理和权限验证"""

    def __init__(self):
        """初始化认证服务 - 加载配置和模拟用户数据（生产环境应使用数据库）"""
        self.settings = get_settings()  # 获取系统配置
        self.secret_key = self.settings.JWT_SECRET_KEY  # JWT签名密钥
        self.algorithm = self.settings.JWT_ALGORITHM  # JWT签名算法
        self.expire_minutes = self.settings.JWT_EXPIRE_MINUTES  # Token过期分钟数
        # 演示用户的预计算密码哈希（避免bcrypt在模块导入时阻塞启动）
        # 生产环境密码哈希从数据库读取，无此性能问题
        self._demo_users: Dict[str, dict] = {}  # 延迟初始化用户数据
        self._demo_initialized = False  # 延迟初始化标志

    def _init_demo_users(self) -> None:
        """延迟初始化演示用户 - 仅在首次登录时计算密码哈希，避免模块导入时卡顿"""
        if self._demo_initialized:  # 已初始化
            return  # 跳过
        self._demo_users = {
            "teacher01": {  # 演示教师账号
                "username": "teacher01",
                "password_hash": self._hash_password("123456"),  # 密码哈希（首次计算约200ms）
                "user_id": "u_001",
                "role": "teacher",
                "display_name": "张老师",
                "department": "人工智能系",
            },
            "admin": {  # 演示管理员账号
                "username": "admin",
                "password_hash": self._hash_password("admin123"),
                "user_id": "u_admin",
                "role": "admin",
                "display_name": "系统管理员",
                "department": "教务处",
            },
        }
        self._demo_initialized = True  # 标记已初始化

    def _hash_password(self, password: str) -> str:
        """密码哈希 - 使用bcrypt算法对明文密码进行安全哈希处理"""
        salt = bcrypt.gensalt(rounds=12)  # 生成随机盐值，12轮加密
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)  # 执行bcrypt哈希
        return hashed.decode("utf-8")  # 返回哈希字符串

    def _verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """密码验证 - 验证明文密码是否与哈希值匹配"""
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )

    def _encode_segment(self, value) -> str:
        raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")

    def _decode_segment(self, value: str):
        padding = "=" * (-len(value) % 4)
        raw = base64.urlsafe_b64decode((value + padding).encode("utf-8"))
        return json.loads(raw.decode("utf-8"))

    def _encode_fallback_token(self, payload: dict) -> str:
        header = {"alg": "HS256", "typ": "JWT"}
        signing_input = f"{self._encode_segment(header)}.{self._encode_segment(payload)}"
        signature = hmac.new(self.secret_key.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest()
        return f"{signing_input}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode('utf-8')}"

    def _decode_fallback_token(self, token: str) -> dict:
        try:
            header, payload, signature = token.split(".")
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证令牌") from error
        signing_input = f"{header}.{payload}"
        expected_signature = hmac.new(
            self.secret_key.encode("utf-8"),
            signing_input.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        encoded_expected = base64.urlsafe_b64encode(expected_signature).rstrip(b"=").decode("utf-8")
        if not hmac.compare_digest(signature, encoded_expected):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证令牌")
        payload_data = self._decode_segment(payload)
        if int(payload_data.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌已过期，请重新登录")
        return payload_data

    def authenticate_user(self, username: str, password: str) -> Optional[dict]:
        """用户认证 - 验证用户名密码，成功返回用户信息，失败返回None"""
        self._init_demo_users()  # 延迟初始化演示用户（首次调用时才计算bcrypt哈希）
        user = self._demo_users.get(username)  # 查找用户（生产环境查数据库）
        if not user:  # 用户不存在
            return None  # 返回None表示认证失败
        if not self._verify_password(password, user["password_hash"]):  # 密码不正确
            return None  # 返回None表示认证失败
        return {k: v for k, v in user.items() if k != "password_hash"}  # 返回不含密码的用户信息

    def get_demo_user(self, username: str = "teacher01") -> Optional[dict]:
        """获取演示用户 - 免密返回预置演示账号信息"""
        self._init_demo_users()
        user = self._demo_users.get(username)
        return {k: v for k, v in user.items() if k != "password_hash"} if user else None

    def create_access_token(self, user_data: dict) -> str:
        """创建JWT令牌 - 根据用户信息生成签名的访问令牌"""
        issued_at = datetime.now(timezone.utc)
        expire = issued_at + timedelta(minutes=self.expire_minutes)
        payload = {
            "sub": user_data["user_id"],
            "username": user_data["username"],
            "role": user_data["role"],
            "display_name": user_data.get("display_name", ""),
            "iat": int(issued_at.timestamp()),
            "exp": int(expire.timestamp()),
            "work_order": self.settings.WORK_ORDER_ID[:50],
        }
        if jwt is None:
            return self._encode_fallback_token(payload)
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def decode_access_token(self, token: str) -> dict:
        """解码JWT令牌 - 验证并解析令牌，返回载荷数据"""
        if jwt is None:
            return self._decode_fallback_token(token)
        try:
            return jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
        except ExpiredSignatureError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌已过期，请重新登录")
        except JWTError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证令牌")

    def get_current_user(self, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme)) -> dict:
        """获取当前用户 - FastAPI依赖注入，从请求Header解析用户身份"""
        if not credentials:  # 没有提供认证信息
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请提供认证令牌")
        token = credentials.credentials  # 提取Bearer Token
        payload = self.decode_access_token(token)  # 解码验证令牌
        return {  # 返回标准化的用户信息
            "user_id": payload["sub"],
            "username": payload["username"],
            "role": payload["role"],
            "display_name": payload.get("display_name", ""),
        }

    def require_role(self, allowed_roles: list):
        """角色权限验证 - 返回依赖注入函数，验证当前用户是否属于允许的角色"""
        async def role_checker(current_user: dict = Depends(self.get_current_user)) -> dict:
            """内层权限检查函数 - 检查用户角色是否在允许列表中"""
            if current_user["role"] not in allowed_roles:  # 角色不在允许列表
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足，无法执行此操作")
            return current_user  # 返回当前用户信息
        return role_checker  # 返回依赖注入函数


# 全局认证服务单例
auth_service = AuthService()  # 创建全局唯一的认证服务实例
