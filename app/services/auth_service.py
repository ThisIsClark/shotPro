"""
Authentication Service Module
认证服务：Token 验证、用户信息获取
"""

from typing import Optional, Dict, Any

from .supabase_client import verify_token, get_user_from_token


class AuthService:
    """认证服务"""

    @staticmethod
    async def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
        """
        验证访问 Token

        Args:
            token: JWT Token 字符串

        Returns:
            用户信息字典，验证失败返回 None
        """
        return await verify_token(token)

    @staticmethod
    async def get_user_id_from_token(token: str) -> Optional[str]:
        """
        从 Token 获取用户 ID

        Args:
            token: JWT Token 字符串

        Returns:
            用户 ID 字符串，验证失败返回 None
        """
        return get_user_from_token(token)

    @staticmethod
    async def get_current_user(token: str) -> Optional[Dict[str, Any]]:
        """
        获取当前用户信息

        Args:
            token: JWT Token 字符串

        Returns:
            用户信息字典
        """
        user_info = await verify_token(token)
        if user_info:
            return {
                "id": user_info["id"],
                "email": user_info["email"],
                "email_verified": user_info.get("email_verified", False),
            }
        return None

    @staticmethod
    def extract_token_from_header(auth_header: str) -> Optional[str]:
        """
        从 Authorization header 提取 Token

        Args:
            auth_header: Authorization header 值（如 "Bearer xxx"）

        Returns:
            Token 字符串
        """
        if not auth_header:
            return None

        if auth_header.startswith("Bearer "):
            return auth_header[7:]

        return auth_header


# 单例实例
auth_service = AuthService()