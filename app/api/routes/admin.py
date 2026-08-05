"""
Admin Routes
管理员接口：Dashboard 统计、用户管理、分析记录、支付记录、审计日志
"""

from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..deps import get_current_user_required
from ...services.audit_service import audit_service, AuditAction
from ...services.db_service import db_service
from ...services.local_auth_service import local_auth_service

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin(user: dict = Depends(get_current_user_required)) -> dict:
    """验证管理员权限"""
    if user.get("is_local") and user.get("role") == "admin":
        return user
    raise HTTPException(status_code=403, detail="Admin access required")


# ===== Request Models =====

class AdjustCreditsRequest(BaseModel):
    amount: int  # 正数增加，负数扣减
    reason: str = ""


# ===== Dashboard =====

@router.get("/dashboard-stats")
async def get_dashboard_stats(admin: dict = Depends(require_admin)):
    """获取 Dashboard 概览数据（含订阅统计）"""
    stats = {
        "total_analyses": 0,
        "completed_analyses": 0,
        "failed_analyses": 0,
        "total_users": 0,
        "free_users": 0,
        "paid_users": 0,
        "monthly_subscribers": 0,
        "yearly_subscribers": 0,
        "expired_subscribers": 0,
        "total_credits_granted": 0,
        "total_payments": 0,
        "recent_analyses_7d": 0,
        "recent_analyses_30d": 0,
        "new_users_7d": 0,
        "new_users_30d": 0,
        "db_available": False,
    }

    if not db_service.is_available():
        return stats

    now = datetime.utcnow()
    seven_days_ago = (now - timedelta(days=7)).isoformat()
    thirty_days_ago = (now - timedelta(days=30)).isoformat()

    try:
        # 分析统计
        analyses_resp = db_service.client.table("analyses").select("status, created_at").execute()
        analyses = analyses_resp.data or []
        stats["total_analyses"] = len(analyses)
        stats["completed_analyses"] = len([a for a in analyses if a.get("status") == "completed"])
        stats["failed_analyses"] = len([a for a in analyses if a.get("status") == "failed"])
        stats["recent_analyses_7d"] = len([a for a in analyses if a.get("created_at", "") >= seven_days_ago])
        stats["recent_analyses_30d"] = len([a for a in analyses if a.get("created_at", "") >= thirty_days_ago])
    except Exception as e:
        print(f"[Admin] Analyses stats failed: {e}")

    try:
        # 用户统计
        credits_resp = db_service.client.table("user_credits").select("user_id, credits_remaining, total_granted, created_at").execute()
        credits_data = credits_resp.data or []
        stats["total_users"] = len(credits_data)
        stats["total_credits_granted"] = sum(c.get("total_granted", 0) for c in credits_data)
        stats["new_users_7d"] = len([c for c in credits_data if c.get("created_at", "") >= seven_days_ago])
        stats["new_users_30d"] = len([c for c in credits_data if c.get("created_at", "") >= thirty_days_ago])
    except Exception as e:
        print(f"[Admin] User stats failed: {e}")

    try:
        # 订阅统计
        subs_resp = db_service.client.table("user_subscriptions").select("user_id, plan, status, current_period_end").execute()
        subs_data = subs_resp.data or []

        # 活跃订阅用户集合
        active_sub_user_ids = set()
        for sub in subs_data:
            if sub.get("status") in ("active", "scheduled_cancel"):
                period_end = sub.get("current_period_end")
                if period_end:
                    try:
                        from datetime import timezone
                        end_time = datetime.fromisoformat(period_end.replace("Z", "+00:00")) if isinstance(period_end, str) else period_end
                        if end_time <= datetime.now(timezone.utc):
                            continue
                    except Exception:
                        pass
                active_sub_user_ids.add(sub.get("user_id"))
                if sub.get("plan") == "early_adopter_monthly":
                    stats["monthly_subscribers"] += 1
                elif sub.get("plan") == "early_adopter_yearly":
                    stats["yearly_subscribers"] += 1
            elif sub.get("status") == "expired":
                stats["expired_subscribers"] += 1

        stats["paid_users"] = len(active_sub_user_ids)
        stats["free_users"] = stats["total_users"] - stats["paid_users"]
    except Exception as e:
        print(f"[Admin] Subscription stats failed (table may not exist): {e}")
        stats["free_users"] = stats["total_users"]

    try:
        # 支付统计
        payments_resp = db_service.client.table("payment_checkouts").select("checkout_id").execute()
        stats["total_payments"] = len(payments_resp.data or [])
    except Exception as e:
        print(f"[Admin] Payment stats failed: {e}")

    stats["db_available"] = True

    return stats


# ===== User Management =====

@router.get("/users")
async def list_users(
    admin: dict = Depends(require_admin),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: Optional[str] = None,
    subscription_filter: Optional[str] = None  # "free", "paid", "expired"
):
    """获取用户列表（含订阅状态和使用统计）"""
    if not db_service.is_available():
        return {"users": [], "total": 0, "db_available": False}

    try:
        # 1. 获取所有订阅数据，构建 user_id -> subscription 映射
        subs_map = {}  # user_id -> {plan, status, current_period_end}
        try:
            subs_resp = db_service.client.table("user_subscriptions").select("user_id, plan, status, current_period_end").order("created_at", desc=True).execute()
            for sub in subs_resp.data or []:
                uid = sub.get("user_id", "")
                if uid not in subs_map:
                    subs_map[uid] = {"plan": sub.get("plan"), "status": sub.get("status"), "current_period_end": sub.get("current_period_end")}
        except Exception as e:
            print(f"[Admin] Fetch subscriptions for users failed (table may not exist): {e}")

        # 2. 获取所有分析数据，构建 user_id -> {total, completed, last_activity} 映射
        analyses_map = {}  # user_id -> {total, completed, last_activity}
        try:
            all_analyses = db_service.client.table("analyses").select("user_id, status, created_at").execute()
            for a in all_analyses.data or []:
                uid = a.get("user_id", "")
                if not uid:
                    continue
                if uid not in analyses_map:
                    analyses_map[uid] = {"total": 0, "completed": 0, "last_activity": ""}
                analyses_map[uid]["total"] += 1
                if a.get("status") == "completed":
                    analyses_map[uid]["completed"] += 1
                if a.get("created_at", "") > analyses_map[uid]["last_activity"]:
                    analyses_map[uid]["last_activity"] = a.get("created_at", "")
        except Exception as e:
            print(f"[Admin] Fetch analyses for users failed: {e}")

        # 3. 获取用户 credits
        query = db_service.client.table("user_credits").select("user_id, credits_remaining, total_granted, updated_at, created_at")

        if search:
            query = query.eq("user_id", search)

        query = query.order("created_at", desc=True)
        credits_resp = query.execute()
        credits_data = credits_resp.data or []

        # 4. 应用订阅过滤器
        def get_user_subscription_status(uid):
            sub = subs_map.get(uid)
            if not sub:
                return "free"
            status = sub.get("status", "")
            if status in ("active", "scheduled_cancel"):
                period_end = sub.get("current_period_end")
                if period_end:
                    try:
                        from datetime import timezone
                        end_time = datetime.fromisoformat(period_end.replace("Z", "+00:00")) if isinstance(period_end, str) else period_end
                        if end_time <= datetime.now(timezone.utc):
                            return "expired"
                    except Exception:
                        pass
                return "paid"
            if status == "expired":
                return "expired"
            return "free"

        if subscription_filter:
            credits_data = [c for c in credits_data if get_user_subscription_status(c.get("user_id", "")) == subscription_filter]

        total = len(credits_data)
        page_data = credits_data[offset:offset + limit]

        # 5. 批量获取用户邮箱
        user_emails = {}
        try:
            page = 1
            while True:
                resp = db_service.client.auth.admin.list_users(page=page, per_page=1000)
                users_list = resp if isinstance(resp, list) else getattr(resp, 'users', [])
                for u in users_list:
                    user_emails[u.id] = u.email or ""
                if len(users_list) < 1000:
                    break
                page += 1
        except Exception as e:
            print(f"[Admin] Fetch user emails failed: {e}")

        # 6. 组装用户数据
        users = []
        for c in page_data:
            user_id = c.get("user_id", "")
            sub = subs_map.get(user_id, {})
            a_stats = analyses_map.get(user_id, {"total": 0, "completed": 0, "last_activity": ""})
            sub_status = get_user_subscription_status(user_id)

            users.append({
                "user_id": user_id,
                "email": user_emails.get(user_id, ""),
                "credits_remaining": c.get("credits_remaining", 0),
                "total_granted": c.get("total_granted", 0),
                "total_analyses": a_stats["total"],
                "completed_analyses": a_stats["completed"],
                "last_activity": a_stats["last_activity"],
                "created_at": c.get("created_at", ""),
                "subscription_plan": sub.get("plan"),
                "subscription_status": sub.get("status"),
                "subscription_display": sub_status,  # "free" / "paid" / "expired"
            })

        return {"users": users, "total": total, "db_available": True}
    except Exception as e:
        print(f"[Admin] List users failed: {e}")
        return {"users": [], "total": 0, "db_available": False}


@router.put("/users/{user_id}/credits")
async def adjust_user_credits(
    user_id: str,
    request: AdjustCreditsRequest,
    admin: dict = Depends(require_admin)
):
    """调整用户 credits（正数增加，负数扣减）"""
    if not db_service.is_available():
        raise HTTPException(status_code=503, detail="Database not available")

    if request.amount == 0:
        raise HTTPException(status_code=400, detail="Amount cannot be zero")

    try:
        if request.amount > 0:
            new_remaining = await db_service.increment_user_credits(user_id, request.amount)
        else:
            current = await db_service.get_user_credits(user_id)
            if current < 0:
                raise HTTPException(status_code=404, detail="User not found")
            new_remaining = max(0, current + request.amount)
            db_service.client.table("user_credits").update({
                "credits_remaining": new_remaining,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("user_id", user_id).execute()

        return {
            "success": True,
            "user_id": user_id,
            "credits_remaining": new_remaining,
            "adjusted_by": request.amount
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Admin] Adjust credits failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== Analysis Records =====

@router.get("/analyses")
async def list_analyses(
    admin: dict = Depends(require_admin),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = None,
    user_id: Optional[str] = None
):
    """获取分析记录列表"""
    if not db_service.is_available():
        return {"analyses": [], "count": 0, "db_available": False}

    try:
        query = db_service.client.table("analyses").select("*").order("created_at", desc=True)

        if status_filter:
            query = query.eq("status", status_filter)
        if user_id:
            query = query.eq("user_id", user_id)

        query = query.limit(limit).offset(offset)
        response = query.execute()

        return {
            "analyses": response.data or [],
            "count": len(response.data or []),
            "db_available": True
        }
    except Exception as e:
        print(f"[Admin] List analyses failed: {e}")
        return {"analyses": [], "count": 0, "db_available": False}


# ===== Payment Records =====

@router.get("/payments")
async def list_payments(
    admin: dict = Depends(require_admin),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """获取支付记录列表"""
    if not db_service.is_available():
        return {"payments": [], "count": 0, "db_available": False}

    try:
        query = db_service.client.table("payment_checkouts").select("*").order("processed_at", desc=True).limit(limit).offset(offset)
        response = query.execute()

        return {
            "payments": response.data or [],
            "count": len(response.data or []),
            "db_available": True
        }
    except Exception as e:
        print(f"[Admin] List payments failed: {e}")
        return {"payments": [], "count": 0, "db_available": False}


# ===== Subscriptions =====

@router.get("/subscriptions")
async def list_subscriptions(
    admin: dict = Depends(require_admin),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = None
):
    """获取订阅列表"""
    if not db_service.is_available():
        return {"subscriptions": [], "count": 0, "db_available": False}

    try:
        query = db_service.client.table("user_subscriptions").select("*").order("created_at", desc=True)

        if status_filter:
            query = query.eq("status", status_filter)

        query = query.limit(limit).offset(offset)
        response = query.execute()

        # 批量获取用户邮箱
        user_emails = {}
        try:
            page = 1
            while True:
                resp = db_service.client.auth.admin.list_users(page=page, per_page=1000)
                users_list = resp if isinstance(resp, list) else getattr(resp, 'users', [])
                for u in users_list:
                    user_emails[u.id] = u.email or ""
                if len(users_list) < 1000:
                    break
                page += 1
        except Exception as e:
            print(f"[Admin] Fetch user emails for subscriptions failed: {e}")

        subscriptions = []
        for sub in response.data or []:
            sub_copy = dict(sub)
            sub_copy["email"] = user_emails.get(sub.get("user_id", ""), "")
            subscriptions.append(sub_copy)

        return {
            "subscriptions": subscriptions,
            "count": len(subscriptions),
            "db_available": True
        }
    except Exception as e:
        print(f"[Admin] List subscriptions failed: {e}")
        return {"subscriptions": [], "count": 0, "db_available": False}


# ===== Audit Logs =====

@router.get("/audit-logs")
async def get_audit_logs(
    admin: dict = Depends(require_admin),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    ip_address: Optional[str] = None,
    days: Optional[int] = Query(7, ge=1, le=30)
):
    """获取审计日志列表（支持按 IP 筛选）"""
    if not audit_service.is_available():
        return {"logs": [], "count": 0, "filters": {"user_id": user_id, "action": action, "ip_address": ip_address, "days": days}, "db_available": False}

    start_date = datetime.utcnow() - timedelta(days=days)
    try:
        logs = await audit_service.get_logs(
            limit=limit,
            offset=offset,
            user_id=user_id,
            action=action,
            start_date=start_date
        )
        # IP 筛选（audit_service.get_logs 不支持 ip 筛选，在内存过滤）
        if ip_address:
            logs = [l for l in logs if l.get("ip_address") == ip_address]
        return {
            "logs": logs,
            "count": len(logs),
            "filters": {"user_id": user_id, "action": action, "ip_address": ip_address, "days": days},
            "db_available": True
        }
    except Exception as e:
        print(f"[Admin] Audit logs failed: {e}")
        return {"logs": [], "count": 0, "filters": {"user_id": user_id, "action": action, "ip_address": ip_address, "days": days}, "db_available": False}


@router.get("/audit-stats")
async def get_audit_stats(
    admin: dict = Depends(require_admin),
    days: int = Query(7, ge=1, le=30)
):
    """获取审计统计摘要"""
    if not audit_service.is_available():
        return {}

    try:
        stats = await audit_service.get_stats_summary(days=days)
        return stats
    except Exception as e:
        print(f"[Admin] Audit stats failed: {e}")
        return {}


@router.get("/funnel-stats")
async def get_funnel_stats(
    admin: dict = Depends(require_admin),
    days: int = Query(7, ge=1, le=30)
):
    """
    获取用户行为漏斗统计。

    漏斗步骤：page_view → register_attempt → register_success → login_success → analysis_started → payment_attempt → payment_success
    返回每步计数 + 转化率。
    """
    if not audit_service.is_available():
        return {"funnel": [], "db_available": False}

    start_date = datetime.utcnow() - timedelta(days=days)
    try:
        # 获取时间范围内所有日志
        logs = await audit_service.get_logs(
            limit=5000,
            offset=0,
            start_date=start_date
        )

        # 按动作聚合计数
        action_counts = {}
        for log in logs:
            action = log.get("action", "unknown")
            action_counts[action] = action_counts.get(action, 0) + 1

        # 漏斗步骤定义
        funnel_steps = [
            {"key": "page_view", "label": "Page View", "action": "page_view"},
            {"key": "register_attempt", "label": "Register Attempt", "action": "register_attempt"},
            {"key": "register_success", "label": "Register Success", "action": "register_success"},
            {"key": "login_success", "label": "Login Success", "action": "login_success"},
            {"key": "analysis_started", "label": "Analysis Started", "action": "analysis_started"},
            {"key": "payment_attempt", "label": "Payment Attempt", "action": "payment_attempt"},
            {"key": "payment_success", "label": "Payment Success", "action": "payment_success"},
        ]

        funnel = []
        prev_count = None
        for step in funnel_steps:
            count = action_counts.get(step["action"], 0)
            conversion_rate = None
            if prev_count is not None and prev_count > 0:
                conversion_rate = round((count / prev_count) * 100, 1)
            funnel.append({
                "key": step["key"],
                "label": step["label"],
                "count": count,
                "conversion_from_prev": conversion_rate,
            })
            prev_count = count

        # 总体转化率（page_view → payment_success）
        total_conversion = None
        first_count = funnel[0]["count"]
        last_count = funnel[-1]["count"]
        if first_count > 0:
            total_conversion = round((last_count / first_count) * 100, 2)

        return {
            "funnel": funnel,
            "total_conversion": total_conversion,
            "period_days": days,
            "total_logs": len(logs),
            "action_counts": action_counts,
            "db_available": True,
        }
    except Exception as e:
        print(f"[Admin] Funnel stats failed: {e}")
        return {"funnel": [], "db_available": False}


@router.get("/user-stats/{user_id}")
async def get_user_stats(
    user_id: str,
    admin: dict = Depends(require_admin)
):
    """获取用户统计数据"""
    if not db_service.is_available():
        return {}

    try:
        stats = await db_service.get_user_stats(user_id)
        return stats
    except Exception as e:
        print(f"[Admin] User stats failed: {e}")
        return {}


@router.get("/ip-behavior/{ip_address}")
async def get_ip_behavior(
    ip_address: str,
    admin: dict = Depends(require_admin),
    days: int = Query(30, ge=1, le=90)
):
    """
    获取单个 IP 的完整行为链。

    按 IP 串联同一访客的多次行为（访问→注册→登录→...），
    用于追踪未登录用户的完整行为路径。
    """
    if not audit_service.is_available():
        return {"logs": [], "ip_address": ip_address, "db_available": False}

    start_date = datetime.utcnow() - timedelta(days=days)
    try:
        logs = await audit_service.get_logs(
            limit=500,
            offset=0,
            start_date=start_date
        )
        # 按 IP 过滤，按时间正序排列（行为链顺序）
        ip_logs = [l for l in logs if l.get("ip_address") == ip_address]
        ip_logs.sort(key=lambda x: x.get("created_at", ""))

        return {
            "logs": ip_logs,
            "ip_address": ip_address,
            "total_events": len(ip_logs),
            "period_days": days,
            "db_available": True,
        }
    except Exception as e:
        print(f"[Admin] IP behavior failed: {e}")
        return {"logs": [], "ip_address": ip_address, "db_available": False}
