"""
Health Check Routes
健康检查接口
"""

from fastapi import APIRouter

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
    """根路径"""
    return {
        "message": "Welcome to Basketball Shooting Form Analyzer API",
        "docs": "/docs",
        "version": settings.app_version
    }
