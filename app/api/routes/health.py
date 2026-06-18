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
    """健康检查"""
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.app_version
    }


@router.get("/")
async def root():
    """根路径 - 重定向到应用页面（兼容 Supabase 邮箱验证回调）"""
    return RedirectResponse(url="/app")
