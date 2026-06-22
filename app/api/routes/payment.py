"""
Payment API Routes
付款 API 路由：Creem checkout 创建、Webhook 回调、订阅管理

定价方案：
- Free: $0 — 注册送 3 次免费分析
- Early Adopter 月付: $4.99/月 — 无限次分析（锁定价格）
- Early Adopter 年付: $39.99/年 — 无限次分析（锁定价格，约 $3.33/月）
- Regular Price: $7.99/月 — 加评分体系、改善建议、进步曲线后对新用户生效
"""

import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from ..deps import get_current_user_optional, get_current_user_required
from ...services.creem_service import creem_service
from ...services.db_service import db_service

router = APIRouter(prefix="/payment", tags=["payment"])


# ===== Request/Response Models =====

class CheckoutResponse(BaseModel):
    checkout_url: str
    checkout_id: Optional[str] = None


class SubscribeRequest(BaseModel):
    billing_period: str  # "monthly" or "yearly"


class PlanInfo(BaseModel):
    plan: str
    name: str
    price: float
    price_display: str
    price_unit: Optional[str] = None
    monthly_equivalent: Optional[str] = None
    product_id: Optional[str] = None
    credits: Optional[int] = None
    is_unlimited: bool
    is_early_adopter: Optional[bool] = None
    is_best_value: Optional[bool] = None
    description: str
    description_zh: Optional[str] = None


class PlansResponse(BaseModel):
    plans: list[PlanInfo]
    regular_price: float
    early_adopter_message: str
    early_adopter_message_zh: str


class SubscriptionStatusResponse(BaseModel):
    has_subscription: bool
    plan: Optional[str] = None
    status: Optional[str] = None
    current_period_end: Optional[str] = None
    is_early_adopter: Optional[bool] = None


class CancelSubscriptionResponse(BaseModel):
    success: bool
    message: str


# ===== Routes =====

@router.get("/plans", response_model=PlansResponse)
async def get_plans():
    """获取订阅计划信息"""
    plans = creem_service.get_plans_info()
    return PlansResponse(
        plans=[PlanInfo(**p) for p in plans],
        regular_price=7.99,
        early_adopter_message="V1.0 Early Adopter Pricing — Subscribe now and lock in $4.99/month forever. Regular price will be $7.99/month when we add scoring, coaching tips, and progress tracking.",
        early_adopter_message_zh="V1.0 早期用户定价 — 现在订阅即锁定 $4.99/月永久不变。后续加评分体系、改善建议、进步曲线后，新用户价格将调整为 $7.99/月。",
    )


@router.post("/subscribe", response_model=CheckoutResponse)
async def create_subscription(
    request: SubscribeRequest,
    req: Request,
    user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    创建 Creem 订阅 checkout session

    需要登录。前端拿到 checkout_url 后跳转至 Creem 托管付款页面。
    """
    user_id = None
    user_email = None

    if user and user.get("id"):
        user_id = user["id"]
        user_email = user.get("email")
    elif user and user.get("is_local"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Local admin accounts have unlimited access"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login required to subscribe",
        )

    if not creem_service.is_subscription_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Subscription service is not configured",
        )

    if request.billing_period not in ("monthly", "yearly"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="billing_period must be 'monthly' or 'yearly'",
        )

    # 检查用户是否已有活跃订阅
    if db_service.is_available() and user_id:
        existing_sub = await db_service.get_user_subscription(user_id)
        if existing_sub and existing_sub.get("status") in ("active", "scheduled_cancel"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="You already have an active subscription",
            )

    origin = str(req.base_url).rstrip("/")
    result = await creem_service.create_subscription_checkout(
        user_id=user_id,
        billing_period=request.billing_period,
        user_email=user_email,
        origin=origin,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create subscription checkout",
        )

    return CheckoutResponse(
        checkout_url=result["checkout_url"],
        checkout_id=result.get("checkout_id"),
    )


@router.get("/subscription-status", response_model=SubscriptionStatusResponse)
async def get_subscription_status(
    user: Optional[dict] = Depends(get_current_user_optional)
):
    """获取当前用户订阅状态"""
    user_id = user.get("id") if user else None

    if not user_id:
        return SubscriptionStatusResponse(has_subscription=False)

    if user and user.get("is_local"):
        return SubscriptionStatusResponse(
            has_subscription=True,
            plan="admin",
            status="active",
            is_early_adopter=False,
        )

    if not db_service.is_available():
        return SubscriptionStatusResponse(has_subscription=False)

    sub = await db_service.get_user_subscription(user_id)
    if not sub:
        return SubscriptionStatusResponse(has_subscription=False)

    is_early_adopter = sub.get("plan", "").startswith("early_adopter")

    return SubscriptionStatusResponse(
        has_subscription=True,
        plan=sub.get("plan"),
        status=sub.get("status"),
        current_period_end=sub.get("current_period_end"),
        is_early_adopter=is_early_adopter,
    )


@router.post("/cancel-subscription", response_model=CancelSubscriptionResponse)
async def cancel_subscription(
    user: dict = Depends(get_current_user_required),
):
    """取消当前用户的订阅（到期后取消，保留当前周期访问权限）"""
    user_id = user.get("id")

    if user.get("is_local"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Local admin accounts cannot cancel subscriptions"
        )

    if not db_service.is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not available"
        )

    sub = await db_service.get_user_subscription(user_id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active subscription found"
        )

    creem_subscription_id = sub.get("creem_subscription_id")
    if not creem_subscription_id:
        # 没有 Creem 订阅 ID，直接在本地标记取消
        await db_service.cancel_user_subscription(user_id, immediate=False)
        return CancelSubscriptionResponse(
            success=True,
            message="Subscription will be canceled at the end of the current billing period"
        )

    # 调用 Creem API 取消订阅（scheduled 模式，到期后取消）
    success = await creem_service.cancel_subscription(creem_subscription_id, mode="scheduled")

    if success:
        await db_service.cancel_user_subscription(user_id, immediate=False)
        return CancelSubscriptionResponse(
            success=True,
            message="Subscription will be canceled at the end of the current billing period"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel subscription with payment provider"
        )


@router.post("/webhook")
async def creem_webhook(request: Request):
    """
    Creem webhook 回调端点

    接收 Creem 发送的支付事件通知。
    无需认证（Creem 服务器调用），通过签名验证真实性。
    """
    body = await request.body()
    payload_str = body.decode("utf-8")

    # 验证签名
    signature = request.headers.get("creem-signature", "")
    if not creem_service.verify_webhook_signature(payload_str, signature):
        print("[Creem Webhook] Invalid signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature",
        )

    try:
        event = json.loads(payload_str)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload",
        )

    event_type = event.get("eventType", "")
    print(f"[Creem Webhook] Received event: {event_type}")
    print(f"[Creem Webhook] Full payload: {json.dumps(event, indent=2, ensure_ascii=False)}")

    # 订阅事件
    if event_type == "subscription.active":
        await _handle_subscription_active(event)
    elif event_type == "subscription.paid":
        await _handle_subscription_paid(event)
    elif event_type == "subscription.expired":
        await _handle_subscription_expired(event)
    elif event_type == "subscription.canceled":
        await _handle_subscription_canceled(event)
    elif event_type == "subscription.scheduled_cancel":
        await _handle_subscription_scheduled_cancel(event)

    # 旧的一次性购买事件（兼容）
    elif event_type == "checkout.completed":
        await _handle_checkout_completed(event)

    return {"status": "ok"}


# ===== Subscription Webhook Handlers =====

async def _handle_subscription_active(event: dict):
    """处理 subscription.active 事件：激活用户订阅"""
    obj = event.get("object", {})
    if not obj:
        print("[Creem Webhook] No object in subscription.active event")
        return

    user_id = _extract_user_id(obj)
    if not user_id:
        print("[Creem Webhook] No user_id in subscription.active event")
        return

    creem_subscription_id = obj.get("id", "")
    product_info = obj.get("product", {})
    product_id = product_info.get("id", "")

    # 确定订阅计划
    plan = creem_service.get_plan_for_product(product_id)
    if not plan:
        print(f"[Creem Webhook] Unknown subscription product: {product_id}")
        return

    # 获取计费周期信息（Creem 用 _date 后缀，兼容旧字段名）
    current_period_start = obj.get("current_period_start_date") or obj.get("current_period_start")
    current_period_end = obj.get("current_period_end_date") or obj.get("current_period_end")
    creem_customer_id = obj.get("customer", {}).get("id")

    if db_service.is_available():
        await db_service.set_user_subscription(
            user_id=user_id,
            plan=plan,
            status="active",
            creem_subscription_id=creem_subscription_id,
            creem_customer_id=creem_customer_id,
            current_period_start=current_period_start,
            current_period_end=current_period_end,
        )
        print(f"[Creem Webhook] Subscription activated for user {user_id}, plan={plan}")


async def _handle_subscription_paid(event: dict):
    """处理 subscription.paid 事件：续费成功，延长订阅"""
    obj = event.get("object", {})
    if not obj:
        return

    user_id = _extract_user_id(obj)
    if not user_id:
        return

    creem_subscription_id = obj.get("id", "")
    current_period_start = obj.get("current_period_start_date") or obj.get("current_period_start")
    current_period_end = obj.get("current_period_end_date") or obj.get("current_period_end")

    if db_service.is_available():
        # 获取当前订阅信息以保留 plan
        sub = await db_service.get_user_subscription(user_id)
        plan = sub.get("plan", "early_adopter_monthly") if sub else "early_adopter_monthly"

        await db_service.set_user_subscription(
            user_id=user_id,
            plan=plan,
            status="active",
            creem_subscription_id=creem_subscription_id,
            current_period_start=current_period_start,
            current_period_end=current_period_end,
        )
        print(f"[Creem Webhook] Subscription renewed for user {user_id}")


async def _handle_subscription_expired(event: dict):
    """处理 subscription.expired 事件：订阅过期，撤销无限权限"""
    obj = event.get("object", {})
    if not obj:
        return

    user_id = _extract_user_id(obj)
    if not user_id:
        return

    if db_service.is_available():
        await db_service.expire_user_subscription(user_id)
        print(f"[Creem Webhook] Subscription expired for user {user_id}")


async def _handle_subscription_canceled(event: dict):
    """处理 subscription.canceled 事件：订阅已取消"""
    obj = event.get("object", {})
    if not obj:
        return

    user_id = _extract_user_id(obj)
    if not user_id:
        return

    if db_service.is_available():
        await db_service.cancel_user_subscription(user_id, immediate=True)
        print(f"[Creem Webhook] Subscription canceled for user {user_id}")


async def _handle_subscription_scheduled_cancel(event: dict):
    """处理 subscription.scheduled_cancel 事件：订阅将在到期后取消"""
    obj = event.get("object", {})
    if not obj:
        return

    user_id = _extract_user_id(obj)
    if not user_id:
        return

    if db_service.is_available():
        await db_service.cancel_user_subscription(user_id, immediate=False)
        print(f"[Creem Webhook] Subscription scheduled for cancel for user {user_id}")


# ===== Legacy Checkout Handler (兼容旧的一次性购买) =====

async def _handle_checkout_completed(event: dict):
    """处理 checkout.completed 事件：增加 1 credit（幂等，持久化到 DB）"""
    obj = event.get("object", {})
    if not obj:
        print("[Creem Webhook] No object in event")
        return

    checkout_id = obj.get("id", "")

    # 幂等：检查 DB 中是否已处理过该 checkout
    if checkout_id and db_service.is_available():
        already_processed = await db_service.is_checkout_processed(checkout_id)
        if already_processed:
            print(f"[Creem Webhook] Duplicate checkout event, skipping: {checkout_id}")
            return

    # 从 metadata 获取 user_id
    user_id = _extract_user_id(obj)

    if not user_id:
        print("[Creem Webhook] No user_id in metadata or custom_fields")
        return

    # 验证 product_id 匹配
    product_info = obj.get("product", {})
    product_id = product_info.get("id", "")

    # 如果是订阅产品的 checkout，由 subscription.active 事件处理
    if creem_service.is_subscription_product(product_id):
        print(f"[Creem Webhook] Subscription checkout completed, waiting for subscription.active event: {product_id}")
        return

    if not creem_service.is_valid_product(product_id):
        print(f"[Creem Webhook] Unknown product: {product_id}")
        return

    # 每次购买增加 1 credit
    if db_service.is_available():
        new_remaining = await db_service.increment_user_credits(user_id, 1)
        if new_remaining >= 0:
            # 记录已处理，防止重复
            if checkout_id:
                await db_service.mark_checkout_processed(checkout_id, user_id)
            print(f"[Creem Webhook] Added 1 credit for user {user_id}, new total: {new_remaining}")
        else:
            print(f"[Creem Webhook] Failed to increment credits for user {user_id}")
    else:
        print("[Creem Webhook] Database not available, cannot increment credits")


# ===== Helper =====

def _extract_user_id(obj: dict) -> Optional[str]:
    """从 webhook event object 中提取 user_id"""
    # 优先从 metadata 获取
    metadata = obj.get("metadata", {})
    user_id = metadata.get("user_id")

    if not user_id:
        # 尝试从 custom_fields 获取
        custom_fields = obj.get("custom_fields", [])
        for field in custom_fields:
            if field.get("name") == "user_id":
                user_id = field.get("value")
                break

    return user_id
