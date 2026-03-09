"""
Templates API Routes
模板管理API路由
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from pathlib import Path
from typing import Optional, List
import uuid
import shutil

from app.config import settings
from app.models.template import TemplateManager, TemplateKeyFrame
from app.services.analysis_service import AnalysisService, AnalysisConfig

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])

# 初始化模板管理器
templates_dir = settings.base_dir / "templates"
template_manager = TemplateManager(templates_dir)


@router.post("/create")
async def create_template(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(""),
    shooting_hand: str = Form("right")
):
    """
    创建投篮模板
    
    上传视频并创建模板，保存关键帧
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
        
        # 创建模板
        template = template_manager.create_template(
            template_id=template_id,
            name=name,
            key_frames=key_frames,
            description=description,
            video_info={
                'filename': file.filename,
                'shooting_hand': shooting_hand
            }
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
async def delete_template(template_id: str):
    """删除模板"""
    success = template_manager.delete_template(template_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return {
        'success': True,
        'message': 'Template deleted successfully'
    }


@router.get("/{template_id}/keyframe/{phase}")
async def get_template_keyframe(template_id: str, phase: str):
    """获取模板的关键帧图片"""
    template_dir = template_manager.get_template_dir(template_id)
    image_path = template_dir / f"{phase}.jpg"
    
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Keyframe not found")
    
    return FileResponse(image_path, media_type="image/jpeg")
