"""
Authentication API Routes
认证 API 路由
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..deps import get_current_user_required
from ...services.supabase_client import get_supabase_client_anon, is_supabase_enabled

router = APIRouter(prefix="/auth", tags=["authentication"])


# ===== Request/Response Models =====

class TokenVerifyRequest(BaseModel):
    token: str


class UserInfoResponse(BaseModel):
    id: str
    email: str
    email_verified: bool


class AuthStatusResponse(BaseModel):
    enabled: bool


# ===== Routes =====

@router.get("/status", response_model=AuthStatusResponse)
async def get_auth_status():
    """检查认证服务是否已启用"""
    return AuthStatusResponse(enabled=is_supabase_enabled())


@router.post("/verify", response_model=UserInfoResponse)
async def verify_token(request: TokenVerifyRequest):
    """
    验证 Token

    前端调用此接口验证从 Supabase 获取的 Token 是否有效
    """
    if not is_supabase_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is not configured"
        )

    client = get_supabase_client_anon()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication client not available"
        )

    try:
        response = client.auth.get_user(request.token)
        if response and response.user:
            return UserInfoResponse(
                id=response.user.id,
                email=response.user.email or "",
                email_verified=response.user.email_confirmed_at is not None
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {str(e)}"
        )


@router.get("/me", response_model=UserInfoResponse)
async def get_current_user_info(
    user: dict = Depends(get_current_user_required)
):
    """
    获取当前用户信息

    需要在请求头中携带 Authorization: Bearer {token}
    """
    return UserInfoResponse(
        id=user["id"],
        email=user["email"],
        email_verified=user.get("email_verified", False)
    )