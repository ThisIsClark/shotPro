"""
Database Service Module
数据库操作服务：分析任务的 CRUD 操作
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID

from .supabase_client import get_supabase_client, is_supabase_enabled


class DatabaseService:
    """数据库操作服务"""

    TABLE_ANALYSES = "analyses"
    TABLE_USER_TEMPLATES = "user_templates"
    TABLE_USER_CREDITS = "user_credits"
    TABLE_PAYMENT_CHECKOUTS = "payment_checkouts"
    TABLE_USER_SUBSCRIPTIONS = "user_subscriptions"

    FREE_CREDITS = 3  # 新用户免费次数

    def __init__(self):
        self.client = get_supabase_client()

    def is_available(self) -> bool:
        """检查数据库是否可用"""
        return self.client is not None

    # ===== Analysis CRUD =====

    async def create_analysis(
        self,
        analysis_id: Optional[str] = None,
        user_id: Optional[str] = None,
        video_filename: str = "",
        video_path: str = "",
        shooting_hand: str = "right",
        shooting_style: str = "one_motion",
        template_id: Optional[str] = None,
        generate_video: bool = False,
        generate_skeleton_video: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        创建分析任务记录

        Args:
            analysis_id: 可选，预生成的任务 ID（如果为 None，数据库会自动生成）

        Returns:
            包含 id 的记录字典，失败返回 None
        """
        if not self.client:
            return None

        data = {
            "user_id": user_id,
            "video_filename": video_filename,
            "video_path": video_path,
            "shooting_hand": shooting_hand,
            "shooting_style": shooting_style,
            "template_id": template_id,
            "generate_video": generate_video,
            "generate_skeleton_video": generate_skeleton_video,
            "status": "pending",
            "progress": 0
        }

        # 如果提供了预生成的 ID，使用它
        if analysis_id:
            data["id"] = analysis_id

        try:
            response = self.client.table(self.TABLE_ANALYSES).insert(data).execute()
            if response.data:
                return response.data[0]
        except Exception as e:
            print(f"[DB] Create analysis failed: {e}")

        return None

    async def get_analysis(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """获取单个分析记录"""
        if not self.client:
            return None

        try:
            response = self.client.table(self.TABLE_ANALYSES).select("*").eq("id", analysis_id).execute()
            if response.data:
                return response.data[0]
        except Exception as e:
            print(f"[DB] Get analysis failed: {e}")

        return None

    async def update_analysis(
        self,
        analysis_id: str,
        status: Optional[str] = None,
        progress: Optional[int] = None,
        error_message: Optional[str] = None,
        overall_score: Optional[float] = None,
        rating: Optional[str] = None,
        total_frames: Optional[int] = None,
        fps: Optional[float] = None,
        duration: Optional[float] = None,
        result_path: Optional[str] = None
    ) -> bool:
        """更新分析记录"""
        if not self.client:
            return False

        update_data = {}

        if status is not None:
            update_data["status"] = status
        if progress is not None:
            update_data["progress"] = progress
        if error_message is not None:
            update_data["error_message"] = error_message
        if overall_score is not None:
            update_data["overall_score"] = overall_score
        if rating is not None:
            update_data["rating"] = rating
        if total_frames is not None:
            update_data["total_frames"] = total_frames
        if fps is not None:
            update_data["fps"] = fps
        if duration is not None:
            update_data["duration"] = duration
        if result_path is not None:
            update_data["result_path"] = result_path

        # 完成时设置 completed_at
        if status == "completed":
            update_data["completed_at"] = datetime.utcnow().isoformat()

        if not update_data:
            return True

        try:
            self.client.table(self.TABLE_ANALYSES).update(update_data).eq("id", analysis_id).execute()
            return True
        except Exception as e:
            print(f"[DB] Update analysis failed: {e}")
            return False

    async def delete_analysis(self, analysis_id: str) -> bool:
        """删除分析记录"""
        if not self.client:
            return False

        try:
            self.client.table(self.TABLE_ANALYSES).delete().eq("id", analysis_id).execute()
            return True
        except Exception as e:
            print(f"[DB] Delete analysis failed: {e}")
            return False

    async def get_user_analyses(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
        status_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """获取用户的分析历史"""
        if not self.client:
            return []

        try:
            query = self.client.table(self.TABLE_ANALYSES).select("*").eq("user_id", user_id).order("created_at", desc=True)

            if status_filter:
                query = query.eq("status", status_filter)

            query = query.limit(limit).offset(offset)

            response = query.execute()
            return response.data or []
        except Exception as e:
            print(f"[DB] Get user analyses failed: {e}")
            return []

    async def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """获取用户统计数据"""
        if not self.client:
            return {}

        try:
            # 获取所有完成的分析
            response = self.client.table(self.TABLE_ANALYSES).select("overall_score, status").eq("user_id", user_id).execute()

            analyses = response.data or []
            total = len(analyses)
            completed = len([a for a in analyses if a.get("status") == "completed"])
            scores = [a.get("overall_score") for a in analyses if a.get("status") == "completed" and a.get("overall_score") is not None]

            return {
                "total_analyses": total,
                "completed_analyses": completed,
                "average_score": sum(scores) / len(scores) if scores else None,
                "best_score": max(scores) if scores else None
            }
        except Exception as e:
            print(f"[DB] Get user stats failed: {e}")
            return {}

    # ===== User Templates =====

    async def create_user_template(
        self,
        user_id: str,
        name: str,
        description: Optional[str] = None,
        shooting_hand: str = "right",
        key_frames: Optional[List[Dict]] = None,
        is_public: bool = False
    ) -> Optional[Dict[str, Any]]:
        """创建用户模板"""
        if not self.client:
            return None

        data = {
            "user_id": user_id,
            "name": name,
            "description": description,
            "shooting_hand": shooting_hand,
            "key_frames": key_frames or [],
            "is_public": is_public
        }

        try:
            response = self.client.table(self.TABLE_USER_TEMPLATES).insert(data).execute()
            if response.data:
                return response.data[0]
        except Exception as e:
            print(f"[DB] Create user template failed: {e}")

        return None

    async def get_user_templates(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户的模板列表"""
        if not self.client:
            return []

        try:
            response = self.client.table(self.TABLE_USER_TEMPLATES).select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
            return response.data or []
        except Exception as e:
            print(f"[DB] Get user templates failed: {e}")
            return []

    async def get_public_templates(self) -> List[Dict[str, Any]]:
        """获取公开模板列表"""
        if not self.client:
            return []

        try:
            response = self.client.table(self.TABLE_USER_TEMPLATES).select("*").eq("is_public", True).order("created_at", desc=True).execute()
            return response.data or []
        except Exception as e:
            print(f"[DB] Get public templates failed: {e}")
            return []

    async def delete_user_template(self, template_id: str, user_id: str) -> bool:
        """删除用户模板（需要验证所有权）"""
        if not self.client:
            return False

        try:
            response = self.client.table(self.TABLE_USER_TEMPLATES).delete().eq("id", template_id).eq("user_id", user_id).execute()
            return True
        except Exception as e:
            print(f"[DB] Delete user template failed: {e}")
            return False

    # ===== User Credits =====

    async def get_user_credits(self, user_id: str) -> int:
        """
        获取用户剩余分析次数。若无记录则自动初始化。
        订阅用户返回 999（表示无限）。

        Returns:
            剩余次数，-1 表示查询失败，999 表示订阅用户（无限）
        """
        if not self.client:
            return -1

        try:
            # 先检查是否有活跃订阅
            if await self.is_user_subscribed(user_id):
                return 999  # 订阅用户，无限次数

            response = self.client.table(self.TABLE_USER_CREDITS).select("credits_remaining").eq("user_id", user_id).execute()
            if response.data:
                return response.data[0]["credits_remaining"]

            # 无记录，自动初始化
            init_response = self.client.table(self.TABLE_USER_CREDITS).insert({
                "user_id": user_id,
                "credits_remaining": self.FREE_CREDITS,
                "total_granted": self.FREE_CREDITS
            }).execute()

            if init_response.data:
                print(f"[DB] Initialized credits for user {user_id}: {self.FREE_CREDITS}")
                return self.FREE_CREDITS

            return -1
        except Exception as e:
            print(f"[DB] Get user credits failed: {e}")
            return -1

    async def decrement_user_credits(self, user_id: str) -> int:
        """
        扣减一次分析次数。订阅用户不扣减。

        Returns:
            扣减后的剩余次数，-1 表示失败，999 表示订阅用户（无限）
        """
        if not self.client:
            return -1

        try:
            # 订阅用户不扣减
            if await self.is_user_subscribed(user_id):
                return 999

            # 先获取当前次数
            remaining = await self.get_user_credits(user_id)
            if remaining <= 0:
                return remaining

            # 扣减
            new_remaining = remaining - 1
            self.client.table(self.TABLE_USER_CREDITS).update({
                "credits_remaining": new_remaining,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("user_id", user_id).execute()

            print(f"[DB] Credits decremented for user {user_id}: {remaining} -> {new_remaining}")
            return new_remaining
        except Exception as e:
            print(f"[DB] Decrement user credits failed: {e}")
            return -1

    async def increment_user_credits(self, user_id: str, amount: int) -> int:
        """
        增加用户分析次数（购买后调用）。

        Args:
            user_id: 用户 ID
            amount: 增加的次数

        Returns:
            增加后的剩余次数，-1 表示失败
        """
        if not self.client:
            return -1

        try:
            remaining = await self.get_user_credits(user_id)
            if remaining < 0:
                # 无记录会自动初始化，初始化后再增加
                remaining = await self.get_user_credits(user_id)
                if remaining < 0:
                    return -1

            new_remaining = remaining + amount

            # 获取当前 total_granted
            grant_response = self.client.table(self.TABLE_USER_CREDITS).select("total_granted").eq("user_id", user_id).execute()
            current_granted = grant_response.data[0]["total_granted"] if grant_response.data else self.FREE_CREDITS

            self.client.table(self.TABLE_USER_CREDITS).update({
                "credits_remaining": new_remaining,
                "total_granted": current_granted + amount,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("user_id", user_id).execute()

            print(f"[DB] Credits incremented for user {user_id}: {remaining} -> {new_remaining} (+{amount})")
            return new_remaining
        except Exception as e:
            print(f"[DB] Increment user credits failed: {e}")
            return -1

    # ===== Payment Checkout Tracking (幂等) =====

    async def is_checkout_processed(self, checkout_id: str) -> bool:
        """检查 checkout 是否已处理过"""
        if not self.client:
            return False

        try:
            response = self.client.table(self.TABLE_PAYMENT_CHECKOUTS).select("id").eq("checkout_id", checkout_id).execute()
            return bool(response.data)
        except Exception as e:
            print(f"[DB] Check checkout processed failed: {e}")
            return False

    async def mark_checkout_processed(self, checkout_id: str, user_id: str) -> bool:
        """记录已处理的 checkout"""
        if not self.client:
            return False

        try:
            self.client.table(self.TABLE_PAYMENT_CHECKOUTS).insert({
                "checkout_id": checkout_id,
                "user_id": user_id,
                "processed_at": datetime.utcnow().isoformat(),
            }).execute()
            print(f"[DB] Checkout {checkout_id} marked as processed")
            return True
        except Exception as e:
            # 唯一约束冲突说明已存在，视为成功
            if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                print(f"[DB] Checkout {checkout_id} already recorded (race condition)")
                return True
            print(f"[DB] Mark checkout processed failed: {e}")
            return False

    # ===== User Subscriptions =====

    async def is_user_subscribed(self, user_id: str) -> bool:
        """
        检查用户是否有活跃订阅

        包括 active、scheduled_cancel，以及 expired 但 current_period_end 尚未到达的订阅

        Returns:
            True 如果用户有活跃订阅
        """
        if not self.client:
            return False

        try:
            response = self.client.table(self.TABLE_USER_SUBSCRIPTIONS).select("status, current_period_end").eq("user_id", user_id).execute()
            if not response.data:
                return False

            for sub in response.data:
                status = sub.get("status")
                if status in ("active", "scheduled_cancel"):
                    return True
                # expired 但计费周期未结束，仍视为有效
                if status == "expired":
                    period_end = sub.get("current_period_end")
                    if period_end:
                        from datetime import timezone
                        try:
                            end_time = datetime.fromisoformat(period_end.replace("Z", "+00:00")) if isinstance(period_end, str) else period_end
                            if end_time > datetime.now(timezone.utc):
                                return True
                        except Exception:
                            pass

            return False
        except Exception as e:
            print(f"[DB] Check user subscribed failed: {e}")
            return False

    async def get_user_subscription(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取用户当前活跃订阅

        包括 active、scheduled_cancel，以及 expired 但 current_period_end 尚未到达的订阅
        （用户取消后仍享有权限直到计费周期结束）

        Returns:
            订阅信息字典，无订阅返回 None
        """
        if not self.client:
            return None

        try:
            response = self.client.table(self.TABLE_USER_SUBSCRIPTIONS).select("*").eq("user_id", user_id).order("created_at", desc=True).limit(1).execute()
            if response.data:
                sub = response.data[0]
                status = sub.get("status")
                if status in ("active", "scheduled_cancel"):
                    return sub
                # expired 但计费周期未结束，仍视为有效
                if status == "expired":
                    period_end = sub.get("current_period_end")
                    if period_end:
                        from datetime import timezone
                        try:
                            end_time = datetime.fromisoformat(period_end.replace("Z", "+00:00")) if isinstance(period_end, str) else period_end
                            if end_time > datetime.now(timezone.utc):
                                return sub
                        except Exception:
                            pass
            return None
        except Exception as e:
            print(f"[DB] Get user subscription failed: {e}")
            return None

    async def set_user_subscription(
        self,
        user_id: str,
        plan: str,
        status: str,
        creem_subscription_id: Optional[str] = None,
        creem_customer_id: Optional[str] = None,
        current_period_start: Optional[str] = None,
        current_period_end: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        创建或更新用户订阅

        Args:
            plan: 'early_adopter_monthly', 'early_adopter_yearly', 'regular'
            status: 'active', 'canceled', 'expired', 'scheduled_cancel'
            creem_subscription_id: Creem 订阅 ID
            creem_customer_id: Creem 客户 ID
            current_period_start: 当前计费周期开始时间
            current_period_end: 当前计费周期结束时间
        """
        if not self.client:
            return None

        try:
            # 先查找是否已有该 creem_subscription_id 的记录
            if creem_subscription_id:
                existing = self.client.table(self.TABLE_USER_SUBSCRIPTIONS).select("*").eq("creem_subscription_id", creem_subscription_id).execute()
                if existing.data:
                    # 更新已有记录
                    update_data = {
                        "status": status,
                        "updated_at": datetime.utcnow().isoformat(),
                    }
                    if plan:
                        update_data["plan"] = plan
                    if current_period_start:
                        update_data["current_period_start"] = current_period_start
                    if current_period_end:
                        update_data["current_period_end"] = current_period_end
                    if creem_customer_id:
                        update_data["creem_customer_id"] = creem_customer_id

                    resp = self.client.table(self.TABLE_USER_SUBSCRIPTIONS).update(update_data).eq("creem_subscription_id", creem_subscription_id).execute()
                    print(f"[DB] Updated subscription for user {user_id}: status={status}, plan={plan}")
                    return resp.data[0] if resp.data else None

            # 查找用户是否有活跃订阅
            existing_sub = await self.get_user_subscription(user_id)

            if existing_sub:
                # 更新已有订阅
                update_data = {
                    "status": status,
                    "updated_at": datetime.utcnow().isoformat(),
                }
                if plan:
                    update_data["plan"] = plan
                if creem_subscription_id:
                    update_data["creem_subscription_id"] = creem_subscription_id
                if creem_customer_id:
                    update_data["creem_customer_id"] = creem_customer_id
                if current_period_start:
                    update_data["current_period_start"] = current_period_start
                if current_period_end:
                    update_data["current_period_end"] = current_period_end

                resp = self.client.table(self.TABLE_USER_SUBSCRIPTIONS).update(update_data).eq("id", existing_sub["id"]).execute()
                print(f"[DB] Updated subscription for user {user_id}: status={status}, plan={plan}")
                return resp.data[0] if resp.data else None

            # 创建新订阅记录
            data = {
                "user_id": user_id,
                "plan": plan,
                "status": status,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
            if creem_subscription_id:
                data["creem_subscription_id"] = creem_subscription_id
            if creem_customer_id:
                data["creem_customer_id"] = creem_customer_id
            if current_period_start:
                data["current_period_start"] = current_period_start
            if current_period_end:
                data["current_period_end"] = current_period_end

            resp = self.client.table(self.TABLE_USER_SUBSCRIPTIONS).insert(data).execute()
            print(f"[DB] Created subscription for user {user_id}: status={status}, plan={plan}")
            return resp.data[0] if resp.data else None

        except Exception as e:
            print(f"[DB] Set user subscription failed: {e}")
            return None

    async def cancel_user_subscription(self, user_id: str, immediate: bool = False) -> bool:
        """
        取消用户订阅

        Args:
            immediate: True 立即取消，False 标记为 scheduled_cancel（到期后取消）
        """
        if not self.client:
            return False

        try:
            sub = await self.get_user_subscription(user_id)
            if not sub:
                print(f"[DB] No active subscription to cancel for user {user_id}")
                return False

            new_status = "expired" if immediate else "scheduled_cancel"
            update_data = {
                "status": new_status,
                "updated_at": datetime.utcnow().isoformat(),
            }
            if immediate:
                update_data["canceled_at"] = datetime.utcnow().isoformat()

            self.client.table(self.TABLE_USER_SUBSCRIPTIONS).update(update_data).eq("id", sub["id"]).execute()
            print(f"[DB] Subscription canceled for user {user_id}: status={new_status}")
            return True
        except Exception as e:
            print(f"[DB] Cancel user subscription failed: {e}")
            return False

    async def expire_user_subscription(self, user_id: str) -> bool:
        """将用户订阅标记为过期"""
        if not self.client:
            return False

        try:
            # 将所有 active/scheduled_cancel 的订阅标记为 expired
            for status in ("active", "scheduled_cancel"):
                self.client.table(self.TABLE_USER_SUBSCRIPTIONS).update({
                    "status": "expired",
                    "updated_at": datetime.utcnow().isoformat(),
                }).eq("user_id", user_id).eq("status", status).execute()

            print(f"[DB] Subscription expired for user {user_id}")
            return True
        except Exception as e:
            print(f"[DB] Expire user subscription failed: {e}")
            return False


# 单例实例
db_service = DatabaseService()