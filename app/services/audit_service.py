"""
Audit Service Module
审计日志服务：记录用户操作
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

from .supabase_client import get_supabase_client, is_supabase_enabled


class AuditAction(str, Enum):
    """审计操作类型"""
    ANALYSIS_STARTED = "analysis_started"
    ANALYSIS_COMPLETED = "analysis_completed"
    ANALYSIS_FAILED = "analysis_failed"
    TEMPLATE_CREATED = "template_created"
    TEMPLATE_DELETED = "template_deleted"
    PDF_EXPORTED = "pdf_exported"
    IMAGES_EXPORTED = "images_exported"
    LOGIN = "login"
    LOGOUT = "logout"
    REGISTER = "register"


class AuditService:
    """审计日志服务"""

    TABLE_AUDIT_LOGS = "audit_logs"

    def __init__(self):
        self.client = get_supabase_client()

    def is_available(self) -> bool:
        """检查审计服务是否可用"""
        return self.client is not None

    async def log(
        self,
        action: AuditAction,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        resource_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """
        记录审计日志

        Args:
            action: 操作类型
            user_id: 用户 ID
            user_email: 用户邮箱（本地用户可能没有 ID）
            resource_id: 相关资源 ID（如分析任务 ID）
            resource_type: 资源类型（如 "analysis", "template"）
            details: 额外详情（JSON）
            ip_address: 客户端 IP 地址
            user_agent: 客户端 User-Agent

        Returns:
            是否成功记录
        """
        if not self.client:
            print(f"[Audit] Database not available, skipping log: {action}")
            return False

        data = {
            "action": action.value if isinstance(action, AuditAction) else action,
            "user_id": user_id,
            "user_email": user_email,
            "resource_id": resource_id,
            "resource_type": resource_type,
            "details": details or {},
            "ip_address": ip_address,
            "user_agent": user_agent,
            "created_at": datetime.utcnow().isoformat()
        }

        try:
            self.client.table(self.TABLE_AUDIT_LOGS).insert(data).execute()
            print(f"[Audit] Logged: {action} by user {user_id or user_email}")
            return True
        except Exception as e:
            print(f"[Audit] Log failed: {e}")
            return False

    async def get_logs(
        self,
        limit: int = 100,
        offset: int = 0,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        获取审计日志列表

        Args:
            limit: 返回数量限制
            offset: 偏移量
            user_id: 按用户筛选
            action: 按操作类型筛选
            start_date: 开始时间
            end_date: 结束时间

        Returns:
            审计日志列表
        """
        if not self.client:
            return []

        try:
            query = self.client.table(self.TABLE_AUDIT_LOGS).select("*").order("created_at", desc=True)

            if user_id:
                query = query.eq("user_id", user_id)

            if action:
                query = query.eq("action", action)

            if start_date:
                query = query.gte("created_at", start_date.isoformat())

            if end_date:
                query = query.lte("created_at", end_date.isoformat())

            query = query.limit(limit).offset(offset)

            response = query.execute()
            return response.data or []
        except Exception as e:
            print(f"[Audit] Get logs failed: {e}")
            return []

    async def get_user_action_count(
        self,
        user_id: str,
        action: AuditAction,
        since: Optional[datetime] = None
    ) -> int:
        """
        获取用户某操作的次数

        Args:
            user_id: 用户 ID
            action: 操作类型
            since: 从何时开始计算

        Returns:
            操作次数
        """
        if not self.client:
            return 0

        try:
            query = self.client.table(self.TABLE_AUDIT_LOGS).select("id", count="exact").eq("user_id", user_id).eq("action", action.value)

            if since:
                query = query.gte("created_at", since.isoformat())

            response = query.execute()
            return response.count or 0
        except Exception as e:
            print(f"[Audit] Get count failed: {e}")
            return 0

    async def get_stats_summary(self, days: int = 7) -> Dict[str, Any]:
        """
        获取审计统计摘要

        Args:
            days: 统计最近多少天

        Returns:
            统计摘要
        """
        if not self.client:
            return {}

        start_date = datetime.utcnow() - timedelta(days=days)

        try:
            response = self.client.table(self.TABLE_AUDIT_LOGS).select("action, created_at").gte("created_at", start_date.isoformat()).execute()

            logs = response.data or []

            # 按操作类型统计
            action_counts = {}
            for log in logs:
                action = log.get("action", "unknown")
                action_counts[action] = action_counts.get(action, 0) + 1

            return {
                "period_days": days,
                "total_logs": len(logs),
                "action_counts": action_counts
            }
        except Exception as e:
            print(f"[Audit] Get stats failed: {e}")
            return {}


from datetime import timedelta

# 单例实例
audit_service = AuditService()