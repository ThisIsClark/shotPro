"""
Image Export Service
导出分析结果为图片
"""

import io
import zipfile
from pathlib import Path
from typing import Optional, Dict, List
from PIL import Image as PILImage, ImageDraw, ImageFont, ImageFilter
import cv2
import numpy as np
from datetime import datetime

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

        # 字体配置
        self.font_title = self._load_font(48)
        self.font_subtitle = self._load_font(32)
        self.font_body = self._load_font(24)
        self.font_small = self._load_font(18)
        self.font_score = self._load_font(56)

    def _load_font(self, size: int):
        """加载字体"""
        font_paths = [
            '/System/Library/Fonts/STHeiti Medium.ttc',
            '/System/Library/Fonts/PingFang.ttc',
            '/System/Library/Fonts/Helvetica.ttc',
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        ]
        for path in font_paths:
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
        return ImageFont.load_default()

    def _load_image(self, image_path: str) -> Optional[PILImage.Image]:
        """
        加载图片
        
        Args:
            image_path: 图片路径（可以是相对路径或绝对路径）
            
        Returns:
            PIL Image对象，如果加载失败返回None
        """
        try:
            # 处理路径
            if image_path.startswith('/template_images/'):
                # 模板图片路径
                # /template_images/xxx -> templates/xxx
                relative_path = image_path.replace('/template_images/', '', 1)
                full_path = settings.templates_dir / relative_path
            elif image_path.startswith('/results/'):
                # 结果图片路径
                # /results/xxx -> results/xxx
                relative_path = image_path[1:]  # 去掉开头的 '/'
                full_path = self.output_dir.parent / relative_path
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
            
            
            if full_path.exists():
                img = PILImage.open(full_path)
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

    def export_share_card(
        self,
        task_id: str,
        result: Dict,
        language: str = 'zh-CN'
    ) -> Optional[Path]:
        """
        导出分享卡片图片（适合社交媒体分享的单张长图）

        Args:
            task_id: 任务 ID
            result: 分析结果
            language: 语言

        Returns:
            分享卡片图片路径，如果失败返回 None
        """
        try:
            # 配置
            card_width = 1400  # 增加宽度以容纳更大的图片
            padding = 40
            section_gap = 30

            # 颜色配置
            bg_gradient_start = (26, 31, 58)  # 深蓝背景
            bg_gradient_end = (45, 52, 98)
            accent_color = (72, 219, 251)  # 亮蓝色
            accent_orange = (255, 168, 107)  # 橙色
            accent_pink = (236, 72, 153)  # 粉色
            text_primary = (255, 255, 255)
            text_secondary = (200, 200, 200)

            # 获取数据
            overall_score = result.get('overall_score', 0)
            rating = result.get('rating', 'unknown')
            key_frames = result.get('key_frames', [])
            template_comparison = result.get('template_comparison')
            issues = result.get('issues', [])
            video_filename = result.get('video_filename', 'unknown')

            # 评级颜色和文字
            rating_colors = {
                'excellent': (76, 175, 80),
                'good': (102, 187, 106),
                'fair': (255, 193, 7),
                'needs_improvement': (244, 67, 54)
            }
            rating_texts = {
                'zh-CN': {
                    'excellent': '优秀',
                    'good': '良好',
                    'fair': '一般',
                    'needs_improvement': '需改进'
                },
                'en-US': {
                    'excellent': 'Excellent',
                    'good': 'Good',
                    'fair': 'Fair',
                    'needs_improvement': 'Needs Work'
                }
            }

            rating_color = rating_colors.get(rating, (200, 200, 200))
            rating_text = rating_texts.get(language, {}).get(rating, rating)

            # 阶段名称
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

            # 计算卡片高度 - 根据实际图片尺寸动态计算
            header_height = 220
            tips_height = 180
            footer_height = 60

            # 目标图片宽度（每张图片）
            target_img_width = 280

            # 加载所有图片并计算最大高度
            frame_images = {}
            template_images = {}
            max_img_height = 0

            for kf in key_frames:
                phase = kf.get('phase', '')
                image_url = kf.get('image_url', '')
                img = self._load_image(image_url)
                if img:
                    # 按比例缩放
                    aspect_ratio = img.height / img.width
                    scaled_height = int(target_img_width * aspect_ratio)
                    frame_images[phase] = (img, target_img_width, scaled_height)
                    max_img_height = max(max_img_height, scaled_height)

            if template_comparison:
                for comp in template_comparison.get('comparisons', []):
                    phase = comp.get('phase', '')
                    template_frame = comp.get('template_frame', {})
                    if template_frame:
                        template_img = self._load_image(template_frame.get('image_url', ''))
                        if template_img:
                            aspect_ratio = template_img.height / template_img.width
                            scaled_height = int(target_img_width * aspect_ratio)
                            template_images[phase] = (template_img, target_img_width, scaled_height)
                            max_img_height = max(max_img_height, scaled_height)

            # 确保最小高度
            max_img_height = max(max_img_height, 200)

            # 每行高度 = 图片高度 + 标签和边距
            phase_row_height = max_img_height + 80
            phases_height = phase_row_height * 4

            total_height = header_height + phases_height + tips_height + footer_height + padding * 4 + section_gap * 3

            # 创建主图像
            card = PILImage.new('RGB', (card_width, total_height), bg_gradient_start)
            draw = ImageDraw.Draw(card)

            # 绘制渐变背景（简化版本）
            for y in range(total_height):
                ratio = y / total_height
                r = int(bg_gradient_start[0] + (bg_gradient_end[0] - bg_gradient_start[0]) * ratio)
                g = int(bg_gradient_start[1] + (bg_gradient_end[1] - bg_gradient_start[1]) * ratio)
                b = int(bg_gradient_start[2] + (bg_gradient_end[2] - bg_gradient_start[2]) * ratio)
                # 使用更高效的方式绘制水平线
                for x in range(0, card_width, 10):
                    draw.rectangle([(x, y), (min(x + 10, card_width), y + 1)], fill=(r, g, b))

            current_y = padding
            rect_radius = 24

            # ============= HEADER - 分数部分 =============
            # 直接在 card 上绘制半透明圆角矩形
            header_rect = PILImage.new('RGBA', (card_width - padding * 2, header_height), (0, 0, 0, 0))
            header_draw = ImageDraw.Draw(header_rect)
            header_draw.rounded_rectangle(
                [(0, 0), (card_width - padding * 2, header_height)],
                radius=rect_radius,
                fill=(255, 255, 255, 30)
            )
            card.paste(header_rect, (padding, current_y), header_rect)

            # 绘制分数
            score_x = card_width // 2 - 60
            score_y = current_y + 40
            draw.text((score_x, score_y), str(int(overall_score)), fill=text_primary, font=self.font_score)
            draw.text((score_x + 70, score_y + 35), "/100", fill=text_secondary, font=self.font_body)

            # 评级标签 - 直接在 card 上绘制
            rating_pill_width = 160
            rating_pill_height = 36
            rating_pill_x = card_width // 2 - rating_pill_width // 2
            rating_pill_y = score_y + 75
            draw.rounded_rectangle(
                [(rating_pill_x, rating_pill_y),
                 (rating_pill_x + rating_pill_width, rating_pill_y + rating_pill_height)],
                radius=18,
                fill=rating_color
            )
            draw.text((card_width // 2, rating_pill_y + 6), rating_text, fill=(255, 255, 255), font=self.font_subtitle, anchor="mm")

            # 视频名称
            video_name_y = current_y + header_height - 35
            draw.text((card_width // 2, video_name_y), f"🏀 {video_filename}", fill=text_secondary, font=self.font_small, anchor="mm")
            current_y += header_height + section_gap

            # ============= 四个阶段对比（每行一个阶段） =============
            phases_order = ['preparation', 'lifting', 'release', 'follow_through']

            for idx, phase in enumerate(phases_order):
                phase_name = phase_names.get(language, {}).get(phase, phase)
                phase_y = current_y + idx * (phase_row_height + section_gap)

                # 阶段卡片背景
                phase_card = PILImage.new('RGBA', (card_width - padding * 2, phase_row_height), (0, 0, 0, 0))
                phase_draw = ImageDraw.Draw(phase_card)
                phase_draw.rounded_rectangle(
                    [(0, 0), (card_width - padding * 2, phase_row_height)],
                    radius=rect_radius,
                    fill=(255, 255, 255, 15)
                )
                card.paste(phase_card, (padding, phase_y), phase_card)

                # 阶段名称（左侧）
                draw.text((padding + 20, phase_y + 20), phase_name, fill=accent_color, font=self.font_body)

                # 图片布局：用户图片和模板图片并排（保持原始宽高比）
                user_data = frame_images.get(phase)  # (img, width, height)
                template_data = template_images.get(phase)  # (img, width, height)

                user_x = padding + 180
                template_x = padding + 180 + target_img_width + 30
                img_y = phase_y + 15

                if user_data:
                    user_img, u_width, u_height = user_data
                    user_resized = user_img.resize((u_width, u_height), PILImage.LANCZOS)
                    if user_resized.mode == 'RGBA':
                        user_resized = user_resized.convert('RGB')
                    card.paste(user_resized, (user_x, img_y))
                    draw.text((user_x + u_width // 2, img_y + u_height + 8), "你的动作", fill=accent_orange, font=self.font_small, anchor="mm")

                if template_data:
                    template_img, t_width, t_height = template_data
                    template_resized = template_img.resize((t_width, t_height), PILImage.LANCZOS)
                    if template_resized.mode == 'RGBA':
                        template_resized = template_resized.convert('RGB')
                    card.paste(template_resized, (template_x, img_y))
                    draw.text((template_x + t_width // 2, img_y + t_height + 8), "标准模板", fill=accent_color, font=self.font_small, anchor="mm")

            current_y += phases_height + section_gap

            # ============= 建议部分 =============
            tips_card = PILImage.new('RGBA', (card_width - padding * 2, tips_height), (0, 0, 0, 0))
            tips_draw = ImageDraw.Draw(tips_card)
            tips_draw.rounded_rectangle(
                [(0, 0), (card_width - padding * 2, tips_height)],
                radius=rect_radius,
                fill=(255, 255, 255, 15)
            )
            card.paste(tips_card, (padding, current_y), tips_card)

            tips_title = "💡 改进建议" if language == 'zh-CN' else "💡 Improvement Tips"
            draw.text((card_width // 2, current_y + 18), tips_title, fill=accent_pink, font=self.font_subtitle)

            if issues:
                for i, issue in enumerate(issues[:3]):
                    tip_text = issue.get('suggestion', '') if language == 'zh-CN' else issue.get('suggestion_en', '')
                    if tip_text:
                        if len(tip_text) > 55:
                            tip_text = tip_text[:52] + "..."
                        draw.text((padding + 25, current_y + 65 + i * 32), f"• {tip_text}", fill=text_secondary, font=self.font_small)
            else:
                no_tips_text = "动作很标准，继续保持！" if language == 'zh-CN' else "Great form, keep it up!"
                draw.text((card_width // 2, current_y + 65), no_tips_text, fill=text_secondary, font=self.font_body)

            current_y += tips_height + section_gap

            # ============= Footer =============
            footer_text = f"🏀 Basketball Shooting Analysis | {datetime.now().strftime('%Y.%m.%d')}"
            draw.text((card_width // 2, current_y + 20), footer_text, fill=text_secondary, font=self.font_small)

            # 保存图片（使用 PNG 格式避免压缩损失）
            output_path = self.output_dir / f"{task_id}_share_card.png"
            card_rgb = card.convert('RGB')
            card_rgb.save(output_path, 'PNG')

            print(f"分享卡片已保存：{output_path}")
            return output_path

        except Exception as e:
            print(f"[ERROR] 导出分享卡片失败：{e}")
            import traceback
            traceback.print_exc()
            return None
