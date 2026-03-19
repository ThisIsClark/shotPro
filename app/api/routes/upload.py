"""
Upload Routes
视频上传接口
"""

import uuid
import shutil
import aiofiles
from pathlib import Path
from datetime import datetime
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks

from ...config import settings
from ...models.schemas import UploadResponse, TaskStatus, TaskStatusResponse
from ...services.analysis_service import AnalysisService, AnalysisConfig, AnalysisProgress
from ...models.template import TemplateManager

router = APIRouter(prefix="/videos", tags=["videos"])

# 任务状态存储（简单实现，生产环境应使用 Redis）
task_store: dict[str, dict] = {}

# 最大保留任务数量
MAX_TASKS = 10

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


def cleanup_old_tasks(keep_count: int = MAX_TASKS) -> List[str]:
    """
    清理旧任务，只保留最近的任务

    Args:
        keep_count: 保留的任务数量，默认为 MAX_TASKS

    Returns:
        被删除的任务ID列表
    """
    if len(task_store) <= keep_count:
        return []

    # 按创建时间排序任务
    sorted_tasks = sorted(
        task_store.items(),
        key=lambda x: x[1].get("created_at", ""),
        reverse=True  # 最新的在前
    )

    # 需要删除的任务（超过 keep_count 的）
    tasks_to_delete = sorted_tasks[keep_count:]
    deleted_ids = []

    for task_id, task in tasks_to_delete:
        try:
            # 删除上传的视频
            video_path = Path(task.get("video_path", ""))
            if video_path.exists():
                video_path.unlink()
                print(f"[CLEANUP] 删除视频文件: {video_path}")

            # 删除结果目录
            result_dir = settings.results_dir / task_id
            if result_dir.exists():
                shutil.rmtree(result_dir)
                print(f"[CLEANUP] 删除结果目录: {result_dir}")

            # 从内存存储中删除
            del task_store[task_id]
            deleted_ids.append(task_id)
            print(f"[CLEANUP] 清理旧任务: {task_id}")

        except Exception as e:
            print(f"[CLEANUP] 清理任务 {task_id} 失败: {e}")

    return deleted_ids


def run_analysis(task_id: str, video_path: Path, shooting_hand: str = "right", shooting_style: str = "one_motion", template_id: str = None, generate_video: bool = False, generate_skeleton_video: bool = False):
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
            generate_annotated_video=generate_video,
            generate_skeleton_video=generate_skeleton_video
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

                # 生成基于模板的改进建议
                template_suggestions = _generate_template_based_suggestions(comparison_data)

                # 合并建议到现有的 issues
                if template_suggestions:
                    if 'issues' in result_dict:
                        existing_issues = result_dict['issues']
                        new_issues = existing_issues + template_suggestions
                        # 去重但保持顺序（基于 suggestion 字段）
                        seen = set()
                        result_dict['issues'] = [x for x in new_issues if not (x.get('suggestion', '') in seen or seen.add(x.get('suggestion', '')))]
                    else:
                        # 如果原来没有问题，直接添加模板建议
                        result_dict['issues'] = template_suggestions

                print(f"[DEBUG] 生成的模板建议数量：{len(template_suggestions)}")
            else:
                print(f"[DEBUG] 模板未找到: {template_id}")
        
        # 更新结果
        task_store[task_id]["status"] = TaskStatus.COMPLETED
        task_store[task_id]["progress"] = 100
        task_store[task_id]["message"] = "分析完成"
        task_store[task_id]["result"] = result_dict
        
        # 持久化结果到磁盘
        result_dir = settings.results_dir / task_id
        result_file = result_dir / "result.json"
        with open(result_file, 'w', encoding='utf-8') as f:
            import json
            json.dump(result_dict, f, ensure_ascii=False, indent=2)
        print(f"[DEBUG] 结果已保存到: {result_file}")
        print(f"[DEBUG] 结果包含 template_comparison: {'template_comparison' in result_dict}")
        if 'template_comparison' in result_dict:
            print(f"[DEBUG] template_comparison.comparisons 数量: {len(result_dict['template_comparison']['comparisons'])}")
        
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
            # 修复模板图片路径，确保使用 /template_images 前缀
            image_path = template_kf.image_path
            
            # 移除 'templates/' 前缀
            if image_path.startswith('templates/'):
                image_path = image_path.replace('templates/', '', 1)
            
            # 确保路径以 /template_images 开头
            if not image_path.startswith('/template_images'):
                if image_path.startswith('/'):
                    image_path = image_path[1:]
                image_path = '/template_images/' + image_path
                
            comp["template_frame"] = {
                "image_url": image_path,
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



def _generate_template_based_suggestions(comparison_data):
    """
    基于模板对比数据生成改进建议

    优化策略：
    1. 按投篮动作的关键问题聚合（而非按角度）
    2. 每个阶段只输出 1-2 个最关键的改进点
    3. 用更自然的投篮教学语言，避免过度数据化
    """
    suggestions = []

    SIGNIFICANT_DIFF_THRESHOLD = 12  # 显著差异阈值（度）- 提高阈值减少琐碎建议
    CRITICAL_DIFF_THRESHOLD = 20     # 关键差异阈值（度）- 超过此值的问题优先输出

    # 阶段名称映射
    phase_names_zh = {
        'preparation': '准备阶段',
        'lifting': '上升阶段',
        'release': '出手阶段',
        'follow_through': '跟随阶段'
    }
    phase_names_en = {
        'preparation': 'Preparation',
        'lifting': 'Lifting',
        'release': 'Release',
        'follow_through': 'Follow Through'
    }

    # 按阶段收集所有显著差异
    phase_issues = {}  # {phase: [(angle_key, diff, is_less, priority), ...]}

    for comp in comparison_data:
        if 'angle_differences' not in comp or 'user_frame' not in comp or 'template_frame' not in comp:
            continue

        phase = comp['phase']
        if phase not in phase_issues:
            phase_issues[phase] = []

        user_angles = comp['user_frame'].get('angles', {})
        template_angles = comp['template_frame'].get('angles', {})

        for angle_key, diff in comp['angle_differences'].items():
            if diff < SIGNIFICANT_DIFF_THRESHOLD:
                continue

            user_angle = user_angles.get(angle_key)
            template_angle = template_angles.get(angle_key)

            if user_angle is None or template_angle is None:
                continue

            is_less = user_angle < template_angle
            # 根据差异大小设置优先级
            priority = 2 if diff >= CRITICAL_DIFF_THRESHOLD else 1
            phase_issues[phase].append((angle_key, diff, is_less, priority))

    # 为每个阶段生成最多 2 条建议，按优先级排序
    for phase, issues in phase_issues.items():
        if not issues:
            continue

        # 按优先级和差异大小排序
        issues.sort(key=lambda x: (-x[3], -x[1]))

        # 只取前 2 个最重要的问题
        top_issues = issues[:2]

        for angle_key, diff, is_less, priority in top_issues:
            diff_value = int(diff)
            suggestion_zh = ""
            suggestion_en = ""
            title_zh = ""
            title_en = ""

            # 根据角度类型和阶段，生成贴近投篮教学的语言
            if angle_key == 'knee_angle':
                if is_less:
                    title_zh = "腿部发力不足"
                    title_en = "Insufficient leg drive"
                    suggestion_zh = f"准备阶段膝盖弯曲不够，建议加深屈膝幅度，更好地利用腿部力量带动投篮。"
                    suggestion_en = f"Your knee bend is not deep enough. Try bending your knees more to generate power from your legs."
                else:
                    title_zh = "屈膝过度"
                    title_en = "Excessive knee bend"
                    suggestion_zh = f"膝盖弯曲幅度过大，可能导致发力不流畅，建议调整到更自然的屈膝角度。"
                    suggestion_en = f"Your knee bend is too deep, which may disrupt your shooting rhythm. Try a more natural bend."

            elif angle_key == 'elbow_angle':
                if is_less:
                    title_zh = "手肘未充分弯曲"
                    title_en = "Elbow not flexed enough"
                    suggestion_zh = f"手肘弯曲角度不足，建议在举球时保持手肘更充分地弯曲，形成标准投篮姿势。"
                    suggestion_en = f"Your elbow is not bent enough. Keep your elbow more flexed as you raise the ball."
                else:
                    title_zh = "手肘外展"
                    title_en = "Elbow flare"
                    suggestion_zh = f"手肘有外翻趋势，建议将手肘向内收，保持更紧凑的投篮动作。"
                    suggestion_en = f"Your elbow is flaring out. Tuck it in for a more compact and consistent shot."

            elif angle_key == 'shoulder_angle':
                if is_less:
                    title_zh = "持球位置偏低"
                    title_en = "Ball position too low"
                    suggestion_zh = f"持球高度不足，建议将球举到更高的起始位置，获得更好的投篮发力点。"
                    suggestion_en = f"Your ball position is too low. Start with the ball higher for better shooting mechanics."
                else:
                    title_zh = "持球位置偏高"
                    title_en = "Ball position too high"
                    suggestion_zh = f"持球位置过高，可能影响投篮节奏，建议调整到更舒适的出手高度。"
                    suggestion_en = f"Your ball position is too high. Lower it slightly for a smoother shooting motion."

            elif angle_key == 'wrist_angle':
                if is_less:
                    title_zh = "压腕不充分"
                    title_en = "Incomplete wrist snap"
                    suggestion_zh = f"跟随动作中手腕下压不够充分，建议在出手后更完整地完成压腕动作。"
                    suggestion_en = f"Your wrist snap is incomplete. Follow through with a fuller wrist motion after release."
                else:
                    title_zh = "手腕角度过陡"
                    title_en = "Wrist angle too steep"
                    suggestion_zh = f"手腕角度偏陡，建议调整压腕角度，使投篮弧线更平滑。"
                    suggestion_en = f"Your wrist angle is too steep. Adjust for a smoother shooting arc."

            elif angle_key == 'trunk_angle':
                if is_less:
                    title_zh = "身体过于前倾"
                    title_en = "Body leaning forward"
                    suggestion_zh = f"身体前倾较多，建议保持更直立的上身姿态，提升投篮稳定性。"
                    suggestion_en = f"Your body is leaning too far forward. Stay more upright for better shooting stability."
                else:
                    title_zh = "身体后仰"
                    title_en = "Body leaning back"
                    suggestion_zh = f"投篮时有后仰趋势，建议收紧核心，保持身体垂直发力。"
                    suggestion_en = f"You're leaning back when shooting. Engage your core and stay vertical."

            elif angle_key == 'hip_angle':
                if is_less:
                    title_zh = "髋部位置偏低"
                    title_en = "Hip position too low"
                    suggestion_zh = f"髋部下沉较多，建议保持更稳定的髋部位置，优化力量传递链条。"
                    suggestion_en = f"Your hips are dropping too low. Keep them more stable for better power transfer."
                else:
                    title_zh = "髋部位置偏高"
                    title_en = "Hip position too high"
                    suggestion_zh = f"髋部位置偏高，建议适当降低重心，更好地衔接上下肢发力。"
                    suggestion_en = f"Your hips are too high. Lower your center of gravity for better leg-to-arm connection."

            if suggestion_zh and title_zh:
                suggestions.append({
                    "type": "template_difference",
                    "severity": "high" if priority == 2 else "medium",
                    "description": title_zh,
                    "description_en": title_en,
                    "phase": phase,
                    "phase_name_zh": phase_names_zh.get(phase, phase),
                    "phase_name_en": phase_names_en.get(phase, phase),
                    "suggestion": suggestion_zh,
                    "suggestion_en": suggestion_en,
                    "priority": priority
                })

    # 按优先级排序所有建议
    suggestions.sort(key=lambda x: (-x['priority'], x['phase']))

    return suggestions


@router.post("/upload", response_model=UploadResponse)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    shooting_hand: str = "right",
    shooting_style: str = "one_motion",
    template_id: str = None,
    generate_video: bool = False,
    generate_skeleton_video: bool = False
):
    """
    上传投篮视频

    - **file**: 视频文件 (支持 mp4, mov, avi, webm)
    - **shooting_hand**: 投篮手 ("left" 或 "right")
    - **shooting_style**: 投篮方式 ("one_motion" 或 "two_motion")
    - **template_id**: 可选，对比模板ID
    - **generate_video**: 是否生成标注视频（默认false，提高速度）
    - **generate_skeleton_video**: 是否生成骨骼运动视频（默认false）

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
        "template_id": template_id,
        "created_at": datetime.now().isoformat()
    }

    # 清理旧任务（保留最近 MAX_TASKS 个）
    deleted = cleanup_old_tasks()
    if deleted:
        print(f"[CLEANUP] 自动清理了 {len(deleted)} 个旧任务")

    # 添加后台任务
    background_tasks.add_task(run_analysis, task_id, video_path, shooting_hand, shooting_style, template_id, generate_video, generate_skeleton_video)
    
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
