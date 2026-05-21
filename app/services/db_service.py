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


# 单例实例
db_service = DatabaseService()