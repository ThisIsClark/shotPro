"""
Image Export Service
导出分析结果为图片
"""

import io
import zipfile
from pathlib import Path
from typing import Optional, Dict, List
from PIL import Image as PILImage, ImageDraw, ImageFont
import cv2
import numpy as np

from ..config import settings


class ImageExportService:
    """图片导出服务"""
    
    def __init__(self, output_dir: Path):
        """
        初始化图片导出服务
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_image(self, image_path: str) -> Optional[PILImage.Image]:
        """
        加载图片
        
        Args:
            image_path: 图片路径（可以是相对路径或绝对路径）
            
        Returns:
            PIL Image对象，如果加载失败返回None
        """
        try:
            print(f"[DEBUG _load_image] 尝试加载图片: {image_path}")
            # 处理路径
            if image_path.startswith('/template_images/'):
                # 模板图片路径
                # /template_images/xxx -> templates/xxx
                relative_path = image_path.replace('/template_images/', '', 1)
                full_path = settings.templates_dir / relative_path
            elif image_path.startswith('/'):
                # 绝对路径
                full_path = Path(image_path)
            elif image_path.startswith('results/'):
                # 相对路径（results/）
                full_path = self.output_dir / image_path
            elif image_path.startswith('templates/'):
                # 相对路径（templates/）
                full_path = self.output_dir.parent / image_path
            else:
                # 其他情况
                full_path = self.output_dir / image_path
            
            print(f"[DEBUG _load_image] 解析后的路径: {full_path}")
            print(f"[DEBUG _load_image] 路径存在: {full_path.exists()}")
            
            if full_path.exists():
                img = PILImage.open(full_path)
                print(f"[DEBUG _load_image] 成功加载图片: {image_path}")
                return img
            else:
                print(f"图片不存在: {full_path}")
                return None
        except Exception as e:
            print(f"加载图片失败 {image_path}: {e}")
            return None
    
    def _create_comparison_image(
        self,
        user_image_path: str,
        template_image_path: str,
        phase_name: str,
        language: str = 'zh-CN'
    ) -> Optional[PILImage.Image]:
        """
        创建对比图片（并排显示）
        
        Args:
            user_image_path: 用户图片路径
            template_image_path: 模板图片路径
            phase_name: 阶段名称
            language: 语言
            
        Returns:
            对比图片，如果创建失败返回None
        """
        # 加载图片
        user_img = self._load_image(user_image_path)
        template_img = self._load_image(template_image_path)
        
        print(f"[DEBUG _create_comparison_image] user_img: {user_img is not None}, template_img: {template_img is not None}")
        
        if not user_img or not template_img:
            print(f"[DEBUG _create_comparison_image] 图片加载失败，跳过此对比")
            return None
        
        # 统一图片尺寸（取较大的）
        max_width = max(user_img.width, template_img.width)
        max_height = max(user_img.height, template_img.height)
        
        # 调整图片大小
        user_img = user_img.resize((max_width, max_height), PILImage.LANCZOS)
        template_img = template_img.resize((max_width, max_height), PILImage.LANCZOS)
        
        # 创建并排图片
        gap = 20
        total_width = max_width * 2 + gap
        total_height = max_height + 80  # 顶部留出标题空间
        
        comparison_img = PILImage.new('RGB', (total_width, total_height), color=(255, 255, 255))
        draw = ImageDraw.Draw(comparison_img)
        
        # 绘制背景
        draw.rectangle([0, 0, total_width, total_height], fill=(245, 245, 245))
        
        # 绘制标题
        title_color = (50, 50, 50)
        try:
            font = ImageFont.truetype('/System/Library/Fonts/STHeiti Medium.ttc', 24)
        except:
            font = ImageFont.load_default()
        
        text = f"{phase_name} - 对比"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (total_width - text_width) // 2
        draw.text((text_x, 20), text, fill=title_color, font=font)
        
        # 绘制分割线
        line_y = 60
        draw.line([(0, line_y), (total_width, line_y)], fill=(200, 200, 200), width=2)
        
        # 绘制用户图片
        user_x = 0
        user_y = line_y + 10
        comparison_img.paste(user_img, (user_x, user_y))
        
        # 绘制用户标签
        label_y = user_y + max_height + 10
        user_label = "你的投篮"
        draw.text((user_x + 20, label_y), user_label, fill=(255, 165, 0), font=font)
        
        # 绘制模板图片
        template_x = max_width + gap
        template_y = line_y + 10
        comparison_img.paste(template_img, (template_x, template_y))
        
        # 绘制模板标签
        template_label = "模板"
        draw.text((template_x + 20, label_y), template_label, fill=(0, 150, 255), font=font)
        
        return comparison_img
    
    def export_key_frames(self, task_id: str, result: Dict) -> Optional[Path]:
        """
        导出关键帧图片（单独的图片）
        
        Args:
            task_id: 任务ID
            result: 分析结果
            
        Returns:
            ZIP文件路径，如果导出失败返回None
        """
        key_frames = result.get('key_frames', [])
        if not key_frames:
            return None
        
        # 创建ZIP文件
        zip_path = self.output_dir / f"{task_id}_keyframes.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for kf in key_frames:
                phase = kf.get('phase', 'unknown')
                image_url = kf.get('image_url', '')
                
                # 加载图片
                img = self._load_image(image_url)
                if img:
                    # 保存到ZIP
                    img_buffer = io.BytesIO()
                    img.save(img_buffer, format='JPEG', quality=95)
                    img_buffer.seek(0)
                    
                    zip_filename = f"{phase}.jpg"
                    zipf.writestr(zip_filename, img_buffer.read())
                    print(f"添加到ZIP: {zip_filename}")
        
        return zip_path
    
    def export_comparison_images(self, task_id: str, result: Dict, language: str = 'zh-CN') -> Optional[Path]:
        """
        导出对比图片（并排对比）
        
        Args:
            task_id: 任务ID
            result: 分析结果
            language: 语言
            
        Returns:
            ZIP文件路径，如果导出失败返回None
        """
        # 检查是否有模板对比数据
        template_comparison = result.get('template_comparison')
        print(f"[DEBUG export_comparison_images] template_comparison: {template_comparison is not None}")
        
        if not template_comparison:
            print(f"[DEBUG export_comparison_images] 没有模板对比数据")
            return None
        
        comparisons = template_comparison.get('comparisons', [])
        print(f"[DEBUG export_comparison_images] comparisons 数量: {len(comparisons)}")
        
        if not comparisons:
            print(f"[DEBUG export_comparison_images] comparisons 为空")
            return None
        
        # 阶段名称映射
        phase_names = {
            'zh-CN': {
                'preparation': '准备阶段',
                'lifting': '上升阶段',
                'release': '出手阶段',
                'follow_through': '跟随阶段'
            },
            'en-US': {
                'preparation': 'Preparation',
                'lifting': 'Lifting',
                'release': 'Release',
                'follow_through': 'Follow Through'
            }
        }
        
        # 创建ZIP文件
        zip_path = self.output_dir / f"{task_id}_comparisons.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for comp in comparisons:
                phase = comp.get('phase', '')
                phase_name = phase_names.get(language, {}).get(phase, phase)
                
                user_frame = comp.get('user_frame', {})
                template_frame = comp.get('template_frame', {})
                
                user_image_url = user_frame.get('image_url', '')
                template_image_url = template_frame.get('image_url', '')
                
                # 创建对比图片
                comparison_img = self._create_comparison_image(
                    user_image_url,
                    template_image_url,
                    phase_name,
                    language
                )
                
                if comparison_img:
                    # 保存到ZIP
                    img_buffer = io.BytesIO()
                    comparison_img.save(img_buffer, format='JPEG', quality=95)
                    img_buffer.seek(0)
                    
                    zip_filename = f"{phase}_comparison.jpg"
                    zipf.writestr(zip_filename, img_buffer.read())
                    print(f"添加对比图到ZIP: {zip_filename}")
        
        return zip_path
    
    def export_all_images(self, task_id: str, result: Dict, language: str = 'zh-CN') -> Optional[Path]:
        """
        导出所有图片（关键帧 + 对比图）
        
        Args:
            task_id: 任务ID
            result: 分析结果
            language: 语言
            
        Returns:
            ZIP文件路径，如果导出失败返回None
        """
        # 创建ZIP文件
        zip_path = self.output_dir / f"{task_id}_all_images.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 添加关键帧
            key_frames = result.get('key_frames', [])
            for kf in key_frames:
                phase = kf.get('phase', 'unknown')
                image_url = kf.get('image_url', '')
                
                img = self._load_image(image_url)
                if img:
                    img_buffer = io.BytesIO()
                    img.save(img_buffer, format='JPEG', quality=95)
                    img_buffer.seek(0)
                    
                    zip_filename = f"keyframes/{phase}.jpg"
                    zipf.writestr(zip_filename, img_buffer.read())
            
            # 添加对比图
            template_comparison = result.get('template_comparison')
            if template_comparison:
                comparisons = template_comparison.get('comparisons', [])
                
                phase_names = {
                    'zh-CN': {
                        'preparation': '准备阶段',
                        'lifting': '上升阶段',
                        'release': '出手阶段',
                        'follow_through': '跟随阶段'
                    },
                    'en-US': {
                        'preparation': 'Preparation',
                        'lifting': 'Lifting',
                        'release': 'Release',
                        'follow_through': 'Follow Through'
                    }
                }
                
                for comp in comparisons:
                    phase = comp.get('phase', '')
                    phase_name = phase_names.get(language, {}).get(phase, phase)
                    
                    user_frame = comp.get('user_frame', {})
                    template_frame = comp.get('template_frame', {})
                    
                    user_image_url = user_frame.get('image_url', '')
                    template_image_url = template_frame.get('image_url', '')
                    
                    comparison_img = self._create_comparison_image(
                        user_image_url,
                        template_image_url,
                        phase_name,
                        language
                    )
                    
                    if comparison_img:
                        img_buffer = io.BytesIO()
                        comparison_img.save(img_buffer, format='JPEG', quality=95)
                        img_buffer.seek(0)
                        
                        zip_filename = f"comparisons/{phase}_comparison.jpg"
                        zipf.writestr(zip_filename, img_buffer.read())
        
        return zip_path
