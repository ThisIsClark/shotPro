"""Application configuration"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # App info
    app_name: str = "Basketball Shooting Form Analyzer"
    app_version: str = "0.1.0"
    debug: bool = True
    
    # Paths
    base_dir: Path = Path(__file__).resolve().parent.parent
    upload_dir: Path = base_dir / "uploads"
    results_dir: Path = base_dir / "results"
    static_dir: Path = base_dir / "static"
    templates_dir: Path = base_dir / "templates"
    
    # Upload limits
    max_video_size_mb: int = 50
    max_video_duration_seconds: int = 10
    allowed_video_extensions: set = {".mp4", ".mov", ".avi", ".webm"}
    
    # Analysis settings
    target_fps: int = 30  # Target FPS for analysis
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    
    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# Ensure directories exist
settings.upload_dir.mkdir(parents=True, exist_ok=True)
settings.results_dir.mkdir(parents=True, exist_ok=True)
settings.static_dir.mkdir(parents=True, exist_ok=True)
settings.templates_dir.mkdir(parents=True, exist_ok=True)
