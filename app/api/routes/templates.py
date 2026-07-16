"""
Templates API Routes
模板管理API路由
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
from typing import Optional, List
import uuid
import shutil
import json

from app.config import settings
from app.models.template import TemplateManager, TemplateKeyFrame
from app.services.analysis_service import AnalysisService, AnalysisConfig
from app.api.deps import require_admin

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])

# 初始化模板管理器
templates_dir = settings.base_dir / "templates"
template_manager = TemplateManager(templates_dir)


def _extract_phase_boundaries(frame_data: list) -> dict:
    """
    从 per-frame 时序数据推阶段边界，供 M3 曲线对比按阶段对齐用。

    返回形如：
        {
            "preparation": {"start_frame": 0, "end_frame": 12, "start_time": 0.0, "end_time": 0.4},
            "lifting": {...},
            "release": {...},
            "follow_through": {...}
        }
    只记录出现在 frame_data 里的阶段；unknown 阶段跳过。
    """
    boundaries: dict = {}
    for fd in frame_data:
        phase = fd.get("phase")
        if not phase or phase == "unknown":
            continue
        if phase not in boundaries:
            boundaries[phase] = {
                "start_frame": fd["frame_number"],
                "end_frame": fd["frame_number"],
                "start_time": fd["timestamp"],
                "end_time": fd["timestamp"],
            }
        else:
            boundaries[phase]["end_frame"] = fd["frame_number"]
            boundaries[phase]["end_time"] = fd["timestamp"]
    return boundaries


@router.post("/create")
async def create_template(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(""),
    shooting_hand: str = Form("right"),
    admin: dict = Depends(require_admin)
):
    """
    创建投篮模板（仅管理员）

    上传视频并创建模板，保存关键帧 + per-frame 曲线数据（angles.json + phases.json）。
    需要管理员 JWT（Authorization: Bearer {token}）。
    """
    # 验证文件类型
    if not file.content_type or not file.content_type.startswith('video/'):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a video file.")
    
    # 生成模板ID
    template_id = f"template_{uuid.uuid4().hex[:12]}"
    
    # 创建临时目录
    temp_dir = settings.base_dir / "temp" / template_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # 保存上传的视频
    video_path = temp_dir / file.filename
    try:
        with open(video_path, 'wb') as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        file.file.close()
    
    # 创建模板目录
    template_dir = template_manager.get_template_dir(template_id)
    template_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # 分析视频获取关键帧
        config = AnalysisConfig(
            shooting_hand=shooting_hand,
            generate_key_frames=True,
            generate_annotated_video=False,  # 模板不需要标注视频
            generate_evaluation=False  # 模板不需要评分和建议
        )
        
        # AnalysisService 会自动创建所需的模块
        analysis_service = AnalysisService(config=config)
        
        # 执行分析
        result = analysis_service.analyze_video(
            video_path=video_path,
            task_id=template_id
        )
        
        # 将关键帧复制到模板目录
        key_frames = []
        result_dir = settings.results_dir / template_id
        
        print(f"[DEBUG 模板创建] result.key_frames 数量: {len(result.key_frames)}")
        print(f"[DEBUG 模板创建] result_dir: {result_dir}")
        print(f"[DEBUG 模板创建] result_dir 是否存在: {result_dir.exists()}")
        
        for kf in result.key_frames:
            # image_path 格式: /results/{task_id}/{filename}
            # 提取文件名
            image_filename = Path(kf.image_path).name
            temp_image_path = result_dir / image_filename
            
            print(f"[DEBUG 模板创建] 处理关键帧: phase={kf.phase.value}, image_path={kf.image_path}")
            print(f"[DEBUG 模板创建] temp_image_path: {temp_image_path}")
            print(f"[DEBUG 模板创建] 文件是否存在: {temp_image_path.exists()}")
            
            if temp_image_path.exists():
                # 使用阶段名作为新文件名
                new_image_name = f"{kf.phase.value}.jpg"
                new_image_path = template_dir / new_image_name
                shutil.copy(temp_image_path, new_image_path)
                
                print(f"[DEBUG 模板创建] 已复制到: {new_image_path}")
                
                key_frames.append(TemplateKeyFrame(
                    phase=kf.phase.value,
                    frame_number=kf.frame_number,
                    timestamp=kf.timestamp,
                    image_path=f"templates/{template_id}/{new_image_name}",
                    angles=kf.angles.to_dict() if kf.angles else None
                ))
            else:
                print(f"[DEBUG 模板创建] ⚠️ 文件不存在，跳过: {temp_image_path}")
        
        print(f"[DEBUG 模板创建] 最终 key_frames 数量: {len(key_frames)}")

        # 持久化 per-frame 曲线数据（M2）：从分析结果目录拷 frame_data.json -> angles.json
        has_curve_data = False
        if result.frame_data_url:
            src_frame_data = result_dir / "frame_data.json"
            if src_frame_data.exists():
                dst_angles = template_dir / "angles.json"
                shutil.copy(src_frame_data, dst_angles)

                # 推 phases.json：扫 frame_data 的 phase 字段，记录每个阶段的首尾帧
                try:
                    with open(src_frame_data, 'r', encoding='utf-8') as f:
                        frame_data = json.load(f)
                    phases = _extract_phase_boundaries(frame_data)
                    with open(template_dir / "phases.json", 'w', encoding='utf-8') as f:
                        json.dump(phases, f, ensure_ascii=False)
                    has_curve_data = True
                    print(f"[DEBUG 模板创建] 曲线数据已写入: angles.json + phases.json")
                except Exception as e:
                    print(f"[DEBUG 模板创建] ⚠️ phases.json 写入失败: {e}")
                    # angles.json 已拷贝，仍标记为有曲线数据（phases 缺失时对比侧降级处理）
                    has_curve_data = True

        # 创建模板
        template = template_manager.create_template(
            template_id=template_id,
            name=name,
            key_frames=key_frames,
            description=description,
            video_info={
                'filename': file.filename,
                'shooting_hand': shooting_hand
            },
            has_curve_data=has_curve_data
        )
        
        # 后台任务：清理临时文件
        def cleanup():
            try:
                # 清理上传视频的临时目录
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                # 清理分析生成的结果目录
                if result_dir.exists():
                    shutil.rmtree(result_dir)
            except Exception as e:
                print(f"清理临时文件失败: {e}")
        
        background_tasks.add_task(cleanup)
        
        template_dict = template.to_dict()
        
        # 添加 image_url
        for kf in template_dict['key_frames']:
            image_path = kf['image_path']
            
            # 移除 'templates/' 前缀
            if image_path.startswith('templates/'):
                image_path = image_path.replace('templates/', '', 1)
            
            # 确保路径以 /template_images 开头
            if not image_path.startswith('/'):
                image_path = '/' + image_path
                
            if not image_path.startswith('/template_images'):
                image_path = '/template_images' + image_path
                
            kf['image_url'] = image_path
        
        return {
            'success': True,
            'template': template_dict
        }
    
    except Exception as e:
        # 清理失败的模板
        if template_dir.exists():
            shutil.rmtree(template_dir)
        raise HTTPException(status_code=500, detail=f"Failed to create template: {str(e)}")


@router.get("/list")
async def list_templates():
    """获取所有模板列表"""
    templates = template_manager.list_templates()
    return {
        'success': True,
        'templates': templates
    }


@router.get("/{template_id}")
async def get_template(template_id: str):
    """获取单个模板详情"""
    template = template_manager.get_template(template_id)
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # 转换为字典并处理关键帧图片URL
    template_dict = template.to_dict()
    
    # 将image_path转换为前端可访问的image_url
    for kf in template_dict['key_frames']:
        image_path = kf['image_path']
        
        # 移除 'templates/' 前缀，因为 /template_images 已经挂载到了 templates 目录
        if image_path.startswith('templates/'):
            image_path = image_path.replace('templates/', '', 1)
        
        # 确保路径以 /template_images 开头
        if not image_path.startswith('/'):
            image_path = '/' + image_path
            
        if not image_path.startswith('/template_images'):
            image_path = '/template_images' + image_path
            
        kf['image_url'] = image_path
    
    return template_dict


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    admin: dict = Depends(require_admin)
):
    """删除模板（仅管理员）"""
    success = template_manager.delete_template(template_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {
        'success': True,
        'message': 'Template deleted successfully'
    }


@router.get("/{template_id}/curves")
async def get_template_curves(template_id: str):
    """获取模板的 per-frame 角度曲线数据（angles.json）。

    返回可直接被前端时序曲线组件消费的 JSON 数组（与 frame_data.json 结构一致）。
    用于模板「查看」界面展示角度曲线；无曲线数据时返回 404。
    """
    curves = template_manager.get_template_curves(template_id)
    if not curves or not curves.get("angles"):
        raise HTTPException(status_code=404, detail="Template has no curve data")
    return curves["angles"]


@router.get("/{template_id}/keyframe/{phase}")
async def get_template_keyframe(template_id: str, phase: str):
    """获取模板的关键帧图片"""
    template_dir = template_manager.get_template_dir(template_id)
    image_path = template_dir / f"{phase}.jpg"
    
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Keyframe not found")
    
    return FileResponse(image_path, media_type="image/jpeg")
