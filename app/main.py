"""
FastAPI Application Entry Point
应用程序入口
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from .config import settings
from .api.routes import upload, health, export, templates

# 创建 FastAPI 应用
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="投篮姿势分析系统 - 上传投篮视频，获取姿势分析和改进建议",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")
app.mount("/results", StaticFiles(directory=str(settings.results_dir)), name="results")
# 挂载模板图片目录（使用不同的路径避免与API冲突）
template_images_dir = settings.base_dir / "templates"
template_images_dir.mkdir(parents=True, exist_ok=True)
app.mount("/template_images", StaticFiles(directory=str(template_images_dir)), name="template_images")

# 注册路由
app.include_router(health.router)
app.include_router(upload.router, prefix="/api/v1")
app.include_router(export.router, prefix="/api/v1")
app.include_router(templates.router)


# 前端页面
@app.get("/app", response_class=HTMLResponse)
async def serve_app():
    """提供前端页面"""
    html_path = settings.templates_dir / "index.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return HTMLResponse(content="<h1>Frontend not found</h1>", status_code=404)


@app.get("/video-test", response_class=HTMLResponse)
async def serve_video_test():
    """视频播放测试页面"""
    html_path = settings.templates_dir / "video_test.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return HTMLResponse(content="<h1>Video test page not found</h1>", status_code=404)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
