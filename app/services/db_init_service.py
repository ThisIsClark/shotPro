"""
Database Initialization Service
数据库初始化服务：启动时自动创建必要的表
"""

from pathlib import Path
from .supabase_client import get_supabase_client, is_supabase_enabled


class DatabaseInitializer:
    """数据库初始化器"""

    def __init__(self):
        self.client = get_supabase_client()
        self.sql_dir = Path(__file__).parent.parent.parent / "supabase"

    def is_available(self) -> bool:
        """检查是否可用"""
        return self.client is not None

    def run_sql_file(self, sql_file: Path) -> bool:
        """
        执行 SQL 文件

        Args:
            sql_file: SQL 文件路径

        Returns:
            是否成功
        """
        if not self.client or not sql_file.exists():
            return False

        try:
            sql_content = sql_file.read_text(encoding="utf-8")

            # 使用 Supabase 的 rpc 谄域能执行 SQL
            # 但由于权限问题，我们使用另一种方式：
            # 尝试检查表是否存在，如果不存在则通过 API 创建

            # 注意：Supabase Python SDK 不直接支持执行 raw SQL
            # 需要通过 Supabase Dashboard 或使用 service_role 的 REST API
            # 这里我们使用一个替代方案：检查表并尝试操作来判断

            print(f"[DB Init] SQL file loaded: {sql_file.name}")
            print(f"[DB Init] Note: Please execute this SQL in Supabase Dashboard if tables don't exist")

            return True
        except Exception as e:
            print(f"[DB Init] Failed to load SQL file: {e}")
            return False

    def check_and_init_tables(self) -> dict:
        """
        检查并初始化必要的表

        Returns:
            各表的初始化状态
        """
        if not self.client:
            print("[DB Init] Supabase not configured, skipping table init")
            return {"available": False}

        results = {
            "available": True,
            "analyses": self._check_table("analyses"),
            "audit_logs": self._check_table("audit_logs"),
            "user_templates": self._check_table("user_templates"),
            "user_credits": self._check_table("user_credits"),
            "payment_checkouts": self._check_table("payment_checkouts")
        }

        # 如果 audit_logs 表不存在，提示用户手动创建
        if not results["audit_logs"]:
            print("[DB Init] ⚠️  audit_logs table not found!")
            print("[DB Init] Please run the SQL in supabase/audit_logs.sql via Supabase Dashboard")

        # 如果 user_credits 表不存在，提示用户手动创建
        if not results["user_credits"]:
            print("[DB Init] ⚠️  user_credits table not found!")
            print("[DB Init] Please run the following SQL in Supabase Dashboard:")
            print("[DB Init]   CREATE TABLE user_credits (user_id UUID PRIMARY KEY REFERENCES auth.users(id), credits_remaining INT NOT NULL DEFAULT 2, total_granted INT NOT NULL DEFAULT 2, created_at TIMESTAMPTZ DEFAULT NOW(), updated_at TIMESTAMPTZ DEFAULT NOW())")

        # 如果 payment_checkouts 表不存在，提示用户手动创建
        if not results["payment_checkouts"]:
            print("[DB Init] ⚠️  payment_checkouts table not found!")
            print("[DB Init] Please run the following SQL in Supabase Dashboard:")
            print("[DB Init]   CREATE TABLE payment_checkouts (checkout_id TEXT PRIMARY KEY, user_id TEXT NOT NULL, processed_at TIMESTAMPTZ DEFAULT NOW())")

        return results

    def _check_table(self, table_name: str) -> bool:
        """
        检查表是否存在

        Args:
            table_name: 表名

        Returns:
            表是否存在
        """
        if not self.client:
            return False

        try:
            # 尝试查询表的一行数据来检查表是否存在
            response = self.client.table(table_name).select("*").limit(1).execute()
            print(f"[DB Init] ✓ Table '{table_name}' exists")
            return True
        except Exception as e:
            error_msg = str(e)
            # 如果错误包含 "does not exist" 或类似信息，说明表不存在
            if "does not exist" in error_msg or "relation" in error_msg.lower():
                print(f"[DB Init] ✗ Table '{table_name}' does not exist")
                return False
            # 其他错误（如权限问题）也可能意味着表不存在
            print(f"[DB Init] ? Table '{table_name}' check failed: {e}")
            return False

    def init_audit_logs_table(self) -> bool:
        """
        尝试初始化 audit_logs 表

        注意：由于 Supabase Python SDK 的限制，无法直接执行 DDL SQL
        这个方法会检查表是否存在，并提示用户手动创建

        Returns:
            是否成功（表已存在或创建成功）
        """
        if self._check_table("audit_logs"):
            return True

        # 无法自动创建，返回 False 并提示用户
        print("[DB Init] Cannot auto-create audit_logs table via SDK")
        print("[DB Init] Please execute supabase/audit_logs.sql in Supabase Dashboard")
        return False


# 单例实例
db_initializer = DatabaseInitializer()


async def init_database():
    """
    异步初始化数据库（在应用启动时调用）
    """
    if not is_supabase_enabled():
        print("[DB Init] Supabase not enabled, skipping initialization")
        return

    results = db_initializer.check_and_init_tables()

    if not results.get("audit_logs"):
        print("\n" + "=" * 60)
        print("⚠️  AUDIT LOGS TABLE NOT FOUND")
        print("=" * 60)
        print("To enable audit logging, please:")
        print("1. Go to Supabase Dashboard > SQL Editor")
        print("2. Execute the SQL from: supabase/audit_logs.sql")
        print("=" * 60 + "\n")