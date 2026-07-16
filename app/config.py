"""Application configuration"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # App info
    app_name: str = "Basketball Shooting Form Analyzer"
    app_version: str = "0.1.0"
    debug: bool = True
    app_url: str = ""  # Public URL for payment callbacks (e.g., https://your-domain.com)
    
    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    upload_dir: Path = base_dir / "uploads"
    results_dir: Path = base_dir / "results"
    static_dir: Path = base_dir / "static"
    templates_dir: Path = base_dir / "templates"
    
    # Upload limits
    max_video_size_mb: int = 20
    max_video_duration_seconds: int = 10
    allowed_video_extensions: set = {".mp4", ".mov", ".avi", ".webm"}
    
    # Analysis settings
    target_fps: int = 30  # Target FPS for analysis
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5

    # Supabase Configuration
    supabase_url: str = ""  # e.g., "https://xxxxx.supabase.co"
    supabase_anon_key: str = ""  # Public key for frontend
    supabase_service_key: str = ""  # Service role key for backend (higher privileges)

    # Model Configuration
    # If empty, uses the fixed-version default URL in pose_detector.py (0_2024-03-19, NOT latest)
    # To override, set this to a specific model URL. Do NOT use "latest" tag URLs.
    pose_model_url: str = ""  # e.g., "https://your-supabase.supabase.co/storage/v1/object/public/models/pose_landmarker.task"

    # Admin Configuration
    local_admin_password: str = "myjob123"  # 管理员密码，生产环境务必通过环境变量设置强密码
    jwt_secret: str = "change-me-in-production"  # JWT 签名密钥，生产环境务必通过环境变量设置

    # CORS
    allowed_origins: str = ""  # 逗号分隔的允许域名，为空则允许所有（仅开发模式）

    # Creem Payment Configuration
    creem_api_key: str = ""           # creem_test_xxx or creem_xxx (live)
    creem_webhook_secret: str = ""    # Webhook signing secret from Creem dashboard

    # One-time product (legacy, kept for compatibility)
    creem_product_id: str = ""        # Product ID for single analysis ($1.49/credit)

    # Subscription products
    creem_monthly_product_id: str = ""  # Product ID for Early Adopter Monthly ($4.99/month)
    creem_yearly_product_id: str = ""   # Product ID for Early Adopter Yearly ($39.99/year)

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# Ensure directories exist
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.results_dir.mkdir(parents=True, exist_ok=True)
settings.static_dir.mkdir(parents=True, exist_ok=True)
settings.templates_dir.mkdir(parents=True, exist_ok=True)
