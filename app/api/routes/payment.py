"""
Payment API Routes
付款 API 路由：Creem checkout 创建、Webhook 回调

定价：$1.49/次，每次购买增加 1 credit
"""

import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from ..deps import get_current_user_optional
from ...services.creem_service import creem_service
from ...services.db_service import db_service

router = APIRouter(prefix="/payment", tags=["payment"])


# ===== Response Models =====

class CheckoutResponse(BaseModel):
    checkout_url: str
    checkout_id: Optional[str] = None


class ProductInfo(BaseModel):
    product_id: str
    name: str
    credits: int
    price: str


# ===== Routes =====

@router.get("/products", response_model=list[ProductInfo])
async def get_products():
    """获取产品信息"""
    info = creem_service.get_product_info()
    if info:
        return [ProductInfo(**info)]
    return []


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    request: Request,
    user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    创建 Creem checkout session（$1.49/次）

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
            detail="Local admin accounts have unlimited credits"
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Login required to purchase credits",
        )

    if not creem_service.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment service is not configured",
        )

    # 用前端请求的 origin 作为 success_url，确保付款后回到原页面（保持登录态）
    origin = str(request.base_url).rstrip("/")
    result = await creem_service.create_checkout(
        user_id=user_id,
        user_email=user_email,
        origin=origin,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session",
        )

    return CheckoutResponse(
        checkout_url=result["checkout_url"],
        checkout_id=result.get("checkout_id"),
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

    if event_type == "checkout.completed":
        await _handle_checkout_completed(event)

    return {"status": "ok"}


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
    metadata = obj.get("metadata", {})
    user_id = metadata.get("user_id")

    if not user_id:
        custom_fields = obj.get("custom_fields", [])
        for field in custom_fields:
            if field.get("name") == "user_id":
                user_id = field.get("value")
                break

    if not user_id:
        print("[Creem Webhook] No user_id in metadata or custom_fields")
        return

    # 验证 product_id 匹配
    product_info = obj.get("product", {})
    product_id = product_info.get("id", "")

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
