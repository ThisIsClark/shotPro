"""
Export API Routes
导出功能的API路由
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pathlib import Path

from ...services.pdf_service import PDFExportService
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
