"""
Local Authentication Service Module
本地用户认证服务：管理员账号管理、密码加密验证
"""

import json
import bcrypt
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from ..config import settings


class LocalAuthService:
    """本地用户认证服务"""

    USERS_FILE = settings.base_dir / "data" / "users.json"

    def __init__(self):
        self._ensure_data_dir()

    def _ensure_data_dir(self):
        """确保数据目录存在"""
        data_dir = settings.base_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

    def _load_users(self) -> Dict[str, Any]:
        """加载用户数据"""
        if not self.USERS_FILE.exists():
            return {}
        try:
            with open(self.USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[LocalAuth] Failed to load users: {e}")
            return {}

    def _save_users(self, users: Dict[str, Any]) -> bool:
        """保存用户数据"""
        try:
            with open(self.USERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(users, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"[LocalAuth] Failed to save users: {e}")
            return False

    def _hash_password(self, password: str) -> str:
        """使用 bcrypt 加密密码"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    def _verify_password(self, password: str, hashed_password: str) -> bool:
        """验证密码"""
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                hashed_password.encode('utf-8')
            )
        except Exception:
            return False

    def create_user(
        self,
        username: str,
        password: str,
        role: str = "user",
        email: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        创建用户

        Args:
            username: 用户名
            password: 明文密码（会被加密）
            role: 用户角色（admin/user）
            email: 可选邮箱

        Returns:
            创建的用户信息（不含密码），失败返回 None
        """
        users = self._load_users()

        # 检查用户是否已存在
        if username in users:
            print(f"[LocalAuth] User '{username}' already exists")
            return None

        # 加密密码
        hashed_password = self._hash_password(password)

        # 创建用户记录
        user_data = {
            "username": username,
            "password_hash": hashed_password,  # 密文存储
            "role": role,
            "email": email or f"{username}@local",
            "created_at": datetime.utcnow().isoformat(),
            "is_local": True  # 标记为本地用户
        }

        users[username] = user_data

        if self._save_users(users):
            print(f"[LocalAuth] User '{username}' created successfully")
            # 返回不含密码的用户信息
            return {
                "username": username,
                "role": role,
                "email": user_data["email"],
                "created_at": user_data["created_at"],
                "is_local": True
            }
        return None

    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        验证用户登录

        Args:
            username: 用户名
            password: 明文密码

        Returns:
            用户信息（不含密码），验证失败返回 None
        """
        users = self._load_users()

        if username not in users:
            return None

        user = users[username]

        # 验证密码
        if not self._verify_password(password, user.get("password_hash", "")):
            return None

        # 返回不含密码的用户信息
        return {
            "username": username,
            "role": user.get("role", "user"),
            "email": user.get("email", ""),
            "is_local": True
        }

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        """获取用户信息（不含密码）"""
        users = self._load_users()

        if username not in users:
            return None

        user = users[username]
        return {
            "username": username,
            "role": user.get("role", "user"),
            "email": user.get("email", ""),
            "is_local": True
        }

    def user_exists(self, username: str) -> bool:
        """检查用户是否存在"""
        users = self._load_users()
        return username in users

    def init_admin_user(self, username: str = "admin", password: str = "myjob123") -> bool:
        """
        初始化管理员账号

        如果管理员账号不存在，则创建

        Args:
            username: 管理员用户名
            password: 管理员密码

        Returns:
            是否成功初始化
        """
        if self.user_exists(username):
            print(f"[LocalAuth] Admin user '{username}' already exists")
            return True

        result = self.create_user(
            username=username,
            password=password,
            role="admin",
            email="admin@local"
        )

        if result:
            print(f"[LocalAuth] Admin user '{username}' initialized successfully")
            return True
        return False


# 单例实例
local_auth_service = LocalAuthService()