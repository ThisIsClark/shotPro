"""
Audit / Behavior Tracking Routes
用户行为追踪上报端点：前端上报页面访问/注册登录成败/按钮点击等，
后端取真实 IP+UA，写入 audit_logs 供管理员分析漏斗。
"""

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from ..deps import get_current_user_optional, get_user_id
from ...services.audit_service import audit_service, AuditAction

router = APIRouter(prefix="/audit", tags=["audit"])


# 允许前端上报的动作白名单（防任意写入垃圾数据）
ALLOWED_TRACK_ACTIONS = {
    AuditAction.PAGE_VIEW.value,
    AuditAction.REGISTER_ATTEMPT.value,
    AuditAction.REGISTER_SUCCESS.value,
    AuditAction.REGISTER_FAILED.value,
    AuditAction.LOGIN_ATTEMPT.value,
    AuditAction.LOGIN_SUCCESS.value,
    AuditAction.LOGIN_FAILED.value,
    AuditAction.LOGOUT_ACTION.value,
    AuditAction.BUTTON_CLICK.value,
}


class TrackEventRequest(BaseModel):
    action: str
    details: Optional[Dict[str, Any]] = None


def _get_client_ip(request: Request) -> Optional[str]:
    """取客户端真实 IP（优先 X-Forwarded-For，反代场景）"""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # X-Forwarded-For 可能是 "client, proxy1, proxy2"，取第一个
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@router.post("/event")
async def track_event(
    req: TrackEventRequest,
    request: Request,
    user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    前端用户行为上报。

    未登录用户也可上报（页面访问/注册失败的还没登录）。
    IP/UA 由后端从 request 取（比前端自报准）。
    action 必须在白名单内，防任意写入。
    """
    action = req.action
    if action not in ALLOWED_TRACK_ACTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown action: {action}"
        )

    # 登录用户带身份，未登录留空（靠 IP 串联）
    user_id = get_user_id(user) if user else None
    user_email = user.get("email") if user else None

    ip = _get_client_ip(request)
    ua = request.headers.get("user-agent")

    await audit_service.log(
        action=action,
        user_id=user_id,
        user_email=user_email,
        details=req.details or {},
        ip_address=ip,
        user_agent=ua
    )

    return {"success": True}
