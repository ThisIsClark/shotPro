"""
Export API Routes
导出功能的API路由
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pathlib import Path

from ...services.pdf_service import PDFExportService
from ...services.image_export_service import ImageExportService
from ...api.routes.upload import task_store
from ...config import settings

router = APIRouter()


@router.get("/export/{task_id}/pdf")
async def export_pdf(
    task_id: str,
    language: str = Query('zh-CN', regex='^(zh-CN|en-US)$')
):
    """
    导出分析结果为PDF
    
    Args:
        task_id: 任务ID
        language: 语言选择 (zh-CN 或 en-US)
    
    Returns:
        PDF文件
    """
    # 检查任务是否存在
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_info = task_store[task_id]
    
    # 检查任务是否完成
    if task_info['status'] != 'completed':
        raise HTTPException(
            status_code=400,
            detail=f"Task not completed. Current status: {task_info['status']}"
        )
    
    try:
        # 创建PDF服务
        pdf_service = PDFExportService(output_dir=settings.results_dir)
        
        # 生成PDF
        pdf_path = pdf_service.generate_report(
            task_id=task_id,
            analysis_result=task_info['result'],
            language=language
        )
        
        # 返回PDF文件
        return FileResponse(
            path=str(pdf_path),
            media_type='application/pdf',
            filename=f"shooting_analysis_{task_id}.pdf"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate PDF: {str(e)}"
        )


@router.get("/export/{task_id}/images/keyframes")
async def export_keyframes_images(task_id: str):
    """
    导出关键帧图片（单独的图片）
    
    Args:
        task_id: 任务ID
    
    Returns:
        ZIP文件包含所有关键帧
    """
    # 检查任务是否存在
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_info = task_store[task_id]
    
    # 检查任务是否完成
    if task_info['status'] != 'completed':
        raise HTTPException(
            status_code=400,
            detail=f"Task not completed. Current status: {task_info['status']}"
        )
    
    try:
        # 创建图片导出服务
        image_service = ImageExportService(output_dir=settings.results_dir)
        
        # 生成关键帧ZIP
        zip_path = image_service.export_key_frames(
            task_id=task_id,
            result=task_info['result']
        )
        
        if not zip_path or not zip_path.exists():
            raise HTTPException(
                status_code=500,
                detail="Failed to generate keyframes images"
            )
        
        # 返回ZIP文件
        return FileResponse(
            path=str(zip_path),
            media_type='application/zip',
            filename=f"shooting_analysis_{task_id}_keyframes.zip"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export keyframes: {str(e)}"
        )


@router.get("/export/{task_id}/images/comparisons")
async def export_comparison_images(task_id: str, language: str = Query('zh-CN', regex='^(zh-CN|en-US)$')):
    """
    导出对比图片（并排对比）
    
    Args:
        task_id: 任务ID
        language: 语言选择 (zh-CN 或 en-US)
    
    Returns:
        ZIP文件包含所有对比图片
    """
    # 检查任务是否存在
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_info = task_store[task_id]
    
    # 检查任务是否完成
    if task_info['status'] != 'completed':
        raise HTTPException(
            status_code=400,
            detail=f"Task not completed. Current status: {task_info['status']}"
        )
    
    try:
        # 创建图片导出服务
        image_service = ImageExportService(output_dir=settings.results_dir)
        
        print(f"[DEBUG export_comparison_images] task_id: {task_id}")
        print(f"[DEBUG export_comparison_images] result keys: {list(task_info['result'].keys())}")
        print(f"[DEBUG export_comparison_images] has template_comparison: {'template_comparison' in task_info['result']}")
        
        # 生成对比图片ZIP
        zip_path = image_service.export_comparison_images(
            task_id=task_id,
            result=task_info['result'],
            language=language
        )
        
        print(f"[DEBUG export_comparison_images] zip_path: {zip_path}")
        print(f"[DEBUG export_comparison_images] zip_path exists: {zip_path.exists() if zip_path else 'None'}")
        
        if not zip_path or not zip_path.exists():
            raise HTTPException(
                status_code=500,
                detail="Failed to generate comparison images or no template comparison available"
            )
        
        # 返回ZIP文件
        return FileResponse(
            path=str(zip_path),
            media_type='application/zip',
            filename=f"shooting_analysis_{task_id}_comparisons.zip"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export comparisons: {str(e)}"
        )


@router.get("/export/{task_id}/images/all")
async def export_all_images(task_id: str, language: str = Query('zh-CN', regex='^(zh-CN|en-US)$')):
    """
    导出所有图片（关键帧 + 对比图）
    
    Args:
        task_id: 任务ID
        language: 语言选择 (zh-CN 或 en-US)
    
    Returns:
        ZIP文件包含所有图片
    """
    # 检查任务是否存在
    if task_id not in task_store:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task_info = task_store[task_id]
    
    # 检查任务是否完成
    if task_info['status'] != 'completed':
        raise HTTPException(
            status_code=400,
            detail=f"Task not completed. Current status: {task_info['status']}"
        )
    
    try:
        # 创建图片导出服务
        image_service = ImageExportService(output_dir=settings.results_dir)
        
        # 生成所有图片ZIP
        zip_path = image_service.export_all_images(
            task_id=task_id,
            result=task_info['result'],
            language=language
        )
        
        if not zip_path or not zip_path.exists():
            raise HTTPException(
                status_code=500,
                detail="Failed to generate all images"
            )
        
        # 返回ZIP文件
        return FileResponse(
            path=str(zip_path),
            media_type='application/zip',
            filename=f"shooting_analysis_{task_id}_all_images.zip"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export all images: {str(e)}"
        )
