"""
API Dependencies Module
API 依赖注入：认证、用户获取
"""

from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ..services.auth_service import auth_service
from ..services.supabase_client import is_supabase_enabled


# HTTP Bearer 认证方案
security = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[dict]:
    """
    获取当前用户（可选，未登录返回 None）

    用于支持匿名用户上传，同时可选绑定已登录用户
    """
    if not is_supabase_enabled():
        return None

    if not credentials:
        return None

    token = credentials.credentials
    user_info = await auth_service.verify_access_token(token)

    return user_info


async def get_current_user_required(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> dict:
    """
    获取当前用户（必须认证）

    用于需要用户身份的接口，如历史记录、用户设置等
    """
    if not is_supabase_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is not configured"
        )

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials
    user_info = await auth_service.verify_access_token(token)

    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return user_info


# 用户 ID 提取辅助函数
def get_user_id(user_info: Optional[dict]) -> Optional[str]:
    """从用户信息字典提取用户 ID"""
    if user_info:
        return user_info.get("id")
    return None