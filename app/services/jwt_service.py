"""
JWT Service Module
本地 JWT 签发与验证：用于管理员账号认证
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from jose import jwt, JWTError

from ..config import settings


class JWTService:
    """本地 JWT 服务"""

    ALGORITHM = "HS256"
    TOKEN_EXPIRE_HOURS = 24

    @staticmethod
    def create_token(user_info: Dict[str, Any]) -> str:
        """
        签发 JWT

        Args:
            user_info: 用户信息，必须包含 id，可选 role/is_local/email

        Returns:
            JWT 字符串
        """
        now = datetime.now(timezone.utc)
        payload = {
            "sub": user_info["id"],
            "role": user_info.get("role", "user"),
            "is_local": user_info.get("is_local", False),
            "email": user_info.get("email", ""),
            "iat": now,
            "exp": now + timedelta(hours=JWTService.TOKEN_EXPIRE_HOURS),
        }
        return jwt.encode(payload, settings.jwt_secret, algorithm=JWTService.ALGORITHM)

    @staticmethod
    def verify_token(token: str) -> Optional[Dict[str, Any]]:
        """
        验证 JWT，返回用户信息或 None

        Args:
            token: JWT 字符串

        Returns:
            用户信息字典，验证失败返回 None
        """
        try:
            payload = jwt.decode(
                token, settings.jwt_secret, algorithms=[JWTService.ALGORITHM]
            )
            return {
                "id": payload["sub"],
                "role": payload.get("role", "user"),
                "is_local": payload.get("is_local", False),
                "email": payload.get("email", ""),
            }
        except (JWTError, KeyError):
            return None


jwt_service = JWTService()
