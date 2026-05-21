"""
Supabase Client Module
Supabase 客户端初始化和工具函数
"""

from supabase import create_client, Client
from typing import Optional, Dict, Any
from functools import lru_cache

from ..config import settings


@lru_cache()
def get_supabase_client() -> Optional[Client]:
    """
    获取 Supabase 客户端（使用 service_role key，有更高权限）
    用于后端数据库操作
    """
    if not settings.supabase_url or not settings.supabase_service_key:
        return None

    return create_client(
        settings.supabase_url,
        settings.supabase_service_key
    )


@lru_cache()
def get_supabase_client_anon() -> Optional[Client]:
    """
    获取 Supabase 客户端（使用 anon key，权限较低）
    用于验证用户 Token
    """
    if not settings.supabase_url or not settings.supabase_anon_key:
        return None

    return create_client(
        settings.supabase_url,
        settings.supabase_anon_key
    )


def is_supabase_enabled() -> bool:
    """检查 Supabase 是否已配置"""
    return bool(settings.supabase_url and settings.supabase_service_key)


async def verify_token(token: str) -> Optional[Dict[str, Any]]:
    """
    验证 Supabase JWT Token，返回用户信息

    Args:
        token: JWT Token 字符串

    Returns:
        用户信息字典，包含 id, email 等；验证失败返回 None
    """
    client = get_supabase_client_anon()
    if not client:
        return None

    try:
        # 使用 Supabase 的 get_user 方法验证 token
        response = client.auth.get_user(token)
        if response and response.user:
            return {
                "id": response.user.id,
                "email": response.user.email,
                "email_verified": response.user.email_confirmed_at is not None,
                "created_at": response.user.created_at,
                "last_sign_in_at": response.user.last_sign_in_at,
            }
        return None
    except Exception as e:
        print(f"[Supabase] Token verification failed: {e}")
        return None


def get_user_from_token(token: str) -> Optional[str]:
    """
    从 Token 中提取用户 ID

    Args:
        token: JWT Token 字符串

    Returns:
        用户 ID 字符串，验证失败返回 None
    """
    user_info = verify_token(token)
    if user_info:
        return user_info.get("id")
    return None