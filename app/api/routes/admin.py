"""
Admin Routes
管理员接口：审计日志查看等
"""

from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query

from ..deps import get_current_user_required
from ..services.audit_service import audit_service, AuditAction
from ..services.db_service import db_service
from ..services.local_auth_service import local_auth_service

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(user: dict = Depends(get_current_user_required)) -> dict:
    """验证管理员权限"""
    # 本地用户检查
    if user.get("is_local"):
        if user.get("role") == "admin":
            return user
        raise HTTPException(status_code=403, detail="Admin access required")

    # Supabase 用户暂时都不认为是管理员
    # 后续可以在 Supabase 用户表中添加 role 字段
    raise HTTPException(status_code=403, detail="Admin access required")


@router.get("/audit-logs")
async def get_audit_logs(
    admin: dict = Depends(require_admin),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    days: Optional[int] = Query(7, ge=1, le=30)
):
    """
    获取审计日志列表（管理员）

    Args:
        limit: 返回数量
        offset: 偏移量
        user_id: 按用户筛选
        action: 按操作类型筛选
        days: 最近多少天
    """
    if not audit_service.is_available():
        raise HTTPException(status_code=503, detail="Audit service not available")

    start_date = datetime.utcnow() - timedelta(days=days)

    logs = await audit_service.get_logs(
        limit=limit,
        offset=offset,
        user_id=user_id,
        action=action,
        start_date=start_date
    )

    return {
        "logs": logs,
        "count": len(logs),
        "filters": {
            "user_id": user_id,
            "action": action,
            "days": days
        }
    }


@router.get("/audit-stats")
async def get_audit_stats(
    admin: dict = Depends(require_admin),
    days: int = Query(7, ge=1, le=30)
):
    """
    获取审计统计摘要（管理员）
    """
    if not audit_service.is_available():
        raise HTTPException(status_code=503, detail="Audit service not available")

    stats = await audit_service.get_stats_summary(days=days)
    return stats


@router.get("/user-stats/{user_id}")
async def get_user_stats(
    user_id: str,
    admin: dict = Depends(require_admin)
):
    """
    获取用户统计数据（管理员）
    """
    if not db_service.is_available():
        raise HTTPException(status_code=503, detail="Database not available")

    stats = await db_service.get_user_stats(user_id)
    return stats


@router.get("/all-users-stats")
async def get_all_users_stats(
    admin: dict = Depends(require_admin)
):
    """
    获取所有用户的分析统计（管理员）
    """
    if not audit_service.is_available():
        raise HTTPException(status_code=503, detail="Audit service not available")

    # 获取最近 30 天完成的分析统计
    start_date = datetime.utcnow() - timedelta(days=30)

    # 统计各用户完成分析的数量
    logs = await audit_service.get_logs(
        limit=1000,
        action="analysis_completed",
        start_date=start_date
    )

    # 按用户统计
    user_stats = {}
    for log in logs:
        user_id = log.get("user_id") or log.get("user_email") or "anonymous"
        if user_id not in user_stats:
            user_stats[user_id] = {
                "user_id": user_id,
                "user_email": log.get("user_email"),
                "analysis_count": 0,
                "last_activity": log.get("created_at")
            }
        user_stats[user_id]["analysis_count"] += 1
        # 更新最后活动时间（取最新的）
        if log.get("created_at") > user_stats[user_id]["last_activity"]:
            user_stats[user_id]["last_activity"] = log.get("created_at")

    return {
        "period_days": 30,
        "users": list(user_stats.values()),
        "total_users": len(user_stats),
        "total_analyses": len(logs)
    }