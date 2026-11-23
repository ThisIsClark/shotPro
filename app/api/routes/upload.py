"""
Upload Routes
视频上传接口
"""

import uuid
import shutil
import aiofiles
import asyncio
from fastapi.responses import FileResponse
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, Depends, Request

from ...config import settings
from ...models.schemas import UploadResponse, TaskStatus, TaskStatusResponse
from ...services.analysis_service import AnalysisService, AnalysisConfig, AnalysisProgress
from ...services.db_service import db_service
from ...services.storage_service import storage_service
from ...services.supabase_client import is_supabase_enabled
from ...services.audit_service import audit_service, AuditAction
from ...models.template import TemplateManager
from ...services.comparison_service import compare_curves
from ..deps import get_current_user_optional, get_user_id
from ...services.feedback_service import feedback_store
from ...services.trial_service import trial_store

router = APIRouter(prefix="/videos", tags=["videos"])

# 任务状态存储（内存 fallback，当数据库不可用时使用）
task_store: dict[str, dict] = {}

# 最大保留内存任务数量（仅用于 fallback）
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
        if trial_store.get(task_id):
            continue  # Durable report retention is independent of the old 10-task cache.
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


def run_analysis(task_id: str, video_path: Path, shooting_hand: str = "right", shooting_style: str = "one_motion", template_id: str = None, generate_video: bool = False, generate_skeleton_video: bool = False, user_id: Optional[str] = None, use_db: bool = False):
    """运行分析任务（后台任务）- 支持数据库和内存两种模式

    use_db 由 upload 流程根据用户类型决定传入：本地管理员走内存模式（False）。
    """
    try:
        if feedback_store.get(task_id):
            feedback_store.change(task_id, lambda r: r.update(analysis_state="processing"))
            feedback_store.prepare_playback(task_id)
        # 使用数据库更新状态（如果可用）

        if use_db:
            asyncio.run(db_service.update_analysis(task_id, status="processing", progress=0))
        else:
            # 内存 fallback
            task_store[task_id]["status"] = TaskStatus.PROCESSING
            task_store[task_id]["message"] = "Analyzing..."

        # 进度回调
        def progress_callback(progress: AnalysisProgress):
            if use_db:
                # 数据库模式：异步更新需要在线程中执行
                asyncio.run(db_service.update_analysis(task_id, progress=progress.percentage))
            else:
                # 内存 fallback
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

                # M3: 曲线对比（仅当模板含曲线数据时）
                if template.has_curve_data:
                    print(f"[DEBUG] 模板含曲线数据，开始曲线对比")
                    template_curves = template_manager.get_template_curves(template_id)
                    if template_curves and result.frame_data_url:
                        # 读取用户的 per-frame 时序数据
                        user_frame_data_path = settings.results_dir / task_id / "frame_data.json"
                        if user_frame_data_path.exists():
                            import json as _json
                            with open(user_frame_data_path, 'r', encoding='utf-8') as f:
                                user_frame_data = _json.load(f)
                            curve_comparison = compare_curves(user_frame_data, template_curves)
                            if curve_comparison:
                                result_dict["template_comparison"]["curve_comparison"] = curve_comparison
                                print(f"[DEBUG] curve_comparison 已添加，joints: {len(curve_comparison['joints'])}")
                            else:
                                print(f"[DEBUG] ⚠️ compare_curves 返回 None（数据不足）")
                        else:
                            print(f"[DEBUG] ⚠️ 用户 frame_data.json 不存在: {user_frame_data_path}")
                    else:
                        print(f"[DEBUG] ⚠️ 模板曲线数据缺失或用户无 frame_data_url")

                # 生成基于模板的改进建议
                template_suggestions = _generate_template_based_suggestions(comparison_data)

                # 模板对比建议暂时不合并到 coordination_issues
                # coordination_issues 是专门针对发力连贯性的，模板建议作为额外的参考
                pass

                print(f"[DEBUG] 生成的模板建议数量：{len(template_suggestions)}")
            else:
                print(f"[DEBUG] 模板未找到: {template_id}")

        if not result_dict.get("key_frames"):
            raise ValueError("No usable shooting keyframes detected. Please try another video.")

        # 持久化结果到磁盘（先写文件，再更新状态，避免前端读到空结果）
        result_dir = settings.results_dir / task_id
        result_file = result_dir / "result.json"

        # 上传关键帧图片到 Supabase Storage（如果可用）
        if storage_service.is_available() and not trial_store.get(task_id):
            print(f"[Storage] Uploading key frames for task {task_id}")
            for kf in result_dict.get("key_frames", []):
                local_image_path = kf.get("image_url", "")
                # 本地路径格式: /results/{task_id}/keyframe_{phase}.png
                if local_image_path.startswith("/results/"):
                    # 提取文件名
                    image_filename = local_image_path.split("/")[-1]
                    full_local_path = settings.results_dir / task_id / image_filename

                    if full_local_path.exists():
                        storage_url = storage_service.upload_result_image(
                            full_local_path,
                            user_id=user_id,
                            task_id=task_id,
                            image_name=image_filename
                        )
                        if storage_url:
                            print(f"[Storage] Uploaded: {image_filename} -> {storage_url}")
                            # 更新 URL 为 Storage URL
                            kf["image_url"] = storage_url

        with open(result_file, 'w', encoding='utf-8') as f:
            import json
            json.dump(result_dict, f, ensure_ascii=False, indent=2)
        print(f"[DEBUG] 结果已保存到: {result_file}")
        print(f"[DEBUG] 结果包含 template_comparison: {result_dict.get('template_comparison') is not None}")
        if result_dict.get('template_comparison') and 'comparisons' in result_dict['template_comparison']:
            print(f"[DEBUG] template_comparison.comparisons 数量: {len(result_dict['template_comparison']['comparisons'])}")

        # 更新完成状态（文件已写入，再标记完成，确保前端能读到结果）
        if use_db:
            asyncio.run(db_service.update_analysis(
                task_id,
                status="completed",
                progress=100,
                overall_score=None,  # 新格式不再有评分
                rating=None,  # 新格式不再有评分
                total_frames=result_dict.get("total_frames"),
                fps=result_dict.get("fps"),
                duration=result_dict.get("duration")
            ))

            # 记录审计日志
            asyncio.run(audit_service.log(
                action=AuditAction.ANALYSIS_COMPLETED,
                user_id=user_id,
                resource_id=task_id,
                resource_type="analysis",
                details={
                    "coordination_issues_count": len(result_dict.get("coordination_issues", [])),
                    "issues_detected": sum(1 for issue in result_dict.get("coordination_issues", []) if issue.get("detected")),
                    "shooting_hand": shooting_hand,
                    "shooting_style": shooting_style,
                    "template_id": template_id,
                    "video_filename": video_path.name if video_path else "unknown"
                }
            ))
        else:
            # 内存 fallback
            task_store[task_id]["status"] = TaskStatus.COMPLETED
            task_store[task_id]["progress"] = 100
            task_store[task_id]["message"] = "Analysis complete"
            task_store[task_id]["result"] = result_dict

        from ...services.admin_metrics import quality
        quality(task_id, frames=len(result_dict.get("key_frames", [])))
        from ...services.admin_insights import task_metadata
        task_metadata(task_id, frames=result_dict.get("key_frames", []))
        trial_store.finish(task_id, True)

        # Preserve a private snapshot for feedback before legacy cleanup.
        feedback_store.snapshot(task_id, result_dict, result_dir)

        # ===== 分析完成后删除原始视频（节省存储空间）=====
        # 删除本地视频文件
        try:
            if not (settings.engine_session_origin and user_id) and video_path.exists():
                video_path.unlink()
                print(f"[CLEANUP] 已删除本地视频文件: {video_path}")
        except Exception as cleanup_error:
            print(f"[CLEANUP] 删除本地视频失败: {cleanup_error}")

    except Exception as e:
        from ...services.admin_metrics import quality
        quality(task_id, error=type(e).__name__ + ': ' + str(e))
        trial_store.finish(task_id, False)
        error_msg = str(e)
        if feedback_store.get(task_id):
            feedback_store.change(task_id, lambda r: r.update(analysis_state="failed", error="Automatic analysis failed. Your video is saved for human review."))
        print(f"[Analysis] Analysis failed: {error_msg}")

        if use_db:
            asyncio.run(db_service.update_analysis(task_id, status="failed", error_message=error_msg))
            # 记录审计日志（分析失败）
            asyncio.run(audit_service.log(
                action=AuditAction.ANALYSIS_FAILED,
                user_id=user_id,
                resource_id=task_id,
                resource_type="analysis",
                details={
                    "error": error_msg,
                    "video_filename": video_path.name if video_path else "unknown"
                }
            ))
        else:
            task_store[task_id]["status"] = TaskStatus.FAILED
            task_store[task_id]["error"] = error_msg
            task_store[task_id]["message"] = f"Analysis failed: {error_msg}"

        # ===== 分析失败时也删除原始视频（节省存储空间）=====
        try:
            if video_path and video_path.exists():
                video_path.unlink()
                print(f"[CLEANUP] 已删除本地视频文件（失败后清理）: {video_path}")
        except Exception as cleanup_error:
            print(f"[CLEANUP] 删除本地视频失败: {cleanup_error}")


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

    # 阶段名称映射（3帧版本）
    phase_names_zh = {
        'dip_point': '沉球点',
        'min_elbow_point': '最小肘角点',
        'release_point': '出手点',
        'preparation': '准备阶段',
        'lifting': '上升阶段',
        'release': '出手阶段',
        'follow_through': '跟随阶段'
    }
    phase_names_en = {
        'dip_point': 'Dip Point',
        'min_elbow_point': 'Min Elbow Angle',
        'release_point': 'Release Point',
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
    request: Request,
    file: UploadFile = File(...),
    shooting_hand: str = "right",
    shooting_style: str = "one_motion",
    template_id: str = None,
    generate_video: bool = False,
    generate_skeleton_video: bool = False,
    retain_for_feedback: bool = False,
    user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    上传投篮视频（支持可选用户绑定）

    - **file**: 视频文件 (支持 mp4, mov, avi, webm)
    - **shooting_hand**: 投篮手 ("left" 或 "right")
    - **shooting_style**: 投篮方式 ("one_motion" 或 "two_motion")
    - **template_id**: 可选，对比模板ID
    - **generate_video**: 是否生成标注视频（默认false，提高速度）
    - **generate_skeleton_video**: 是否生成骨骼运动视频（默认false）

    如果请求头携带 Authorization: Bearer {token}，分析结果将关联到该用户。

    返回 task_id，可用于查询分析状态和结果
    """
    if request.headers.get("authorization") and not user:
        raise HTTPException(401, "Your session expired. Please sign in again.")
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

    # 获取用户 ID（可选）
    user_id = get_user_id(user)

    visitor_id = trial_store.visitor(request) if not user else None
    if not user and trial_store.remaining(visitor_id) == 0:
        raise HTTPException(403, "Your free trial is used or in progress. Sign in to continue.")

    # 检查用户分析次数（订阅用户不限，本地管理员不限）
    is_local_user = user and user.get("is_local", False)
    is_subscribed = False

    # 判断是否使用数据库：本地管理员（user_id 非 UUID，如 "admin"）走纯内存模式，
    # 否则 Supabase 的 analyses.user_id(UUID) 列写入会失败，导致任务状态无处可查、前端卡死。
    engine_member = bool(user and user.get("provider") == "gefei")
    use_db = not engine_member and bool(user_id) and is_supabase_enabled() and db_service.is_available() and not is_local_user

    if user_id and not engine_member and not is_local_user and not use_db:
        raise HTTPException(503, "Could not check your credits. Please try again later.")

    if use_db and user_id and not is_local_user:
        is_subscribed = await db_service.is_user_subscribed(user_id)
        if not is_subscribed:
            remaining = await db_service.get_user_credits(user_id)
            if remaining <= 0:
                raise HTTPException(
                    status_code=403,
                    detail="No credits remaining. Please subscribe or purchase more analyses to continue."
                )

    # 生成任务 ID
    task_id = str(uuid.uuid4())

    # 创建数据库记录（如果可用）
    if use_db:
        db_record = await db_service.create_analysis(
            analysis_id=task_id,  # 使用预生成的 task_id
            user_id=user_id,
            video_filename=file.filename or "unknown",
            video_path="",  # 暂时为空，保存文件后更新
            shooting_hand=shooting_hand,
            shooting_style=shooting_style,
            template_id=template_id,
            generate_video=generate_video,
            generate_skeleton_video=generate_skeleton_video
        )
        if not db_record:
            raise HTTPException(503, "Could not save your analysis. Please try again.")
        if db_record:
            print(f"[DB] Created analysis record with ID: {task_id}")

    # 保存文件
    file_ext = Path(file.filename).suffix.lower() if file.filename else ".mp4"
    video_path = settings.upload_dir / f"{task_id}{file_ext}"

    await save_upload_file(file, video_path)

    # 检查文件大小
    file_size_mb = video_path.stat().st_size / (1024 * 1024)
    if file_size_mb > settings.max_video_size_mb:
        video_path.unlink()  # 删除文件
        if use_db:
            await db_service.delete_analysis(task_id)
        raise HTTPException(
            status_code=400,
            detail=f"文件过大: {file_size_mb:.1f}MB，最大允许 {settings.max_video_size_mb}MB"
        )

    # 更新视频路径（数据库）
    if use_db:
        await db_service.update_analysis(task_id, result_path=str(video_path))

    duration = 0
    # 检查视频时长
    try:
        import cv2
        cap = cv2.VideoCapture(str(video_path))
        if cap.isOpened():
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            cap.release()
            if fps > 0 and frame_count > 0:
                duration = frame_count / fps
                if duration > (min(10, settings.max_video_duration_seconds) if not user else settings.max_video_duration_seconds):
                    video_path.unlink()
                    if use_db:
                        await db_service.delete_analysis(task_id)
                    raise HTTPException(
                        status_code=400,
                        detail=f"视频时长 {duration:.1f}s 超过限制，最长允许 {settings.max_video_duration_seconds}s"
                    )
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Upload] 视频时长检查失败（忽略）: {e}")

    if duration <= 0:
        video_path.unlink(missing_ok=True)
        if use_db:
            await db_service.delete_analysis(task_id)
        raise HTTPException(400, "Cannot read this video. Please upload a valid video.")
    try:
        trial_store.reserve(task_id, visitor_id, user_id, file.filename or 'Video',
                            trial_store.sign(request.client.host if request.client else 'unknown'))
    except HTTPException:
        video_path.unlink(missing_ok=True)
        if use_db:
            await db_service.delete_analysis(task_id)
        raise

    from ...services.admin_insights import task_metadata
    task_metadata(task_id, metadata={'shooting_hand':shooting_hand, 'shooting_style':shooting_style,
                                    'template_id':template_id, 'duration':duration, 'file_size_mb':file_size_mb})
    # Keep an explicitly requested private copy, independent of legacy cleanup.
    if retain_for_feedback and user and not engine_member:
        feedback_store.capture(task_id, user, video_path, file.filename or "Video", locals().get("duration", 0))
        feedback_store.change(task_id, lambda r: r.update(shooting_hand=shooting_hand))

    # 扣减分析次数（订阅用户不扣减，本地管理员不扣减）
    if use_db and user_id and not is_local_user and not is_subscribed:
        new_remaining = await db_service.decrement_user_credits(user_id)
        print(f"[Credits] User {user_id} credits: {new_remaining + 1} -> {new_remaining}")

    # 内存 fallback：初始化任务状态
    if not use_db:
        task_store[task_id] = {
            "status": TaskStatus.PENDING,
            "progress": 0,
            "message": "Task created, processing...",
            "result": None,
            "error": None,
            "video_path": str(video_path),
            "filename": file.filename,
            "template_id": template_id,
            "created_at": datetime.now().isoformat()
        }

        # 清理旧任务（仅内存模式）
        deleted = cleanup_old_tasks()
        if deleted:
            print(f"[CLEANUP] 自动清理了 {len(deleted)} 个旧任务")

    # 添加后台任务
    background_tasks.add_task(
        run_analysis,
        task_id,
        video_path,
        shooting_hand,
        shooting_style,
        template_id,
        generate_video,
        generate_skeleton_video,
        user_id,
        use_db
    )

    # 记录审计日志（分析开始）
    if use_db:
        await audit_service.log(
            action=AuditAction.ANALYSIS_STARTED,
            user_id=user_id,
            resource_id=task_id,
            resource_type="analysis",
            details={
                "video_filename": file.filename,
                "shooting_hand": shooting_hand,
                "shooting_style": shooting_style,
                "template_id": template_id,
                "generate_video": generate_video,
                "generate_skeleton_video": generate_skeleton_video,
                "file_size_mb": file_size_mb
            }
        )

    return UploadResponse(
        task_id=task_id,
        message="Video uploaded, starting analysis",
        filename=file.filename or "unknown"
    )


async def authorize_report(task_id, request, user):
    if trial_store.authorize(task_id, request, user):
        return
    if settings.engine_session_origin:
        raise HTTPException(404, 'Report not found.')
    record = await db_service.get_analysis(task_id) if db_service.is_available() else None
    if not user or not ((record and record.get('user_id') == user['id']) or user.get('role') == 'admin'):
        raise HTTPException(404, 'Report not found.')


@router.get("/tasks/{task_id}/status", response_model=TaskStatusResponse)
async def get_task_status(task_id: str, request: Request, user=Depends(get_current_user_optional)):
    await authorize_report(task_id, request, user)
    persisted = trial_store.get(task_id)
    if persisted and persisted['state'] == 'failed':
        return TaskStatusResponse(task_id=task_id, status=TaskStatus.FAILED, progress=0,
                                  message='Analysis did not complete. Please try another video.',
                                  error='Analysis failed or timed out.')
    """
    获取分析任务状态

    - **task_id**: 任务ID
    """
    # 尝试从数据库获取
    use_db = is_supabase_enabled() and db_service.is_available()

    if use_db:
        analysis = await db_service.get_analysis(task_id)
        if analysis:
            return TaskStatusResponse(
                task_id=task_id,
                status=analysis.get("status", "pending"),
                progress=analysis.get("progress", 0),
                message="",  # 数据库不存储 message
                result=None,  # 结果需要从磁盘读取
                error=analysis.get("error_message")
            )

    # 内存 fallback
    if task_id not in task_store and trial_store.get(task_id):
        record = trial_store.get(task_id)
        return TaskStatusResponse(task_id=task_id, status=record['state'],
                                  progress=100 if record['state']=='completed' else 0,
                                  message=record['state'])
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = task_store[task_id]

    return TaskStatusResponse(
        task_id=task_id,
        status=task["status"],
        progress=task["progress"],
        message=task["message"],
        result=task.get("result"),
        error=task.get("error")
    )


@router.get("/tasks/{task_id}/result")
async def get_task_result(task_id: str, request: Request, user=Depends(get_current_user_optional)):
    await authorize_report(task_id, request, user)
    """
    获取分析结果

    - **task_id**: 任务ID
    """
    # 尝试从数据库获取状态
    use_db = is_supabase_enabled() and db_service.is_available()

    status_info = None
    if use_db:
        analysis = await db_service.get_analysis(task_id)
        if analysis:
            status_info = analysis

    # 内存 fallback
    if not status_info and task_id in task_store:
        status_info = task_store[task_id]

    # 磁盘 fallback（历史记录场景：DB无记录且已从内存淘汰）
    if not status_info:
        result_file = settings.results_dir / task_id / "result.json"
        if result_file.exists():
            status_info = {"status": "completed"}

    if not status_info and trial_store.get(task_id):
        status_info = {"status": trial_store.get(task_id)["state"]}
    if not status_info:
        raise HTTPException(status_code=404, detail="任务不存在")

    persisted = trial_store.get(task_id)
    if persisted and persisted["state"] in ("failed", "processing"):
        status_info = {"status": persisted["state"], "error": "Analysis did not complete. Please try another video."}
    # 检查状态
    task_status = status_info.get("status", "pending")

    if task_status == "pending":
        raise HTTPException(status_code=202, detail="任务等待处理中")

    if task_status == "processing":
        progress = status_info.get("progress", 0)
        raise HTTPException(
            status_code=202,
            detail=f"任务处理中: {progress}%"
        )

    if task_status == "failed":
        error_msg = status_info.get("error_message") or status_info.get("error")
        raise HTTPException(
            status_code=500,
            detail=f"分析失败: {error_msg}"
        )

    # 从磁盘读取结果
    result_dir = settings.results_dir / task_id
    result_file = result_dir / "result.json"

    if result_file.exists():
        import json
        with open(result_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    # 内存 fallback：返回内存中的结果
    return status_info.get("result")


def saved_source(task_id, row):
    suffix = Path(row["filename"]).suffix.lower()
    return settings.upload_dir / (task_id + suffix)


@router.get("/tasks/{task_id}/source")
async def get_source_video(task_id: str, request: Request, user=Depends(get_current_user_optional)):
    if not settings.engine_session_origin or not user:
        raise HTTPException(404, "Video not found.")
    row = trial_store.get(task_id)
    if not row or row["owner"] != user["id"] or row["state"] != "completed":
        raise HTTPException(404, "Video not found.")
    source = saved_source(task_id, row)
    if not source.is_file():
        raise HTTPException(404, "Video not found.")
    return FileResponse(source, filename=Path(row["filename"]).name,
                        headers={"Cache-Control": "private, no-store"})


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str, request: Request, user=Depends(get_current_user_optional)):
    await authorize_report(task_id, request, user)
    persisted = trial_store.get(task_id)
    if persisted and persisted['state'] == 'processing':
        raise HTTPException(409, 'Wait for analysis to finish before deleting this report.')
    """
    删除任务及相关文件

    - **task_id**: 任务ID
    """
    retained = feedback_store.get(task_id)
    if retained and retained["state"] != "deleted":
        raise HTTPException(409, "Delete this video from Training to remove its feedback and private media too.")
    use_db = is_supabase_enabled() and db_service.is_available()

    # 获取任务信息
    task_info = None
    if use_db:
        analysis = await db_service.get_analysis(task_id)
        if analysis:
            task_info = analysis

    # 内存 fallback
    if not task_info and task_id in task_store:
        task_info = task_store[task_id]

    if not task_info and trial_store.get(task_id):
        task_info = {"video_path": str(saved_source(task_id, persisted))}
    if not task_info:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 删除上传的视频
    video_path = Path(task_info.get("video_path") or task_info.get("result_path", ""))
    if video_path.exists():
        video_path.unlink()

    # 删除结果目录
    result_dir = settings.results_dir / task_id
    if result_dir.exists():
        shutil.rmtree(result_dir)

    # 从数据库删除（如果可用）
    if use_db:
        await db_service.delete_analysis(task_id)

    # 从内存删除（如果存在）
    if task_id in task_store:
        del task_store[task_id]

    trial_store.delete(task_id)
    return {"message": "任务已删除", "task_id": task_id}


@router.get("/history")
async def get_analysis_history(
    limit: int = 20,
    offset: int = 0,
    user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    获取分析历史记录

    - **limit**: 返回数量（默认20）
    - **offset**: 偏移量（默认0）
    """
    if not user:
        raise HTTPException(401, 'Sign in to view your saved reports.')
    import json
    rows = {r['id']: {'task_id': r['id'], 'video_filename': r['filename'],
                     'status': r['state'], 'created_at': datetime.fromtimestamp(r['created']).isoformat()}
            for r in trial_store.history(user['id'])}
    if db_service.is_available() and not user.get('is_local') and user.get("provider") != "gefei":
        for r in await db_service.get_user_analyses(user_id=user['id'], limit=100, offset=0):
            tracked = trial_store.get(r['id'])
            if tracked and tracked['state'] == 'deleted':
                continue
            if r['id'] not in rows:
                rows[r['id']] = dict(task_id=r['id'], video_filename=r.get('video_filename', 'Video'),
                                    status=r['status'], created_at=r.get('created_at', ''))
    for row in rows.values():
        result_file = settings.results_dir / row['task_id'] / 'result.json'
        if result_file.exists():
            data = json.loads(result_file.read_text())
            issues = data.get('coordination_issues', [])
            row.update(duration=data.get('duration'), issues_count=len(issues),
                       issues_detected=sum(bool(i.get('detected')) for i in issues))
    return sorted(rows.values(), key=lambda r: r['created_at'], reverse=True)[max(0,offset):max(0,offset)+min(100,max(1,limit))]
