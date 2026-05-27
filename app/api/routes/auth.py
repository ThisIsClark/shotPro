"""
Authentication API Routes
认证 API 路由：支持 Supabase 认证和本地管理员账号
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..deps import get_current_user_required
from ...services.supabase_client import get_supabase_client_anon, is_supabase_enabled
from ...services.local_auth_service import local_auth_service

router = APIRouter(prefix="/auth", tags=["authentication"])


# ===== Request/Response Models =====

class TokenVerifyRequest(BaseModel):
    token: str


class LocalLoginRequest(BaseModel):
    username: str
    password: str


class UserInfoResponse(BaseModel):
    id: str
    email: str
    email_verified: bool
    role: str = "user"
    is_local: bool = False


class AuthStatusResponse(BaseModel):
    enabled: bool
    local_auth_enabled: bool = True


class LocalLoginResponse(BaseModel):
    success: bool
    user: Optional[UserInfoResponse] = None
    message: str = ""


# ===== Routes =====

@router.get("/status", response_model=AuthStatusResponse)
async def get_auth_status():
    """检查认证服务状态"""
    return AuthStatusResponse(
        enabled=is_supabase_enabled(),
        local_auth_enabled=True
    )


@router.post("/local-login", response_model=LocalLoginResponse)
async def local_login(request: LocalLoginRequest):
    """
    本地账号登录

    用于管理员账号登录，账号密码存储在本地
    """
    user = local_auth_service.authenticate(request.username, request.password)

    if not user:
        return LocalLoginResponse(
            success=False,
            message="Invalid username or password"
        )

    return LocalLoginResponse(
        success=True,
        user=UserInfoResponse(
            id=user["username"],  # 使用 username 作为 id
            email=user.get("email", ""),
            email_verified=True,  # 本地账号默认已验证
            role=user.get("role", "user"),
            is_local=True
        ),
        message="Login successful"
    )


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
        email_verified=user.get("email_verified", False),
        role=user.get("role", "user"),
        is_local=user.get("is_local", False)
    )