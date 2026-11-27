"""
FastAPI Application Entry Point
应用程序入口
"""

import mimetypes
import re
from urllib.parse import urlencode
import shutil
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse

from .config import settings
from .api.routes import upload, health, export, templates
from .api.routes import auth, users, admin, payment
from .api.routes import audit, feedback, seo
from .services.seo_service import metadata, HOME_TITLE, HOME_DESCRIPTION, PUBLIC_PATHS, indexable_host
from .services.admin_session import SESSION_PATH, read_session
from .services.feedback_service import feedback_store
from .services.local_auth_service import local_auth_service
from .services.db_init_service import init_database

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
            if trial_store.get(task_dir.name):
                continue
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
    print("[STARTUP] Basketball Shooting Form Analyzer starting...")
    feedback_store.recover()
    trial_store.maintenance()
    cleanup_disk_tasks()

    # 初始化管理员账号
    print("[STARTUP] Initializing admin account...")
    local_auth_service.init_admin_user(username="admin", password=settings.local_admin_password)

    # 初始化数据库表（检查是否存在）
    print("[STARTUP] Checking database tables...")
    await init_database()

    yield
    # 关闭时执行
    print("[SHUTDOWN] Basketball Shooting Form Analyzer stopped")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="投篮姿势分析系统 - 上传投篮视频，获取姿势分析和改进建议",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

@app.middleware("http")
async def search_indexing_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    public_asset = path.startswith("/static/")
    indexable_path = path in PUBLIC_PATHS or path in ("/robots.txt", "/sitemap.xml")
    if (settings.engine_session_origin == settings.seo_site_url and settings.seo_indexable
            and indexable_path and 200 <= response.status_code < 300):
        response.headers["X-FormRefine-Indexable"] = "1"
    if (not indexable_host(request.url.hostname) or response.status_code >= 400
            or (path not in PUBLIC_PATHS and path not in ("/", "/robots.txt", "/sitemap.xml") and not public_asset)):
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


# CORS 配置
_corigins = settings.allowed_origins.split(",") if settings.allowed_origins else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_corigins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public workspace paths carried by the existing staging Worker route.
STAGING_WORKSPACE = "/api/v1/videos/workspace"
STAGING_PUBLIC_PAGES = {"/app", "/privacy", "/guides"}
STAGING_PUBLIC_PREFIXES = ("/static/", "/guides/", "/api/v1/templates/", "/template_images/")


def staging_workspace_html(html):
    return re.sub(
        r"""(?<=["'`])/(?:app(?=[#?"'`])|privacy(?=["'`])|guides(?=[/#?"'`])|static/|api/v1/templates/|template_images/)""",
        lambda match: STAGING_WORKSPACE + match[0],
        html,
    )


# Private reports use the same ownership checks for API exports and static media.
from .api.routes import trial
from .services.trial_service import trial_store
app.include_router(trial.router, prefix="/api/v1")

@app.middleware("http")
async def protect_report_media(request: Request, call_next):
    import hmac
    import time
    from fastapi import HTTPException
    from fastapi.responses import JSONResponse
    from fastapi.security import HTTPAuthorizationCredentials
    from .api.deps import get_current_user_optional
    path = request.url.path
    workspace = settings.staging_engine_auth and (
        path == STAGING_WORKSPACE or path.startswith(STAGING_WORKSPACE + "/")
    )
    if workspace:
        path = path.removeprefix(STAGING_WORKSPACE) or "/app"
        if request.method not in {"GET", "HEAD"} or (
            path not in STAGING_PUBLIC_PAGES and not path.startswith(STAGING_PUBLIC_PREFIXES)
        ):
            return JSONResponse({"detail": "Unknown workspace route."}, status_code=404)
        request.scope["path"] = path
    public_read = request.method in {"GET", "HEAD"} and (
        path in {"/", "/app", "/privacy", "/guides", "/robots.txt", "/sitemap.xml", "/health"} or
        path.startswith(("/static/", "/guides/", "/api/v1/templates/")) or
        (path.startswith("/template_images/") and Path(path).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})
    )
    admin_page = path == "/admin" and request.method in {"GET", "HEAD"}
    admin_api = path.startswith("/api/v1/admin/")
    if settings.password_admin_enabled and (admin_page or admin_api):
        private_headers = {"Cache-Control": "private, no-store", "X-Robots-Tag": "noindex, nofollow"}
        if request.method not in {"GET", "HEAD"} and request.headers.get("origin") != settings.engine_session_origin:
            return JSONResponse({"detail": "Request must originate from FormRefine."}, status_code=403,
                                headers=private_headers)
        if admin_api and not (path == SESSION_PATH and request.method in {"POST", "DELETE"}):
            user = read_session(request)
            if not user:
                return JSONResponse({"detail": "Administrator login required."}, status_code=401,
                                    headers=private_headers)
            request.state.engine_admin = user
        response = await call_next(request)
        response.headers.update(private_headers)
        return response
    if settings.engine_session_origin and settings.engine_admin_member_id and (admin_page or admin_api):
        from .services.engine_identity import verify_engine_member
        private_headers = {"Cache-Control": "private, no-store", "X-Robots-Tag": "noindex, nofollow"}
        try:
            member = await verify_engine_member(request)
        except HTTPException as exc:
            if admin_page and exc.status_code == 401:
                query = urlencode({"next": "/admin"})
                return RedirectResponse(f"{settings.engine_session_origin}/_auth/google/start?{query}",
                                        status_code=303, headers=private_headers)
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code,
                                headers=private_headers)
        if member["subject"] != settings.engine_admin_member_id:
            return JSONResponse({"detail": "Admin access required"}, status_code=403,
                                headers=private_headers)
        request.state.engine_admin = {**member, "role": "admin"}
        response = await call_next(request)
        response.headers.update(private_headers)
        return response
    if path in {audit.ENGINE_VISIT_PATH, audit.ENGINE_JOURNEY_PATH}:
        if not settings.engine_session_origin:
            return JSONResponse({"detail": "Route not found."}, status_code=404)
        if request.method != "POST" or request.headers.get("origin") != settings.engine_session_origin:
            return JSONResponse({"detail": "Request must originate from FormRefine."}, status_code=403)
        if path == audit.ENGINE_JOURNEY_PATH:
            from .services.engine_identity import verify_engine_member
            try:
                request.state.engine_member = await verify_engine_member(request)
            except HTTPException as exc:
                return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        return await call_next(request)
    if settings.engine_session_origin and not public_read:
        from .services.engine_identity import verify_engine_member
        if not path.startswith(("/api/v1/videos/", "/results/", "/api/v1/export/")):
            return JSONResponse({"detail": "Route not found."}, status_code=404)
        try:
            request.state.engine_member = await verify_engine_member(request)
        except HTTPException as exc:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code,
                                headers={"Cache-Control": "no-store"})
    if path.startswith('/results/') or path.startswith('/api/v1/export/'):
        parts = path.split('/')
        task_id = parts[2] if path.startswith('/results/') else parts[4]
        # Preserve public legacy demonstration assets; all newly created reports are private.
        if settings.engine_session_origin or trial_store.get(task_id) or path.startswith('/api/v1/export/'):
            user = getattr(request.state, "engine_member", None)
            auth = request.headers.get('authorization', '')
            if not user and auth.startswith('Bearer '):
                user = await get_current_user_optional(request, HTTPAuthorizationCredentials(scheme='Bearer', credentials=auth[7:]))
            token = request.cookies.get('shot_media', '').rsplit(':', 2)
            if not user and len(token) == 3:
                value = ':'.join(token[:2])
                try:
                    if int(token[1]) > time.time() and hmac.compare_digest(token[2], trial_store.sign(value)):
                        user = {'id': token[0]}
                except ValueError:
                    pass
            try:
                await upload.authorize_report(task_id, request, user)
            except HTTPException as exc:
                return JSONResponse({'detail': exc.detail}, status_code=exc.status_code)
            response = await call_next(request)
            response.headers['Cache-Control'] = 'private, no-store'
            return response
    response = await call_next(request)
    if workspace and response.headers.get("content-type", "").startswith("text/html"):
        body = b"".join([chunk async for chunk in response.body_iterator])
        del response.headers["content-length"]
        return HTMLResponse(staging_workspace_html(body.decode("utf-8")),
                            status_code=response.status_code, headers=response.headers)
    return response

# 挂载静态文件
mimetypes.add_type("image/webp", ".webp")
app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")
app.mount("/results", StaticFiles(directory=str(settings.results_dir)), name="results")
# 挂载模板图片目录（使用不同的路径避免与API冲突）
template_images_dir = settings.base_dir / "templates"
template_images_dir.mkdir(parents=True, exist_ok=True)
app.mount("/template_images", StaticFiles(directory=str(template_images_dir)), name="template_images")

# 注册路由
app.include_router(seo.router)
app.include_router(feedback.router, prefix="/api/v1")
app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1")  # 认证路由
app.include_router(users.router, prefix="/api/v1")  # 用户管理路由
app.include_router(upload.router, prefix="/api/v1")
app.include_router(export.router, prefix="/api/v1")
app.include_router(templates.router)
app.include_router(admin.router, prefix="/api/v1")  # 管理员路由
app.include_router(payment.router, prefix="/api/v1")  # 付款路由
app.include_router(audit.router, prefix="/api/v1")  # 用户行为追踪路由
app.add_api_route(audit.ENGINE_VISIT_PATH, audit.record_visit, methods=["POST"], include_in_schema=False)
app.add_api_route(audit.ENGINE_JOURNEY_PATH, audit.journey_event, methods=["POST"], include_in_schema=False)
# Webhook 兼容路由：Creem 后台默认调 /api/payment/webhook，需要同时支持 /api/v1/payment/webhook
app.include_router(payment.router, prefix="/api")  # 付款路由兼容（webhook 用）


# 前端页面
@app.get("/app", response_class=HTMLResponse)
async def serve_app():
    """提供前端页面，注入环境配置"""
    html_path = settings.templates_dir / "index.html"
    if html_path.exists():
        html = html_path.read_text(encoding="utf-8")
        # 将后端环境变量注入到前端，替换占位符
        if settings.engine_session_origin:
            html = html.replace('<body>', '<body data-engine-auth>')
            html = html.replace('1 free analysis without signup &nbsp; · &nbsp; 3 more with a free account',
                                'Sign in with Google to save your video and compare your practice sessions.')
            html = html.replace('Try one analysis without signing up. Videos up to 10 seconds; trial reports available for 24 hours.',
                                'Upload a clip up to 10 seconds. Your video and report are saved in History.')
            for asset in ("/static/quality-survey.js",
                          "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"):
                html = html.replace(f'<script src="{asset}"></script>', '')
        html = html.replace("{{SUPABASE_URL}}", settings.supabase_url or "")
        html = html.replace("{{SUPABASE_ANON_KEY}}", settings.supabase_anon_key or "")
        html = html.replace("{{SEO_METADATA}}", metadata("/app", HOME_TITLE, HOME_DESCRIPTION))
        for asset in ("feedback.js", "feedback.css", "one-page.css"):
            stamp = (settings.static_dir / asset).stat().st_mtime_ns
            html = html.replace(f"/static/{asset}", f"/static/{asset}?v={stamp}")
        return html
    return HTMLResponse(content="<h1>Frontend not found</h1>", status_code=404)


@app.get("/privacy", response_class=HTMLResponse)
async def privacy_policy():
    html = (settings.templates_dir / "privacy.html").read_text(encoding="utf-8")
    if settings.engine_session_origin:
        html = html.replace(
            "The analyzer removes the source upload after processing. Saved reports and their images remain "
            "available in your analysis history until deleted. Guest reports expire unless saved to an account.",
            "Your original video and report are saved to your account after successful analysis. "
            "You can remove them from Analysis History.")
        html = html.replace("<h2>Site operation and subscriptions</h2>", "<h2>Site operation</h2>")
        html = html.replace("enforce free-trial limits and control access to reports",
                            "and control access to reports").replace("maintain sessions, and", "maintain sessions and")
        html = html.replace(" If you subscribe, Creem handles checkout. We use transaction references and subscription "
                            "status to manage access. We do not store your full payment card number.", "")
        html = html.replace("We use Supabase for account and data services on the existing analyzer. ", "")
        html = html.replace(" Creem processes payments when you use checkout.", "")
    return html.replace("{{SEO_METADATA}}", metadata(
        "/privacy", "FormRefine Privacy Policy",
        ("How FormRefine handles shooting videos, saved reports, Google sign-in and privacy requests."
         if settings.engine_session_origin else
         "How FormRefine handles shooting videos, saved reports, Google sign-in, payments and privacy requests."),
    ))


@app.get("/video-test", response_class=HTMLResponse)
async def serve_video_test():
    """视频播放测试页面"""
    html_path = settings.templates_dir / "video_test.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return HTMLResponse(content="<h1>Video test page not found</h1>", status_code=404)


@app.get("/admin", response_class=HTMLResponse)
async def serve_admin():
    """管理后台页面"""
    html_path = settings.templates_dir / "admin.html"
    if html_path.exists():
        html = html_path.read_text(encoding="utf-8")
        if settings.password_admin_enabled:
            html = html.replace("<body>", "<body data-engine-password-admin>")
        elif settings.engine_session_origin:
            html = html.replace("<body>", "<body data-engine-admin>")
        return HTMLResponse(html, headers={"Cache-Control": "private, no-store"})
    return HTMLResponse(content="<h1>Admin page not found</h1>", status_code=404)


@app.get("/feedback-share", response_class=HTMLResponse)
async def serve_feedback_share():
    return HTMLResponse((settings.templates_dir / "feedback_share.html").read_text(), headers={
        "Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "X-Robots-Tag": "noindex"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug
    )
