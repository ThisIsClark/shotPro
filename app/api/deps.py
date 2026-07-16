"""
API Dependencies Module
API 依赖注入：认证、用户获取（支持 Supabase Token + 本地 JWT）
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..services.auth_service import auth_service
from ..services.jwt_service import jwt_service
from ..services.supabase_client import is_supabase_enabled


# HTTP Bearer 认证方案
security = HTTPBearer(auto_error=False)


async def _verify_local_token(token: str) -> Optional[dict]:
    """验证本地 JWT，返回用户信息或 None"""
    return jwt_service.verify_token(token)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """
    获取当前用户（可选，未登录返回 None）

    优先尝试 Supabase Token，失败后尝试本地 JWT
    """
    if not credentials:
        return None

    token = credentials.credentials

    # 1. 尝试 Supabase Token
    if is_supabase_enabled():
        user_info = await auth_service.verify_access_token(token)
        if user_info:
            return user_info

    # 2. 尝试本地 JWT
    user_info = await _verify_local_token(token)
    return user_info


async def get_current_user_required(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> dict:
    """
    获取当前用户（必须认证）

    优先尝试 Supabase Token，失败后尝试本地 JWT
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials

    # 1. 尝试 Supabase Token
    if is_supabase_enabled():
        user_info = await auth_service.verify_access_token(token)
        if user_info:
            return user_info

    # 2. 尝试本地 JWT
    user_info = await _verify_local_token(token)
    if user_info:
        return user_info

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"}
    )


async def require_admin(
    user: dict = Depends(get_current_user_required)
) -> dict:
    """
    要求当前用户是管理员（role == "admin"）。

    用于保护管理类端点（如模板创建）。复用现有 local_auth_service JWT 体系：
    admin 登录后 JWT payload 里带 role: "admin"（见 auth.py local-login）。
    """
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin only",
        )
    return user


# 用户 ID 提取辅助函数
def get_user_id(user_info: Optional[dict]) -> Optional[str]:
    """从用户信息字典提取用户 ID"""
    if user_info:
        return user_info.get("id")
    return None
