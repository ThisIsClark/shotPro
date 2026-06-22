"""
Creem Payment Service
Creem 支付服务：封装 Creem API 调用（创建 checkout、验证 webhook 签名）

定价方案：
- Early Adopter 月付：$4.99/月（无限次分析，锁定价格）
- Early Adopter 年付：$39.99/年（无限次分析，锁定价格，约 $3.33/月）
- Regular Price：$7.99/月（加评分体系、改善建议、进步曲线后对新用户生效）
- Free：注册送 3 次免费分析
"""

import hmac
import hashlib
import httpx
from typing import Optional, Dict, Any, List

from ..config import settings

# 订阅价格（显示用）
EARLY_ADOPTER_MONTHLY_PRICE = 4.99
EARLY_ADOPTER_YEARLY_PRICE = 39.99
REGULAR_MONTHLY_PRICE = 7.99


class CreemService:
    """Creem 支付服务"""

    TEST_BASE_URL = "https://test-api.creem.io"
    LIVE_BASE_URL = "https://api.creem.io"

    def __init__(self):
        self.api_key = settings.creem_api_key
        self.webhook_secret = settings.creem_webhook_secret
        self.product_id = settings.creem_product_id  # 旧的一次性购买产品
        self.monthly_product_id = settings.creem_monthly_product_id
        self.yearly_product_id = settings.creem_yearly_product_id
        self._test_mode = self.api_key.startswith("creem_test_") if self.api_key else False

    @property
    def is_configured(self) -> bool:
        """检查 Creem 是否已配置（至少有一个产品 ID）"""
        return bool(self.api_key and (self.product_id or self.monthly_product_id or self.yearly_product_id))

    @property
    def is_subscription_configured(self) -> bool:
        """检查订阅产品是否已配置"""
        return bool(self.api_key and (self.monthly_product_id or self.yearly_product_id))

    @property
    def base_url(self) -> str:
        return self.TEST_BASE_URL if self._test_mode else self.LIVE_BASE_URL

    async def create_subscription_checkout(
        self,
        user_id: str,
        billing_period: str,
        user_email: Optional[str] = None,
        origin: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        创建 Creem 订阅 checkout session

        Args:
            user_id: 当前用户 ID（存入 metadata，webhook 回调用）
            billing_period: "monthly" 或 "yearly"
            user_email: 用户邮箱（可选，预填 checkout 页面）
            origin: 前端请求来源（用于构造 success_url）

        Returns:
            {"checkout_url": "...", "checkout_id": "..."} 或 None
        """
        product_id = self.monthly_product_id if billing_period == "monthly" else self.yearly_product_id

        if not product_id:
            print(f"[Creem] No product_id configured for billing_period: {billing_period}")
            return None

        if not self.api_key:
            print("[Creem] API key not configured")
            return None

        url = f"{self.base_url}/v1/checkouts"
        success_origin = origin or _get_app_url()

        payload: Dict[str, Any] = {
            "product_id": product_id,
            "success_url": f"{success_origin}/app?payment=success",
            "metadata": {
                "user_id": user_id,
                "billing_period": billing_period,
            },
        }

        if user_email:
            payload["customer"] = {"email": user_email}

        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, json=payload, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    print(f"[Creem] Subscription checkout created: {data.get('id')} for {billing_period}")
                    return {
                        "checkout_url": data.get("checkout_url"),
                        "checkout_id": data.get("id"),
                    }
                else:
                    print(f"[Creem] Create subscription checkout failed: {response.status_code} {response.text}")
                    return None

        except httpx.TimeoutException:
            print("[Creem] Create subscription checkout timeout")
            return None
        except Exception as e:
            print(f"[Creem] Create subscription checkout error: {e}")
            return None

    async def cancel_subscription(self, creem_subscription_id: str, mode: str = "scheduled") -> bool:
        """
        取消 Creem 订阅

        Args:
            creem_subscription_id: Creem 订阅 ID
            mode: "scheduled"（到期后取消）或 "immediate"（立即取消）

        Returns:
            是否成功
        """
        if not self.api_key:
            print("[Creem] API key not configured")
            return False

        url = f"{self.base_url}/v1/subscriptions/{creem_subscription_id}/cancel"
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }

        payload = {}
        if mode == "immediate":
            payload["mode"] = "immediate"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, json=payload, headers=headers)

                if response.status_code == 200:
                    print(f"[Creem] Subscription {creem_subscription_id} canceled (mode={mode})")
                    return True
                else:
                    print(f"[Creem] Cancel subscription failed: {response.status_code} {response.text}")
                    return False

        except Exception as e:
            print(f"[Creem] Cancel subscription error: {e}")
            return False

    async def create_checkout(
        self,
        user_id: str,
        user_email: Optional[str] = None,
        origin: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        创建 Creem checkout session（旧的一次性购买，保留兼容）

        Args:
            user_id: 当前用户 ID（存入 metadata，webhook 回调用）
            user_email: 用户邮箱（可选，预填 checkout 页面）
            origin: 前端请求来源（用于构造 success_url，优先于 settings.app_url）

        Returns:
            {"checkout_url": "...", "checkout_id": "..."} 或 None
        """
        if not self.api_key or not self.product_id:
            print("[Creem] API key or product_id not configured")
            return None

        url = f"{self.base_url}/v1/checkouts"

        success_origin = origin or _get_app_url()

        payload: Dict[str, Any] = {
            "product_id": self.product_id,
            "success_url": f"{success_origin}/app?payment=success",
            "metadata": {
                "user_id": user_id,
            },
        }

        if user_email:
            payload["customer"] = {"email": user_email}

        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, json=payload, headers=headers)

                if response.status_code == 200:
                    data = response.json()
                    print(f"[Creem] Checkout created: {data.get('id')}")
                    return {
                        "checkout_url": data.get("checkout_url"),
                        "checkout_id": data.get("id"),
                    }
                else:
                    print(f"[Creem] Create checkout failed: {response.status_code} {response.text}")
                    return None

        except httpx.TimeoutException:
            print("[Creem] Create checkout timeout")
            return None
        except Exception as e:
            print(f"[Creem] Create checkout error: {e}")
            return None

    def verify_webhook_signature(self, payload: str, signature: str) -> bool:
        """验证 Creem webhook 签名"""
        if not self.webhook_secret:
            print("[Creem] Webhook secret not configured")
            return False

        computed = hmac.new(
            self.webhook_secret.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(computed, signature)

    @staticmethod
    def is_valid_product(product_id: str) -> bool:
        """检查 product_id 是否为配置的产品（含订阅产品）"""
        return product_id in (
            settings.creem_product_id,
            settings.creem_monthly_product_id,
            settings.creem_yearly_product_id,
        )

    @staticmethod
    def is_subscription_product(product_id: str) -> bool:
        """检查 product_id 是否为订阅产品"""
        return product_id in (
            settings.creem_monthly_product_id,
            settings.creem_yearly_product_id,
        )

    @staticmethod
    def get_plan_for_product(product_id: str) -> Optional[str]:
        """根据 product_id 获取对应的 plan 名称"""
        if product_id == settings.creem_monthly_product_id:
            return "early_adopter_monthly"
        elif product_id == settings.creem_yearly_product_id:
            return "early_adopter_yearly"
        return None

    @staticmethod
    def get_plans_info() -> List[Dict[str, Any]]:
        """获取订阅计划信息"""
        plans = [
            {
                "plan": "free",
                "name": "Free",
                "price": 0,
                "price_display": "$0",
                "credits": 3,
                "is_unlimited": False,
                "description": "3 free analyses on signup",
                "description_zh": "注册送 3 次免费分析",
            },
        ]

        if settings.creem_monthly_product_id:
            plans.append({
                "plan": "early_adopter_monthly",
                "name": "Early Adopter Monthly",
                "price": EARLY_ADOPTER_MONTHLY_PRICE,
                "price_display": f"${EARLY_ADOPTER_MONTHLY_PRICE}",
                "price_unit": "/month",
                "regular_price": REGULAR_MONTHLY_PRICE,
                "regular_price_display": f"${REGULAR_MONTHLY_PRICE}",
                "product_id": settings.creem_monthly_product_id,
                "is_unlimited": True,
                "is_early_adopter": True,
                "description": "Unlimited analyses + power transfer report. Lock in this price forever.",
                "description_zh": "无限次分析 + 发力脱节检测报告。锁定此价格，后续涨价不影响。",
            })

        if settings.creem_yearly_product_id:
            plans.append({
                "plan": "early_adopter_yearly",
                "name": "Early Adopter Yearly",
                "price": EARLY_ADOPTER_YEARLY_PRICE,
                "price_display": f"${EARLY_ADOPTER_YEARLY_PRICE}",
                "price_unit": "/year",
                "monthly_equivalent": f"${EARLY_ADOPTER_YEARLY_PRICE / 12:.2f}/month",
                "regular_price": REGULAR_MONTHLY_PRICE * 12,
                "regular_price_display": f"${REGULAR_MONTHLY_PRICE * 12:.0f}",
                "product_id": settings.creem_yearly_product_id,
                "is_unlimited": True,
                "is_early_adopter": True,
                "is_best_value": True,
                "description": f"Unlimited analyses + power transfer report. ~${EARLY_ADOPTER_YEARLY_PRICE / 12:.2f}/month, lock in forever.",
                "description_zh": f"无限次分析 + 发力脱节检测报告。约 ${EARLY_ADOPTER_YEARLY_PRICE / 12:.2f}/月，锁定此价格。",
            })

        return plans

    @staticmethod
    def get_product_info() -> Optional[Dict[str, Any]]:
        """获取旧的一次性购买产品信息（兼容）"""
        if not settings.creem_product_id:
            return None
        return {
            "product_id": settings.creem_product_id,
            "name": "Shot Analysis",
            "credits": 1,
            "price": "$1.49",
        }


def _get_app_url() -> str:
    """获取应用的基础 URL（用于构造 success_url）"""
    if settings.app_url:
        return settings.app_url.rstrip("/")

    import os
    space_host = os.getenv("SPACE_HOST", "")
    if space_host:
        return f"https://{space_host}"

    return "http://localhost:8000"


# 单例实例
creem_service = CreemService()
