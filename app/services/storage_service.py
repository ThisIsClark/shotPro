"""
Supabase Storage Service Module
文件存储服务：视频和图片上传到 Supabase Storage
"""

import os
from pathlib import Path
from typing import Optional, BinaryIO
from datetime import datetime

from .supabase_client import get_supabase_client, is_supabase_enabled


class StorageService:
    """Supabase Storage 文件上传服务"""

    BUCKET_VIDEOS = "videos"
    BUCKET_RESULTS = "results"

    def __init__(self):
        self.client = get_supabase_client()

    def is_available(self) -> bool:
        """检查 Storage 服务是否可用"""
        return self.client is not None

    def upload_video(
        self,
        file_path: Path,
        user_id: Optional[str] = None,
        task_id: str = ""
    ) -> Optional[str]:
        """
        上传视频文件到 Supabase Storage

        Args:
            file_path: 本地视频文件路径
            user_id: 用户 ID（可选）
            task_id: 任务 ID

        Returns:
            上传成功返回 Storage URL，失败返回 None
        """
        if not self.client or not file_path.exists():
            return None

        try:
            # 构建存储路径: {user_id}/{task_id}/video.mp4
            if user_id:
                storage_path = f"{user_id}/{task_id}/{file_path.name}"
            else:
                storage_path = f"public/{task_id}/{file_path.name}"

            # 读取文件内容
            with open(file_path, 'rb') as f:
                file_content = f.read()

            # 上传到 Supabase Storage
            response = self.client.storage.from_(self.BUCKET_VIDEOS).upload(
                storage_path,
                file_content,
                file_options={
                    "content-type": "video/mp4",
                    "upsert": "true"  # 允许覆盖同名文件
                }
            )

            if response:
                # 获取公开 URL
                public_url = self.client.storage.from_(self.BUCKET_VIDEOS).get_public_url(storage_path)
                return public_url

        except Exception as e:
            print(f"[Storage] Video upload failed: {e}")

        return None

    def upload_video_bytes(
        self,
        file_content: bytes,
        filename: str,
        user_id: Optional[str] = None,
        task_id: str = ""
    ) -> Optional[str]:
        """
        直接上传视频字节内容到 Supabase Storage

        Args:
            file_content: 文件字节内容
            filename: 文件名
            user_id: 用户 ID（可选）
            task_id: 任务 ID

        Returns:
            上传成功返回 Storage URL
        """
        if not self.client:
            return None

        try:
            # 构建存储路径
            if user_id:
                storage_path = f"{user_id}/{task_id}/{filename}"
            else:
                storage_path = f"public/{task_id}/{filename}"

            # 上传
            response = self.client.storage.from_(self.BUCKET_VIDEOS).upload(
                storage_path,
                file_content,
                file_options={
                    "content-type": "video/mp4",
                    "upsert": "true"
                }
            )

            if response:
                public_url = self.client.storage.from_(self.BUCKET_VIDEOS).get_public_url(storage_path)
                return public_url

        except Exception as e:
            print(f"[Storage] Video bytes upload failed: {e}")

        return None

    def upload_result_image(
        self,
        file_path: Path,
        user_id: Optional[str] = None,
        task_id: str = "",
        image_name: str = ""
    ) -> Optional[str]:
        """
        上传结果图片（关键帧）到 Supabase Storage

        Args:
            file_path: 本地图片文件路径
            user_id: 用户 ID（可选）
            task_id: 任务 ID
            image_name: 图片名称（如 keyframe_release.png）

        Returns:
            上传成功返回 Storage URL
        """
        if not self.client or not file_path.exists():
            return None

        try:
            # 构建存储路径
            if image_name:
                filename = image_name
            else:
                filename = file_path.name

            if user_id:
                storage_path = f"{user_id}/{task_id}/{filename}"
            else:
                storage_path = f"public/{task_id}/{filename}"

            # 读取文件
            with open(file_path, 'rb') as f:
                file_content = f.read()

            # 上传
            response = self.client.storage.from_(self.BUCKET_RESULTS).upload(
                storage_path,
                file_content,
                file_options={
                    "content-type": "image/jpeg",
                    "upsert": "true"
                }
            )

            if response:
                public_url = self.client.storage.from_(self.BUCKET_RESULTS).get_public_url(storage_path)
                return public_url

        except Exception as e:
            print(f"[Storage] Image upload failed: {e}")

        return None

    def upload_result_image_bytes(
        self,
        image_content: bytes,
        image_name: str,
        user_id: Optional[str] = None,
        task_id: str = ""
    ) -> Optional[str]:
        """
        直接上传图片字节内容

        Args:
            image_content: 图片字节内容
            image_name: 图片名称
            user_id: 用户 ID（可选）
            task_id: 任务 ID

        Returns:
            上传成功返回 Storage URL
        """
        if not self.client:
            return None

        try:
            # 构建存储路径
            if user_id:
                storage_path = f"{user_id}/{task_id}/{image_name}"
            else:
                storage_path = f"public/{task_id}/{image_name}"

            # 上传
            response = self.client.storage.from_(self.BUCKET_RESULTS).upload(
                storage_path,
                image_content,
                file_options={
                    "content-type": "image/jpeg",
                    "upsert": "true"
                }
            )

            if response:
                public_url = self.client.storage.from_(self.BUCKET_RESULTS).get_public_url(storage_path)
                return public_url

        except Exception as e:
            print(f"[Storage] Image bytes upload failed: {e}")

        return None

    def delete_video(self, storage_path: str) -> bool:
        """删除视频文件"""
        if not self.client:
            return False

        try:
            self.client.storage.from_(self.BUCKET_VIDEOS).remove([storage_path])
            return True
        except Exception as e:
            print(f"[Storage] Video delete failed: {e}")
            return False

    def delete_video_by_task(self, task_id: str, filename: str, user_id: Optional[str] = None) -> bool:
        """
        根据任务ID删除视频文件

        Args:
            task_id: 任务ID
            filename: 文件名（如 video.mp4）
            user_id: 用户ID（可选）

        Returns:
            删除成功返回 True
        """
        if not self.client:
            return False

        try:
            # 构建存储路径
            if user_id:
                storage_path = f"{user_id}/{task_id}/{filename}"
            else:
                storage_path = f"public/{task_id}/{filename}"

            self.client.storage.from_(self.BUCKET_VIDEOS).remove([storage_path])
            print(f"[Storage] Deleted video: {storage_path}")
            return True
        except Exception as e:
            print(f"[Storage] Video delete by task failed: {e}")
            return False

    def delete_result_images(self, task_id: str, user_id: Optional[str] = None) -> bool:
        """删除任务的所有结果图片"""
        if not self.client:
            return False

        try:
            # 构建路径前缀
            if user_id:
                prefix = f"{user_id}/{task_id}/"
            else:
                prefix = f"public/{task_id}/"

            # 列出所有文件
            files = self.client.storage.from_(self.BUCKET_RESULTS).list(prefix)

            if files:
                # 删除所有文件
                paths_to_delete = [f"{prefix}{f['name']}" for f in files]
                self.client.storage.from_(self.BUCKET_RESULTS).remove(paths_to_delete)

            return True
        except Exception as e:
            print(f"[Storage] Result images delete failed: {e}")
            return False

    def get_video_url(self, storage_path: str) -> Optional[str]:
        """获取视频公开 URL"""
        if not self.client:
            return None

        try:
            return self.client.storage.from_(self.BUCKET_VIDEOS).get_public_url(storage_path)
        except Exception as e:
            print(f"[Storage] Get video URL failed: {e}")
            return None

    def get_result_url(self, storage_path: str) -> Optional[str]:
        """获取结果图片公开 URL"""
        if not self.client:
            return None

        try:
            return self.client.storage.from_(self.BUCKET_RESULTS).get_public_url(storage_path)
        except Exception as e:
            print(f"[Storage] Get result URL failed: {e}")
            return None


# 单例实例
storage_service = StorageService()