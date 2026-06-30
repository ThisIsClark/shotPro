"""
Health Check Routes
健康检查接口
"""

from fastapi import APIRouter
from fastapi.responses import RedirectResponse

from ...config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.app_version
    }


@router.get("/debug/env")
async def debug_env():
    """Debug: check if env vars are injected"""
    return {
        "supabase_url_set": bool(settings.supabase_url),
        "supabase_url_prefix": settings.supabase_url[:20] if settings.supabase_url else "EMPTY",
        "supabase_anon_key_set": bool(settings.supabase_anon_key),
        "supabase_service_key_set": bool(settings.supabase_service_key),
        "creem_api_key_set": bool(settings.creem_api_key),
        "app_url": settings.app_url or "EMPTY",
    }


@router.get("/")
async def root():
    """根路径 - 重定向到应用页面（兼容 Supabase 邮箱验证回调）"""
    return RedirectResponse(url="/app")
