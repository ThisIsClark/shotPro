"""
Upload Routes
视频上传接口
"""

import uuid
import shutil
import aiofiles
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks

from ...config import settings
from ...models.schemas import UploadResponse, TaskStatus, TaskStatusResponse
from ...services.analysis_service import AnalysisService, AnalysisConfig, AnalysisProgress
from ...models.template import TemplateManager

router = APIRouter(prefix="/videos", tags=["videos"])

# 任务状态存储（简单实现，生产环境应使用 Redis）
task_store: dict[str, dict] = {}

# 模板管理器
templates_dir = settings.base_dir / "templates"
template_manager = TemplateManager(templates_dir)


def validate_video_file(file: UploadFile) -> None:
    """验证上传的视频文件"""
    # 检查文件扩展名
    if file.filename:
        ext = Path(file.filename).suffix.lower()
        if ext not in settings.allowed_video_extensions:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件格式: {ext}。支持的格式: {settings.allowed_video_extensions}"
            )
    
    # 检查 content type
    if file.content_type and not file.content_type.startswith("video/"):
        raise HTTPException(
            status_code=400,
            detail=f"文件类型错误: {file.content_type}"
        )


async def save_upload_file(upload_file: UploadFile, destination: Path) -> None:
    """异步保存上传文件"""
    destination.parent.mkdir(parents=True, exist_ok=True)
    
    async with aiofiles.open(destination, 'wb') as f:
        while content := await upload_file.read(1024 * 1024):  # 1MB chunks
            await f.write(content)


def run_analysis(task_id: str, video_path: Path, shooting_hand: str = "right", shooting_style: str = "one_motion", template_id: str = None, generate_video: bool = False):
    """运行分析任务（后台任务）"""
    try:
        # 更新状态
        task_store[task_id]["status"] = TaskStatus.PROCESSING
        task_store[task_id]["message"] = "正在分析..."
        
        # 进度回调
        def progress_callback(progress: AnalysisProgress):
            task_store[task_id]["progress"] = progress.percentage
            task_store[task_id]["message"] = progress.message
        
        # 创建分析服务
        config = AnalysisConfig(
            shooting_hand=shooting_hand,
            shooting_style=shooting_style,
            generate_annotated_video=generate_video
        )
        
        with AnalysisService(config) as service:
            result = service.analyze_video(
                video_path,
                task_id=task_id,
                progress_callback=progress_callback
            )
        
        # 转换结果为字典
        result_dict = result.to_dict()
        
        # 如果指定了模板，添加对比数据
        if template_id:
            print(f"[DEBUG] template_id 存在: {template_id}")
            template = template_manager.get_template(template_id)
            if template:
                print(f"[DEBUG] 找到模板: {template.name}, 关键帧数量: {len(template.key_frames)}")
                print(f"[DEBUG] 用户关键帧数量: {len(result.key_frames)}")
                comparison_data = _generate_comparison(result.key_frames, template.key_frames)
                print(f"[DEBUG] 生成的对比数据数量: {len(comparison_data)}")
                print(f"[DEBUG] comparison_data 详细内容:")
                for i, comp in enumerate(comparison_data):
                    print(f"  [{i}] phase={comp.get('phase')}, has_user_frame={bool(comp.get('user_frame'))}, has_template_frame={bool(comp.get('template_frame'))}")
                result_dict["template_comparison"] = {
                    "template_id": template_id,
                    "template_name": template.name,
                    "comparisons": comparison_data
                }
                print(f"[DEBUG] template_comparison 已添加到 result_dict")
                print(f"[DEBUG] result_dict['template_comparison']['comparisons'] 长度: {len(result_dict['template_comparison']['comparisons'])}")
            else:
                print(f"[DEBUG] 模板未找到: {template_id}")
        
        # 更新结果
        task_store[task_id]["status"] = TaskStatus.COMPLETED
        task_store[task_id]["progress"] = 100
        task_store[task_id]["message"] = "分析完成"
        task_store[task_id]["result"] = result_dict
        
    except Exception as e:
        task_store[task_id]["status"] = TaskStatus.FAILED
        task_store[task_id]["error"] = str(e)
        task_store[task_id]["message"] = f"分析失败: {str(e)}"


def _generate_comparison(user_frames, template_frames):
    """生成关键帧对比数据"""
    comparison = []
    
    print(f"[DEBUG _generate_comparison] 用户关键帧数量: {len(user_frames)}")
    print(f"[DEBUG _generate_comparison] 模板关键帧数量: {len(template_frames)}")
    
    # 创建阶段映射
    template_dict = {tkf.phase: tkf for tkf in template_frames}
    print(f"[DEBUG _generate_comparison] template_dict 键: {list(template_dict.keys())}")
    
    for user_kf in user_frames:
        phase = user_kf.phase.value if hasattr(user_kf.phase, 'value') else user_kf.phase
        print(f"[DEBUG _generate_comparison] 处理用户关键帧: phase={phase}, type={type(phase)}")
        template_kf = template_dict.get(phase)
        print(f"[DEBUG _generate_comparison] 找到模板关键帧: {template_kf is not None}")
        
        comp = {
            "phase": phase,
            "user_frame": {
                "image_url": user_kf.image_path,
                "frame_number": user_kf.frame_number,
                "angles": user_kf.angles.to_dict() if hasattr(user_kf.angles, 'to_dict') else user_kf.angles
            }
        }
        
        if template_kf:
            comp["template_frame"] = {
                "image_url": f"/{template_kf.image_path}" if not template_kf.image_path.startswith('/') else template_kf.image_path,
                "angles": template_kf.angles
            }
            
            # 计算角度差异
            if comp["user_frame"]["angles"] and template_kf.angles:
                angle_diffs = {}
                for key in comp["user_frame"]["angles"]:
                    if key in template_kf.angles:
                        user_angle = comp["user_frame"]["angles"][key]
                        template_angle = template_kf.angles[key]
                        if user_angle is not None and template_angle is not None:
                            angle_diffs[key] = abs(user_angle - template_angle)
                
                comp["angle_differences"] = angle_diffs
        
        comparison.append(comp)
        print(f"[DEBUG _generate_comparison] 添加对比条目: phase={phase}, has_template={template_kf is not None}")
    
    print(f"[DEBUG _generate_comparison] 最终对比数组长度: {len(comparison)}")
    print(f"[DEBUG _generate_comparison] 对比数组内容预览: {[c.get('phase') for c in comparison]}")
    return comparison


@router.post("/upload", response_model=UploadResponse)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    shooting_hand: str = "right",
    shooting_style: str = "one_motion",
    template_id: str = None,
    generate_video: bool = False
):
    """
    上传投篮视频
    
    - **file**: 视频文件 (支持 mp4, mov, avi, webm)
    - **shooting_hand**: 投篮手 ("left" 或 "right")
    - **shooting_style**: 投篮方式 ("one_motion" 或 "two_motion")
    - **template_id**: 可选，对比模板ID
    - **generate_video**: 是否生成标注视频（默认false，提高速度）
    
    返回 task_id，可用于查询分析状态和结果
    """
    # 验证文件
    validate_video_file(file)
    
    # 验证投篮手参数
    if shooting_hand not in ["left", "right"]:
        raise HTTPException(
            status_code=400,
            detail="shooting_hand 必须是 'left' 或 'right'"
        )
    
    # 如果指定了模板，验证模板是否存在
    if template_id:
        template = template_manager.get_template(template_id)
        if not template:
            raise HTTPException(
                status_code=404,
                detail=f"模板不存在: {template_id}"
            )
    
    # 生成任务 ID
    task_id = str(uuid.uuid4())
    
    # 保存文件
    file_ext = Path(file.filename).suffix if file.filename else ".mp4"
    video_path = settings.upload_dir / f"{task_id}{file_ext}"
    
    await save_upload_file(file, video_path)
    
    # 检查文件大小
    file_size_mb = video_path.stat().st_size / (1024 * 1024)
    if file_size_mb > settings.max_video_size_mb:
        video_path.unlink()  # 删除文件
        raise HTTPException(
            status_code=400,
            detail=f"文件过大: {file_size_mb:.1f}MB，最大允许 {settings.max_video_size_mb}MB"
        )
    
    # 初始化任务状态
    task_store[task_id] = {
        "status": TaskStatus.PENDING,
        "progress": 0,
        "message": "任务已创建，等待处理",
        "result": None,
        "error": None,
        "video_path": str(video_path),
        "filename": file.filename,
        "template_id": template_id
    }
    
    # 添加后台任务
    background_tasks.add_task(run_analysis, task_id, video_path, shooting_hand, shooting_style, template_id, generate_video)
    
    return UploadResponse(
        task_id=task_id,
        message="视频上传成功，开始分析",
        filename=file.filename or "unknown"
    )


@router.get("/tasks/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    获取分析任务状态
    
    - **task_id**: 任务ID
    """
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = task_store[task_id]
    
    return TaskStatusResponse(
        task_id=task_id,
        status=task["status"],
        progress=task["progress"],
        message=task["message"],
        result=task["result"],
        error=task["error"]
    )


@router.get("/tasks/{task_id}/result")
async def get_task_result(task_id: str):
    """
    获取分析结果
    
    - **task_id**: 任务ID
    """
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = task_store[task_id]
    
    if task["status"] == TaskStatus.PENDING:
        raise HTTPException(status_code=202, detail="任务等待处理中")
    
    if task["status"] == TaskStatus.PROCESSING:
        raise HTTPException(
            status_code=202, 
            detail=f"任务处理中: {task['progress']}%"
        )
    
    if task["status"] == TaskStatus.FAILED:
        raise HTTPException(
            status_code=500,
            detail=f"分析失败: {task['error']}"
        )
    
    return task["result"]


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    """
    删除任务及相关文件
    
    - **task_id**: 任务ID
    """
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    task = task_store[task_id]
    
    # 删除上传的视频
    video_path = Path(task.get("video_path", ""))
    if video_path.exists():
        video_path.unlink()
    
    # 删除结果目录
    result_dir = settings.results_dir / task_id
    if result_dir.exists():
        shutil.rmtree(result_dir)
    
    # 从存储中删除
    del task_store[task_id]
    
    return {"message": "任务已删除", "task_id": task_id}
