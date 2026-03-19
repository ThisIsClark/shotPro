"""
FastAPI Application Entry Point
应用程序入口
"""

import shutil
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from .config import settings
from .api.routes import upload, health, export, templates

# 最大保留任务数量
MAX_TASKS = 10


def cleanup_disk_tasks():
    """
    启动时清理磁盘上的旧任务目录
    只保留最近的 MAX_TASK 个任务
    """
    results_dir = settings.results_dir
    upload_dir = settings.upload_dir

    if not results_dir.exists():
        return

    # 获取所有任务目录及其修改时间
    task_dirs = []
    for task_dir in results_dir.iterdir():
        if task_dir.is_dir():
            # 尝试从 result.json 读取创建时间
            result_file = task_dir / "result.json"
            if result_file.exists():
                try:
                    import json
                    with open(result_file, 'r') as f:
                        data = json.load(f)
                        created_at = data.get("created_at", "")
                except:
                    created_at = ""
            else:
                created_at = ""

            # 如果没有创建时间，使用目录修改时间
            if not created_at:
                created_at = datetime.fromtimestamp(task_dir.stat().st_mtime).isoformat()

            task_dirs.append((task_dir.name, created_at))

    # 按创建时间排序（最新的在前）
    task_dirs.sort(key=lambda x: x[1], reverse=True)

    # 清理超过 MAX_TASKS 的任务
    if len(task_dirs) > MAX_TASKS:
        tasks_to_delete = task_dirs[MAX_TASKS:]
        print(f"[STARTUP] 发现 {len(task_dirs)} 个任务，清理 {len(tasks_to_delete)} 个旧任务")

        for task_id, _ in tasks_to_delete:
            try:
                # 删除结果目录
                result_dir = results_dir / task_id
                if result_dir.exists():
                    shutil.rmtree(result_dir)
                    print(f"[STARTUP] 删除结果目录: {result_dir}")

                # 删除上传的视频文件
                for ext in ['.mp4', '.mov', '.avi', '.webm']:
                    video_file = upload_dir / f"{task_id}{ext}"
                    if video_file.exists():
                        video_file.unlink()
                        print(f"[STARTUP] 删除视频文件: {video_file}")
                        break

            except Exception as e:
                print(f"[STARTUP] 清理任务 {task_id} 失败: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    print("[STARTUP] 投篮姿势分析系统启动中...")
    cleanup_disk_tasks()
    yield
    # 关闭时执行
    print("[SHUTDOWN] 投篮姿势分析系统关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="投篮姿势分析系统 - 上传投篮视频，获取姿势分析和改进建议",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
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
