"""
Authentication API Routes
认证 API 路由：支持 Supabase 认证和本地管理员账号
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..deps import get_current_user_required, get_current_user_optional, get_user_id
from ...services.supabase_client import get_supabase_client_anon, is_supabase_enabled
from ...services.local_auth_service import local_auth_service
from ...services.jwt_service import jwt_service
from ...services.db_service import db_service

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
    token: Optional[str] = None
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

    # 签发本地 JWT
    token = jwt_service.create_token({
        "id": user["username"],
        "role": user.get("role", "user"),
        "is_local": True,
        "email": user.get("email", ""),
    })

    return LocalLoginResponse(
        success=True,
        user=UserInfoResponse(
            id=user["username"],  # 使用 username 作为 id
            email=user.get("email", ""),
            email_verified=True,  # 本地账号默认已验证
            role=user.get("role", "user"),
            is_local=True
        ),
        token=token,
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


class CreditsResponse(BaseModel):
    credits_remaining: int
    is_unlimited: bool = False
    subscription_plan: Optional[str] = None
    subscription_status: Optional[str] = None
    is_early_adopter: Optional[bool] = None
    current_period_end: Optional[str] = None  # 订阅到期时间 ISO 格式


@router.get("/credits", response_model=CreditsResponse)
async def get_user_credits(
    user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    获取用户剩余分析次数和订阅状态

    - 本地管理员账户：不限次数
    - 订阅用户：不限次数
    - 未登录用户：返回 0 次
    - Free 用户：从数据库读取
    """
    # 本地管理员不限次数
    if user and user.get("is_local"):
        return CreditsResponse(
            credits_remaining=999,
            is_unlimited=True,
            subscription_plan="admin",
            subscription_status="active",
        )

    user_id = get_user_id(user)
    if not user_id:
        return CreditsResponse(credits_remaining=0, is_unlimited=False)

    if not db_service.is_available():
        return CreditsResponse(credits_remaining=999, is_unlimited=True)

    # 检查订阅状态
    sub = await db_service.get_user_subscription(user_id)
    if sub and sub.get("status") in ("active", "scheduled_cancel"):
        is_early_adopter = sub.get("plan", "").startswith("early_adopter")
        return CreditsResponse(
            credits_remaining=999,
            is_unlimited=True,
            subscription_plan=sub.get("plan"),
            subscription_status=sub.get("status"),
            is_early_adopter=is_early_adopter,
            current_period_end=sub.get("current_period_end"),
        )

    # Free 用户
    remaining = await db_service.get_user_credits(user_id)
    if remaining < 0:
        remaining = 0

    return CreditsResponse(credits_remaining=remaining, is_unlimited=False)