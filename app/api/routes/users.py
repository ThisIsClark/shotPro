"""
Users API Routes
用户管理 API 路由
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel

from ..deps import get_current_user_required
from ...services.db_service import db_service
from ...services.supabase_client import is_supabase_enabled

router = APIRouter(prefix="/users", tags=["users"])


# ===== Response Models =====

class AnalysisHistoryItem(BaseModel):
    id: str
    video_filename: str
    status: str
    overall_score: Optional[float] = None
    rating: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


class AnalysisHistoryResponse(BaseModel):
    total: int
    items: List[AnalysisHistoryItem]


class UserStatsResponse(BaseModel):
    total_analyses: int
    completed_analyses: int
    average_score: Optional[float] = None
    best_score: Optional[float] = None


# ===== Routes =====

@router.get("/history", response_model=AnalysisHistoryResponse)
async def get_analysis_history(
    user: dict = Depends(get_current_user_required),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None)
):
    """
    获取用户的分析历史记录

    需要在请求头中携带 Authorization: Bearer {token}
    """
    if not is_supabase_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is not configured"
        )

    user_id = user["id"]
    analyses = await db_service.get_user_analyses(
        user_id=user_id,
        limit=limit,
        offset=offset,
        status_filter=status_filter
    )

    items = []
    for a in analyses:
        items.append(AnalysisHistoryItem(
            id=a["id"],
            video_filename=a.get("video_filename", ""),
            status=a.get("status", "pending"),
            overall_score=a.get("overall_score"),
            rating=a.get("rating"),
            created_at=a.get("created_at", ""),
            completed_at=a.get("completed_at")
        ))

    return AnalysisHistoryResponse(total=len(items), items=items)


@router.get("/stats", response_model=UserStatsResponse)
async def get_user_stats(
    user: dict = Depends(get_current_user_required)
):
    """
    获取用户统计数据

    需要在请求头中携带 Authorization: Bearer {token}
    """
    if not is_supabase_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is not configured"
        )

    user_id = user["id"]
    stats = await db_service.get_user_stats(user_id)

    return UserStatsResponse(
        total_analyses=stats.get("total_analyses", 0),
        completed_analyses=stats.get("completed_analyses", 0),
        average_score=stats.get("average_score"),
        best_score=stats.get("best_score")
    )


@router.get("/templates")
async def get_user_templates(
    user: dict = Depends(get_current_user_required)
):
    """
    获取用户的私人模板列表

    需要在请求头中携带 Authorization: Bearer {token}
    """
    if not is_supabase_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is not configured"
        )

    user_id = user["id"]
    templates = await db_service.get_user_templates(user_id)

    return {
        "success": True,
        "templates": templates
    }