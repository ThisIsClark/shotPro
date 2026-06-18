"""
Creem Payment Service
Creem 支付服务：封装 Creem API 调用（创建 checkout、验证 webhook 签名）

定价方案：$1.49/次（单次购买，买一次加 1 credit）
"""

import hmac
import hashlib
import httpx
from typing import Optional, Dict, Any

from ..config import settings

# 单价
PRICE_PER_CREDIT = 1.49


class CreemService:
    """Creem 支付服务"""

    TEST_BASE_URL = "https://test-api.creem.io"
    LIVE_BASE_URL = "https://api.creem.io"

    def __init__(self):
        self.api_key = settings.creem_api_key
        self.webhook_secret = settings.creem_webhook_secret
        self.product_id = settings.creem_product_id
        self._test_mode = self.api_key.startswith("creem_test_") if self.api_key else False

    @property
    def is_configured(self) -> bool:
        """检查 Creem 是否已配置"""
        return bool(self.api_key and self.product_id)

    @property
    def base_url(self) -> str:
        return self.TEST_BASE_URL if self._test_mode else self.LIVE_BASE_URL

    async def create_checkout(
        self,
        user_id: str,
        user_email: Optional[str] = None,
        origin: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        创建 Creem checkout session（$1.49/次）

        Args:
            user_id: 当前用户 ID（存入 metadata，webhook 回调用）
            user_email: 用户邮箱（可选，预填 checkout 页面）
            origin: 前端请求来源（用于构造 success_url，优先于 settings.app_url）

        Returns:
            {"checkout_url": "...", "checkout_id": "..."} 或 None
        """
        if not self.is_configured:
            print("[Creem] API key or product_id not configured")
            return None

        url = f"{self.base_url}/v1/checkouts"

        # success_url 优先使用前端 origin，确保用户付款后回到原页面（保持登录态）
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
        """检查 product_id 是否为配置的产品"""
        return product_id == settings.creem_product_id

    @staticmethod
    def get_product_info() -> Optional[Dict[str, Any]]:
        """获取产品信息"""
        if not settings.creem_product_id:
            return None
        return {
            "product_id": settings.creem_product_id,
            "name": "Shot Analysis",
            "credits": 1,
            "price": f"${PRICE_PER_CREDIT}",
            "original_price": "$2.99",
            "discount": "50%",
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
