"""
Image Export Service
导出分析结果为图片 - NBA技术分析风格
"""

import io
import math
import zipfile
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from PIL import Image as PILImage, ImageDraw, ImageFont, ImageFilter
import numpy as np
from datetime import datetime

from ..config import settings


# NBA Design System Constants
NBA_COLORS = {
    'bg_primary': (10, 14, 26),
    'bg_secondary': (15, 22, 40),
    'bg_tertiary': (21, 29, 53),
    'accent_electric': (0, 212, 255),
    'accent_green': (0, 255, 135),
    'accent_orange': (255, 140, 66),
    'accent_red': (255, 59, 92),
    'accent_pink': (236, 72, 153),
    'text_primary': (240, 240, 240),
    'text_secondary': (136, 146, 176),
    'text_dim': (74, 85, 120),
}

PHASE_NAMES = {
    'zh-CN': {
        'sync_frame_1': '沉球点',
        'sync_frame_2': '手上升点',
        'knee_min_frame': '最低蹲点',
        'elbow_min_frame': '最紧折叠点',
        'max_hold_frame': '最高持球点',
        'wrist_peak_frame': '手腕最高点',
        'release_frame': '出手点',
        'follow_through_frame': '跟随定型点',
        # 旧版阶段名（兼容）
        'preparation': '准备阶段',
        'lifting': '上升阶段',
        'release': '出手阶段',
        'follow_through': '跟随阶段',
    },
    'en-US': {
        'sync_frame_1': 'Dip Point',
        'sync_frame_2': 'Hand Rise',
        'knee_min_frame': 'Deep Squat',
        'elbow_min_frame': 'Elbow Tuck',
        'max_hold_frame': 'Max Hold',
        'wrist_peak_frame': 'Wrist Peak',
        'release_frame': 'Release',
        'follow_through_frame': 'Follow-thru',
        # 旧版阶段名（兼容）
        'preparation': 'Preparation',
        'lifting': 'Lifting',
        'release': 'Release',
        'follow_through': 'Follow Through',
    }
}

# 角度标签映射
ANGLE_LABELS = {
    'zh-CN': {
        'knee_angle': '膝盖',
        'elbow_angle': '肘部',
        'shoulder_angle': '肩部',
        'trunk_angle': '躯干',
        'wrist_angle': '手腕',
        'hip_angle': '髋部',
    },
    'en-US': {
        'knee_angle': 'Knee',
        'elbow_angle': 'Elbow',
        'shoulder_angle': 'Shoulder',
        'trunk_angle': 'Trunk',
        'wrist_angle': 'Wrist',
        'hip_angle': 'Hip',
    }
}

# 阶段排列顺序（与前端 KEYFRAME_DISPLAY_ORDER 一致）
PHASE_ORDER_NEW = [
    'knee_min_frame', 'sync_frame_1', 'elbow_min_frame', 'sync_frame_2',
    'wrist_peak_frame', 'max_hold_frame', 'release_frame', 'follow_through_frame'
]
PHASE_ORDER_OLD = ['preparation', 'lifting', 'release', 'follow_through']


class ImageExportService:
    """图片导出服务 - NBA技术分析风格"""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 字体配置
        self.font_display = self._load_font(72)
        self.font_h1 = self._load_font(42)
        self.font_h2 = self._load_font(32)
        self.font_h3 = self._load_font(24)
        self.font_metric = self._load_font(28)
        self.font_body = self._load_font(20)
        self.font_small = self._load_font(18)
        self.font_caption = self._load_font(16)

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
        """加载图片（支持本地路径和远程URL）"""
        try:
            # 远程 URL：通过 HTTP 下载
            if image_path.startswith('http://') or image_path.startswith('https://'):
                import urllib.request
                resp = urllib.request.urlopen(image_path, timeout=10)
                img_buffer = io.BytesIO(resp.read())
                return PILImage.open(img_buffer)

            # 本地路径
            if image_path.startswith('/template_images/'):
                relative_path = image_path.replace('/template_images/', '', 1)
                full_path = settings.templates_dir / relative_path
            elif image_path.startswith('/results/'):
                relative_path = image_path[1:]
                full_path = self.output_dir.parent / relative_path
            elif image_path.startswith('/'):
                full_path = Path(image_path)
            elif image_path.startswith('results/'):
                full_path = self.output_dir / image_path
            elif image_path.startswith('templates/'):
                full_path = self.output_dir.parent / image_path
            else:
                full_path = self.output_dir / image_path

            if full_path.exists():
                return PILImage.open(full_path)
            else:
                print(f"图片不存在: {full_path}")
                return None
        except Exception as e:
            print(f"加载图片失败 {image_path}: {e}")
            return None

    # ===== NBA 风格辅助绘制方法 =====

    def _create_gradient_bg(self, width: int, height: int,
                            start_color: tuple, end_color: tuple) -> PILImage.Image:
        """用 numpy 快速生成垂直渐变背景"""
        arr = np.zeros((height, width, 3), dtype=np.uint8)
        for i in range(3):
            arr[:, :, i] = np.linspace(start_color[i], end_color[i], height).astype(np.uint8)[:, np.newaxis]
        return PILImage.fromarray(arr)

    def _draw_angular_rect(self, draw: ImageDraw.Draw, bbox: tuple,
                           fill: tuple, chamfer: int = 8):
        """绘制切角矩形（8个顶点的多边形）"""
        x0, y0, x1, y1 = bbox
        c = chamfer
        points = [
            (x0 + c, y0), (x1 - c, y0), (x1, y0 + c),
            (x1, y1 - c), (x1 - c, y1), (x0 + c, y1),
            (x0, y1 - c), (x0, y0 + c),
        ]
        draw.polygon(points, fill=fill)

    def _draw_angular_rect_outline(self, draw: ImageDraw.Draw, bbox: tuple,
                                   outline: tuple, chamfer: int = 8, width: int = 1):
        """绘制切角矩形边框"""
        x0, y0, x1, y1 = bbox
        c = chamfer
        points = [
            (x0 + c, y0), (x1 - c, y0), (x1, y0 + c),
            (x1, y1 - c), (x1 - c, y1), (x0 + c, y1),
            (x0, y1 - c), (x0, y0 + c),
        ]
        draw.polygon(points, outline=outline, width=width)

    def _draw_glow_line(self, card: PILImage.Image, y: int, x0: int, x1: int,
                        color: tuple, width: int = 2):
        """绘制带两端渐隐的发光水平线"""
        glow_layer = PILImage.new('RGBA', (x1 - x0, 20), (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow_layer)

        # 主线
        glow_draw.line([(0, 10), (x1 - x0, 10)], fill=(*color, 255), width=width)

        # 两端渐隐：左端和右端各覆盖一个渐变遮罩
        fade_len = 60
        for i in range(fade_len):
            alpha = int(255 * (i / fade_len))
            # 左端
            glow_draw.line([(i, 10 - width // 2), (i, 10 + width // 2)],
                          fill=(*color, alpha), width=1)
            # 右端
            rx = (x1 - x0) - 1 - i
            glow_draw.line([(rx, 10 - width // 2), (rx, 10 + width // 2)],
                          fill=(*color, alpha), width=1)

        # 发光模糊
        glow_blurred = glow_layer.filter(ImageFilter.GaussianBlur(radius=3))
        card.paste(glow_blurred, (x0, y - 10), glow_blurred)

    def _draw_severity_badge(self, draw: ImageDraw.Draw, pos: tuple,
                             severity: str, language: str = 'zh-CN'):
        """绘制严重度标签"""
        severity_colors = {
            'none': NBA_COLORS['accent_green'],
            'minor': NBA_COLORS['accent_electric'],
            'moderate': NBA_COLORS['accent_orange'],
            'severe': NBA_COLORS['accent_red'],
        }
        severity_texts = {
            'zh-CN': {'none': '正常', 'minor': '轻微', 'moderate': '中等', 'severe': '严重'},
            'en-US': {'none': 'OK', 'minor': 'Minor', 'moderate': 'Moderate', 'severe': 'Severe'},
        }
        color = severity_colors.get(severity, NBA_COLORS['text_dim'])
        text = severity_texts.get(language, {}).get(severity, severity)

        x, y = pos
        badge_w = max(60, len(text) * 14 + 20)
        badge_h = 28
        self._draw_angular_rect(draw, (x, y, x + badge_w, y + badge_h),
                               color, chamfer=4)
        draw.text((x + badge_w // 2, y + badge_h // 2), text,
                 fill=(255, 255, 255), font=self.font_caption, anchor="mm")

    def _draw_angle_cell(self, card: PILImage.Image, bbox: tuple,
                         label: str, value: Optional[float], color: tuple = None):
        """绘制单个角度指标格子"""
        x0, y0, x1, y1 = bbox
        draw = ImageDraw.Draw(card)

        cell_w = x1 - x0
        cell_h = y1 - y0

        # 背景
        self._draw_angular_rect(draw, bbox, NBA_COLORS['bg_tertiary'], chamfer=4)

        # 左侧色条
        bar_color = color or NBA_COLORS['accent_electric']
        draw.rectangle([(x0 + 2, y0 + 4), (x0 + 4, y1 - 4)], fill=bar_color)

        # 标签 — 顶部
        draw.text((x0 + 14, y0 + 8), label,
                 fill=NBA_COLORS['text_dim'], font=self.font_caption)

        # 数值 — 底部，用大字体
        if value is not None:
            val_text = f"{int(round(value))}°"
            draw.text((x0 + 14, y1 - 6), val_text,
                     fill=bar_color, font=self.font_metric, anchor="lb")

    def _compute_score(self, coordination_issues: list) -> Tuple[int, str]:
        """从 coordination_issues 计算分数和评级"""
        score = 100
        severity_deductions = {'severe': 25, 'moderate': 15, 'minor': 5, 'none': 0}
        for issue in coordination_issues:
            if issue.get('detected', False):
                severity = issue.get('severity', 'none')
                score -= severity_deductions.get(severity, 0)
        score = max(0, min(100, score))

        if score >= 90:
            rating = 'excellent'
        elif score >= 75:
            rating = 'good'
        elif score >= 60:
            rating = 'fair'
        else:
            rating = 'needs_improvement'

        return score, rating

    def _wrap_text(self, draw: ImageDraw.Draw, text: str, font,
                   max_width: int) -> List[str]:
        """PIL 文字自动换行"""
        if not text:
            return []
        lines = []
        current = ""
        for char in text:
            test = current + char
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] > max_width:
                if current:
                    lines.append(current)
                current = char
            else:
                current = test
        if current:
            lines.append(current)
        return lines

    def _get_phase_order(self, key_frames: list) -> list:
        """根据关键帧数据判断使用哪组阶段名称"""
        phases = [kf.get('phase', '') for kf in key_frames]
        if any(p in PHASE_ORDER_NEW for p in phases):
            return PHASE_ORDER_NEW
        return PHASE_ORDER_OLD

    # ===== 主要导出方法 =====

    def _render_styled_keyframe_card(
        self,
        phase: str,
        image_url: str,
        angles: Optional[dict],
        language: str = 'zh-CN',
        card_width: int = 900,
        img_width: int = 680,
    ) -> Optional[PILImage.Image]:
        """渲染单个带样式的关键帧卡片"""
        # 加载图片
        img = self._load_image(image_url)
        if not img:
            return None

        # 计算缩放后的图片高度
        aspect_ratio = img.height / img.width
        img_height = int(img_width * aspect_ratio)
        img_resized = img.resize((img_width, img_height), PILImage.LANCZOS)
        if img_resized.mode == 'RGBA':
            img_resized = img_resized.convert('RGB')

        # 布局尺寸
        padding = 40
        header_h = 60
        angle_grid_h = 110 if angles else 0
        footer_h = 40
        card_h = padding + header_h + 20 + img_height + 20 + angle_grid_h + footer_h + padding

        # 创建画布
        card = self._create_gradient_bg(card_width, card_h,
                                        NBA_COLORS['bg_primary'], NBA_COLORS['bg_secondary'])
        draw = ImageDraw.Draw(card)

        # 头部条
        header_y = padding
        self._draw_angular_rect(
            draw, (padding, header_y, card_width - padding, header_y + header_h),
            fill=NBA_COLORS['bg_tertiary'], chamfer=6
        )
        # 阶段名
        phase_name = PHASE_NAMES.get(language, {}).get(phase, phase)
        draw.text((padding + 20, header_y + header_h // 2), phase_name,
                 fill=NBA_COLORS['accent_electric'], font=self.font_h2, anchor="lm")

        # 右侧小标识
        draw.text((card_width - padding - 20, header_y + header_h // 2), "KEY FRAME",
                 fill=NBA_COLORS['text_dim'], font=self.font_caption, anchor="rm")

        # 图片边框 + 图片
        img_x = (card_width - img_width) // 2
        img_y = header_y + header_h + 20

        # 图片外框
        border_pad = 2
        self._draw_angular_rect(
            draw,
            (img_x - border_pad, img_y - border_pad,
             img_x + img_width + border_pad, img_y + img_height + border_pad),
            fill=NBA_COLORS['bg_secondary'], chamfer=4
        )
        self._draw_angular_rect_outline(
            draw,
            (img_x - border_pad, img_y - border_pad,
             img_x + img_width + border_pad, img_y + img_height + border_pad),
            outline=(*NBA_COLORS['accent_electric'],), chamfer=4, width=1
        )

        # 底部强调线
        draw.rectangle(
            [(img_x, img_y + img_height + border_pad),
             (img_x + img_width, img_y + img_height + border_pad + 3)],
            fill=NBA_COLORS['accent_electric']
        )

        # 贴图
        card.paste(img_resized, (img_x, img_y))

        # 角度网格
        if angles:
            angle_y = img_y + img_height + 20
            labels = ANGLE_LABELS.get(language, ANGLE_LABELS['en-US'])
            valid_angles = [(k, v) for k, v in angles.items()
                          if v is not None and k in labels]

            cols = min(3, max(1, len(valid_angles)))
            rows = math.ceil(len(valid_angles) / cols) if valid_angles else 1
            min_cell_h = 60  # 最小格子高度：label 18px + value 28px + padding
            cell_h = max(min_cell_h, angle_grid_h // rows)
            cell_w = (card_width - padding * 2) // cols

            for i, (key, val) in enumerate(valid_angles):
                row = i // cols
                col = i % cols
                cx = padding + col * cell_w
                cy = angle_y + row * cell_h
                label = labels.get(key, key)
                self._draw_angle_cell(card, (cx + 4, cy + 2, cx + cell_w - 4, cy + cell_h - 2),
                                     label, val)

        # Footer
        footer_y = card_h - padding - footer_h
        self._draw_glow_line(card, footer_y + footer_h // 2, padding, card_width - padding,
                            NBA_COLORS['accent_electric'], width=1)
        footer_text = "ShotPro Analysis" if language == 'en-US' else "ShotPro 投篮分析"
        draw.text((card_width // 2, footer_y + footer_h - 4), footer_text,
                 fill=NBA_COLORS['text_dim'], font=self.font_caption, anchor="mb")

        return card

    def _create_comparison_image(
        self,
        user_image_path: str,
        template_image_path: str,
        phase_name: str,
        language: str = 'zh-CN',
        angle_differences: Optional[dict] = None,
    ) -> Optional[PILImage.Image]:
        """创建 NBA 风格对比图片"""
        user_img = self._load_image(user_image_path)
        template_img = self._load_image(template_image_path)

        if not user_img or not template_img:
            return None

        # 每张图片600px宽
        img_w = 600
        user_aspect = user_img.height / user_img.width
        template_aspect = template_img.height / template_img.width
        max_aspect = max(user_aspect, template_aspect)
        img_h = int(img_w * max_aspect)

        user_resized = user_img.resize((img_w, int(img_w * user_aspect)), PILImage.LANCZOS)
        template_resized = template_img.resize((img_w, int(img_w * template_aspect)), PILImage.LANCZOS)
        if user_resized.mode == 'RGBA':
            user_resized = user_resized.convert('RGB')
        if template_resized.mode == 'RGBA':
            template_resized.convert('RGB')

        # 布局
        padding = 40
        header_h = 60
        gap = 40
        diff_h = 80 if angle_differences else 0
        footer_h = 40
        total_w = padding * 2 + img_w * 2 + gap
        total_h = padding + header_h + 20 + img_h + 30 + diff_h + footer_h + padding

        # 创建画布
        card = self._create_gradient_bg(total_w, total_h,
                                        NBA_COLORS['bg_primary'], NBA_COLORS['bg_secondary'])
        draw = ImageDraw.Draw(card)

        # 头部
        header_y = padding
        self._draw_angular_rect(
            draw, (padding, header_y, total_w - padding, header_y + header_h),
            fill=NBA_COLORS['bg_tertiary'], chamfer=6
        )
        draw.text((padding + 20, header_y + header_h // 2), phase_name,
                 fill=NBA_COLORS['accent_electric'], font=self.font_h2, anchor="lm")
        comparison_label = "对比分析" if language == 'zh-CN' else "COMPARISON"
        draw.text((total_w - padding - 20, header_y + header_h // 2), comparison_label,
                 fill=NBA_COLORS['text_dim'], font=self.font_caption, anchor="rm")

        # 用户图片（左）—— 橙色边框
        user_x = padding
        img_y = header_y + header_h + 20
        user_label = "你的动作" if language == 'zh-CN' else "YOUR FORM"
        user_img_y = img_y + 24
        user_paste_y = user_img_y + (img_h - int(img_w * user_aspect)) // 2

        # 用户标签
        draw.text((user_x + img_w // 2, img_y + 10), user_label,
                 fill=NBA_COLORS['accent_orange'], font=self.font_small, anchor="mt")

        # 用户图片边框
        self._draw_angular_rect_outline(
            draw,
            (user_x - 2, user_paste_y - 2, user_x + img_w + 2, user_paste_y + int(img_w * user_aspect) + 2),
            outline=NBA_COLORS['accent_orange'], chamfer=4, width=2
        )
        card.paste(user_resized, (user_x, user_paste_y))

        # 中央分隔线
        center_x = padding + img_w + gap // 2
        draw.line([(center_x, img_y), (center_x, img_y + img_h + 30)],
                 fill=(*NBA_COLORS['accent_electric'], ), width=1)

        # 模板图片（右）—— 蓝色边框
        template_x = padding + img_w + gap
        template_label = "参考模板" if language == 'zh-CN' else "REFERENCE"
        template_paste_y = img_y + 24 + (img_h - int(img_w * template_aspect)) // 2

        # 模板标签
        draw.text((template_x + img_w // 2, img_y + 10), template_label,
                 fill=NBA_COLORS['accent_electric'], font=self.font_small, anchor="mt")

        # 模板图片边框
        self._draw_angular_rect_outline(
            draw,
            (template_x - 2, template_paste_y - 2,
             template_x + img_w + 2, template_paste_y + int(img_w * template_aspect) + 2),
            outline=NBA_COLORS['accent_electric'], chamfer=4, width=2
        )
        card.paste(template_resized, (template_x, template_paste_y))

        # 角度差异行
        if angle_differences:
            diff_y = img_y + img_h + 30
            labels = ANGLE_LABELS.get(language, ANGLE_LABELS['en-US'])
            valid_diffs = [(k, v) for k, v in angle_differences.items()
                          if v is not None and k in labels]
            if valid_diffs:
                diff_label = "角度差异" if language == 'zh-CN' else "ANGLE DIFF"
                draw.text((padding, diff_y + 4), diff_label,
                         fill=NBA_COLORS['text_dim'], font=self.font_caption)
                cell_w = (total_w - padding * 2 - 100) // max(1, len(valid_diffs))
                for i, (key, diff) in enumerate(valid_diffs):
                    cx = padding + 100 + i * cell_w
                    label = labels.get(key, key)
                    if abs(diff) <= 5:
                        color = NBA_COLORS['accent_green']
                    elif abs(diff) <= 10:
                        color = NBA_COLORS['accent_orange']
                    else:
                        color = NBA_COLORS['accent_red']
                    draw.text((cx, diff_y + 2), label,
                             fill=NBA_COLORS['text_dim'], font=self.font_caption)
                    draw.text((cx, diff_y + 22), f"{'+' if diff >= 0 else ''}{int(round(diff))}°",
                             fill=color, font=self.font_metric)

        # Footer
        footer_y = total_h - padding - footer_h
        self._draw_glow_line(card, footer_y + footer_h // 2, padding, total_w - padding,
                            NBA_COLORS['accent_electric'], width=1)

        return card

    def export_key_frames(self, task_id: str, result: Dict,
                          language: str = 'zh-CN') -> Optional[Path]:
        """导出关键帧图片（样式化卡片）"""
        key_frames = result.get('key_frames', [])
        if not key_frames:
            return None

        zip_path = self.output_dir / f"{task_id}_keyframes.zip"

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for kf in key_frames:
                phase = kf.get('phase', 'unknown')
                image_url = kf.get('image_url', '')
                angles = kf.get('angles')

                card = self._render_styled_keyframe_card(
                    phase, image_url, angles, language
                )
                if card:
                    img_buffer = io.BytesIO()
                    card.save(img_buffer, format='PNG')
                    img_buffer.seek(0)
                    zipf.writestr(f"{phase}.png", img_buffer.read())

        return zip_path

    def export_comparison_images(self, task_id: str, result: Dict,
                                 language: str = 'zh-CN') -> Optional[Path]:
        """导出对比图片（NBA风格）"""
        template_comparison = result.get('template_comparison')
        if not template_comparison:
            return None

        comparisons = template_comparison.get('comparisons', [])
        if not comparisons:
            return None

        zip_path = self.output_dir / f"{task_id}_comparisons.zip"

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for comp in comparisons:
                phase = comp.get('phase', '')
                phase_name = PHASE_NAMES.get(language, {}).get(phase, phase)

                user_frame = comp.get('user_frame', {})
                template_frame = comp.get('template_frame', {})

                user_image_url = user_frame.get('image_url', '')
                template_image_url = template_frame.get('image_url', '')
                angle_differences = comp.get('angle_differences')

                comparison_img = self._create_comparison_image(
                    user_image_url,
                    template_image_url,
                    phase_name,
                    language,
                    angle_differences,
                )

                if comparison_img:
                    img_buffer = io.BytesIO()
                    comparison_img.save(img_buffer, format='PNG')
                    img_buffer.seek(0)
                    zipf.writestr(f"{phase}_comparison.png", img_buffer.read())

        return zip_path

    def export_all_images(self, task_id: str, result: Dict,
                          language: str = 'zh-CN') -> Optional[Path]:
        """导出所有图片（关键帧 + 对比图）"""
        zip_path = self.output_dir / f"{task_id}_all_images.zip"

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 关键帧
            key_frames = result.get('key_frames', [])
            for kf in key_frames:
                phase = kf.get('phase', 'unknown')
                image_url = kf.get('image_url', '')
                angles = kf.get('angles')

                card = self._render_styled_keyframe_card(
                    phase, image_url, angles, language
                )
                if card:
                    img_buffer = io.BytesIO()
                    card.save(img_buffer, format='PNG')
                    img_buffer.seek(0)
                    zipf.writestr(f"keyframes/{phase}.png", img_buffer.read())

            # 对比图
            template_comparison = result.get('template_comparison')
            if template_comparison:
                comparisons = template_comparison.get('comparisons', [])
                for comp in comparisons:
                    phase = comp.get('phase', '')
                    phase_name = PHASE_NAMES.get(language, {}).get(phase, phase)

                    user_frame = comp.get('user_frame', {})
                    template_frame = comp.get('template_frame', {})

                    comparison_img = self._create_comparison_image(
                        user_frame.get('image_url', ''),
                        template_frame.get('image_url', ''),
                        phase_name,
                        language,
                        comp.get('angle_differences'),
                    )

                    if comparison_img:
                        img_buffer = io.BytesIO()
                        comparison_img.save(img_buffer, format='PNG')
                        img_buffer.seek(0)
                        zipf.writestr(f"comparisons/{phase}_comparison.png", img_buffer.read())

        return zip_path

    def export_share_card(
        self,
        task_id: str,
        result: Dict,
        language: str = 'zh-CN'
    ) -> Optional[Path]:
        """导出分享卡片 - NBA技术分析风格长图"""
        try:
            card_width = 1800
            padding = 60
            section_gap = 40
            img_width = 680  # 关键帧图片宽度，足够大以看清骨骼标注

            # 获取数据
            coordination_issues = result.get('coordination_issues', [])
            key_frames = result.get('key_frames', [])
            template_comparison = result.get('template_comparison')
            video_filename = result.get('video_filename', 'unknown')

            # 计算评分（新格式不再有 overall_score）
            overall_score = result.get('overall_score')
            rating = result.get('rating')
            if overall_score is None:
                overall_score, rating = self._compute_score(coordination_issues)

            # 评级颜色和文字
            rating_colors = {
                'excellent': NBA_COLORS['accent_green'],
                'good': (102, 187, 106),
                'fair': NBA_COLORS['accent_orange'],
                'needs_improvement': NBA_COLORS['accent_red'],
            }
            rating_texts = {
                'zh-CN': {
                    'excellent': '优秀', 'good': '良好',
                    'fair': '一般', 'needs_improvement': '需改进'
                },
                'en-US': {
                    'excellent': 'Excellent', 'good': 'Good',
                    'fair': 'Fair', 'needs_improvement': 'Needs Work'
                },
            }
            rating_color = rating_colors.get(rating, NBA_COLORS['text_dim'])
            rating_text = rating_texts.get(language, {}).get(rating, str(rating))

            # 确定阶段顺序
            phase_order = self._get_phase_order(key_frames)

            # 加载所有关键帧图片并计算高度
            frame_data = {}  # phase -> (resized_img, width, height, angles)
            max_img_height = 0
            for kf in key_frames:
                phase = kf.get('phase', '')
                image_url = kf.get('image_url', '')
                img = self._load_image(image_url)
                if img:
                    aspect = img.height / img.width
                    h = int(img_width * aspect)
                    resized = img.resize((img_width, h), PILImage.LANCZOS)
                    if resized.mode == 'RGBA':
                        resized = resized.convert('RGB')
                    frame_data[phase] = (resized, img_width, h, kf.get('angles'))
                    max_img_height = max(max_img_height, h)

            # 加载模板对比图片
            template_data = {}
            if template_comparison:
                for comp in template_comparison.get('comparisons', []):
                    phase = comp.get('phase', '')
                    tf = comp.get('template_frame', {})
                    if tf:
                        timg = self._load_image(tf.get('image_url', ''))
                        if timg:
                            t_aspect = timg.height / timg.width
                            # 对比模式下每张图片600px
                            t_w = 600
                            t_h = int(t_w * t_aspect)
                            t_resized = timg.resize((t_w, t_h), PILImage.LANCZOS)
                            if t_resized.mode == 'RGBA':
                                t_resized = t_resized.convert('RGB')
                            template_data[phase] = (t_resized, t_w, t_h)

            max_img_height = max(max_img_height, 400)

            # ===== 计算总高度 =====
            header_h = 340
            timeline_h = 80
            angle_grid_h = 120
            phase_header_h = 60
            # 实际角度网格高度取决于角度数量（最多5个：3列2行）
            max_angle_count = 5  # knee, elbow, shoulder, trunk, wrist
            angle_rows = max(1, math.ceil(max_angle_count / 3))
            actual_angle_grid_h = max(angle_grid_h, angle_rows * 60)
            phase_section_h = phase_header_h + 15 + max_img_height + 15 + actual_angle_grid_h
            coordination_h = 0
            if coordination_issues:
                coordination_h = 80 + len(coordination_issues) * 90 + 20
            footer_h = 80

            total_h = (padding + header_h + section_gap +
                       timeline_h + section_gap +
                       len(phase_order) * (phase_section_h + section_gap) +
                       (coordination_h + section_gap if coordination_h > 0 else 0) +
                       footer_h + padding)

            # ===== 创建主画布 =====
            card = self._create_gradient_bg(
                card_width, total_h,
                NBA_COLORS['bg_primary'], NBA_COLORS['bg_secondary']
            )
            draw = ImageDraw.Draw(card)

            current_y = padding

            # ===== HERO HEADER =====
            # 品牌名
            brand_text = "SHOTPRO"
            draw.text((padding, current_y + 10), brand_text,
                     fill=NBA_COLORS['accent_electric'], font=self.font_h1)

            # 日期
            date_text = datetime.now().strftime('%Y.%m.%d')
            draw.text((card_width - padding, current_y + 20), date_text,
                     fill=NBA_COLORS['text_dim'], font=self.font_caption, anchor="rt")

            # 中央大号分数
            score_str = str(int(overall_score))
            score_x = card_width // 2
            score_y = current_y + 80

            # 分数发光背景
            score_glow = PILImage.new('RGBA', (200, 100), (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(score_glow)
            glow_draw.ellipse([(0, 0), (200, 100)], fill=(*NBA_COLORS['accent_electric'], 30))
            glow_blurred = score_glow.filter(ImageFilter.GaussianBlur(radius=30))
            card.paste(glow_blurred, (score_x - 100, score_y - 10), glow_blurred)

            draw.text((score_x, score_y), score_str,
                     fill=NBA_COLORS['text_primary'], font=self.font_display, anchor="mt")
            draw.text((score_x, score_y + 80), "/ 100",
                     fill=NBA_COLORS['text_secondary'], font=self.font_h3, anchor="mt")

            # 评级标签
            pill_w = 180
            pill_h = 42
            pill_x = score_x - pill_w // 2
            pill_y = score_y + 120
            self._draw_angular_rect(draw, (pill_x, pill_y, pill_x + pill_w, pill_y + pill_h),
                                   rating_color, chamfer=6)
            draw.text((score_x, pill_y + pill_h // 2), rating_text,
                     fill=(255, 255, 255), font=self.font_h3, anchor="mm")

            # 视频文件名
            draw.text((card_width // 2, current_y + header_h - 20), video_filename,
                     fill=NBA_COLORS['text_secondary'], font=self.font_small, anchor="mb")

            # 底部分隔发光线
            self._draw_glow_line(card, current_y + header_h - 5,
                                padding, card_width - padding,
                                NBA_COLORS['accent_electric'], width=2)

            current_y += header_h + section_gap

            # ===== 阶段时间轴 =====
            timeline_y = current_y
            timeline_bar_y = timeline_y + 35
            node_radius = 8

            # 连接线
            line_x0 = padding + 100
            line_x1 = card_width - padding - 100
            draw.line([(line_x0, timeline_bar_y), (line_x1, timeline_bar_y)],
                     fill=NBA_COLORS['text_dim'], width=2)

            for i, phase in enumerate(phase_order):
                phase_name = PHASE_NAMES.get(language, {}).get(phase, phase)
                nx = line_x0 + i * (line_x1 - line_x0) // (len(phase_order) - 1) if len(phase_order) > 1 else card_width // 2

                # 菱形节点
                diamond_size = node_radius
                diamond_points = [
                    (nx, timeline_bar_y - diamond_size),
                    (nx + diamond_size, timeline_bar_y),
                    (nx, timeline_bar_y + diamond_size),
                    (nx - diamond_size, timeline_bar_y),
                ]
                color = NBA_COLORS['accent_electric'] if phase in frame_data else NBA_COLORS['text_dim']
                draw.polygon(diamond_points, fill=color)

                # 阶段名
                draw.text((nx, timeline_bar_y + 20), phase_name,
                         fill=color, font=self.font_small, anchor="mt")

            current_y += timeline_h + section_gap

            # ===== 关键帧详情区 =====
            for phase_idx, phase in enumerate(phase_order):
                phase_name = PHASE_NAMES.get(language, {}).get(phase, phase)

                # 阶段头部条
                self._draw_angular_rect(
                    draw,
                    (padding, current_y, card_width - padding, current_y + phase_header_h),
                    fill=NBA_COLORS['bg_tertiary'], chamfer=6
                )
                # 左侧色条
                draw.rectangle([(padding, current_y + 4), (padding + 5, current_y + phase_header_h - 4)],
                              fill=NBA_COLORS['accent_electric'])
                draw.text((padding + 20, current_y + phase_header_h // 2), phase_name,
                         fill=NBA_COLORS['accent_electric'], font=self.font_h2, anchor="lm")

                # 检测这个阶段是否有问题
                phase_issue = None
                for issue in coordination_issues:
                    if issue.get('detected', False):
                        phase_issue = issue
                        break
                if phase_issue:
                    severity = phase_issue.get('severity', 'none')
                    self._draw_severity_badge(draw,
                        (card_width - padding - 100, current_y + phase_header_h // 2 - 14),
                        severity, language)

                current_y += phase_header_h + 15

                # 图片区域
                data = frame_data.get(phase)
                has_template = phase in template_data

                if has_template and data:
                    # 并排对比模式
                    t_data = template_data[phase]
                    t_w, t_h = t_data[1], t_data[2]
                    user_img, u_w, u_h = data[0], data[1], data[2]

                    gap = 40
                    total_img_w = img_width + gap + t_w
                    user_x = (card_width - total_img_w) // 2
                    template_x = user_x + img_width + gap

                    # 用户图标签
                    user_label = "你的动作" if language == 'zh-CN' else "YOUR FORM"
                    draw.text((user_x + img_width // 2, current_y), user_label,
                             fill=NBA_COLORS['accent_orange'], font=self.font_small, anchor="mt")

                    # 用户图边框
                    u_paste_y = current_y + 24 + max(0, (max_img_height - u_h) // 2)
                    self._draw_angular_rect_outline(
                        draw,
                        (user_x - 2, u_paste_y - 2, user_x + u_w + 2, u_paste_y + u_h + 2),
                        outline=NBA_COLORS['accent_orange'], chamfer=4, width=2
                    )
                    card.paste(user_img, (user_x, u_paste_y))

                    # 模板图标签
                    template_label = "参考模板" if language == 'zh-CN' else "REFERENCE"
                    t_paste_y = current_y + 24 + max(0, (max_img_height - t_h) // 2)
                    draw.text((template_x + t_w // 2, current_y), template_label,
                             fill=NBA_COLORS['accent_electric'], font=self.font_small, anchor="mt")

                    # 模板图边框
                    self._draw_angular_rect_outline(
                        draw,
                        (template_x - 2, t_paste_y - 2, template_x + t_w + 2, t_paste_y + t_h + 2),
                        outline=NBA_COLORS['accent_electric'], chamfer=4, width=2
                    )
                    card.paste(t_data[0], (template_x, t_paste_y))

                elif data:
                    # 单图模式
                    img_x = (card_width - img_width) // 2
                    resized_img = data[0]
                    h = data[2]

                    # 边框
                    self._draw_angular_rect_outline(
                        draw,
                        (img_x - 2, current_y - 2, img_x + img_width + 2, current_y + h + 2),
                        outline=NBA_COLORS['accent_electric'], chamfer=4, width=1
                    )
                    # 底部强调线
                    draw.rectangle(
                        [(img_x, current_y + h + 2), (img_x + img_width, current_y + h + 5)],
                        fill=NBA_COLORS['accent_electric']
                    )
                    card.paste(resized_img, (img_x, current_y))

                current_y += max_img_height + 15

                # 角度数据网格
                angles = data[3] if data else None
                if angles:
                    labels = ANGLE_LABELS.get(language, ANGLE_LABELS['en-US'])
                    valid_angles = [(k, v) for k, v in angles.items()
                                  if v is not None and k in labels]
                    cols = min(3, max(1, len(valid_angles)))
                    rows = max(1, math.ceil(len(valid_angles) / cols))
                    cell_w = (card_width - padding * 2) // cols
                    min_cell_h = 60
                    cell_h = max(min_cell_h, angle_grid_h // rows)
                    for i, (key, val) in enumerate(valid_angles):
                        col = i % cols
                        row = i // cols
                        cx = padding + col * cell_w
                        cy = current_y + row * cell_h
                        label = labels.get(key, key)
                        self._draw_angle_cell(card, (cx + 4, cy + 2, cx + cell_w - 4, cy + cell_h - 2),
                                             label, val)

                current_y += angle_grid_h + section_gap

            # ===== 发力连贯性面板 =====
            if coordination_issues:
                coord_header = "发力连贯性检测" if language == 'zh-CN' else "COORDINATION ANALYSIS"
                self._draw_angular_rect(
                    draw,
                    (padding, current_y, card_width - padding, current_y + 60),
                    fill=NBA_COLORS['bg_tertiary'], chamfer=6
                )
                draw.rectangle([(padding, current_y + 4), (padding + 5, current_y + 56)],
                              fill=NBA_COLORS['accent_electric'])
                draw.text((padding + 20, current_y + 30), coord_header,
                         fill=NBA_COLORS['accent_electric'], font=self.font_h2, anchor="lm")
                current_y += 70

                for issue in coordination_issues:
                    severity = issue.get('severity', 'none')
                    description = issue.get('description', '') if language == 'zh-CN' else issue.get('description_en', '')
                    suggestion = issue.get('suggestion', '') if language == 'zh-CN' else issue.get('suggestion_en', '')

                    # 问题条
                    issue_h = 70
                    self._draw_angular_rect(
                        draw,
                        (padding + 20, current_y, card_width - padding - 20, current_y + issue_h),
                        fill=NBA_COLORS['bg_secondary'], chamfer=4
                    )

                    # 严重度色条
                    sev_colors = {
                        'none': NBA_COLORS['accent_green'],
                        'minor': NBA_COLORS['accent_electric'],
                        'moderate': NBA_COLORS['accent_orange'],
                        'severe': NBA_COLORS['accent_red'],
                    }
                    bar_color = sev_colors.get(severity, NBA_COLORS['text_dim'])
                    draw.rectangle([(padding + 20, current_y + 4), (padding + 24, current_y + issue_h - 4)],
                                  fill=bar_color)

                    # 严重度标签
                    self._draw_severity_badge(draw, (padding + 35, current_y + 8), severity, language)

                    # 计算标签实际宽度，动态定位描述文字避免遮挡
                    sev_labels = {
                        'zh-CN': {'none': '正常', 'minor': '轻微', 'moderate': '中等', 'severe': '严重'},
                        'en-US': {'none': 'OK', 'minor': 'Minor', 'moderate': 'Moderate', 'severe': 'Severe'},
                    }
                    sev_text = sev_labels.get(language, {}).get(severity, severity)
                    badge_w = max(60, len(sev_text) * 14 + 20)
                    desc_x = padding + 35 + badge_w + 15

                    # 描述
                    if description:
                        desc_lines = self._wrap_text(draw, description, self.font_small,
                                                    card_width - padding - 20 - desc_x)
                        for li, line in enumerate(desc_lines[:2]):
                            draw.text((desc_x, current_y + 10 + li * 22), line,
                                     fill=NBA_COLORS['text_primary'], font=self.font_small)

                    current_y += issue_h + 10

                    # 建议
                    if suggestion:
                        draw.text((padding + 40, current_y), f"→ {suggestion[:60]}",
                                 fill=NBA_COLORS['text_secondary'], font=self.font_caption)
                        current_y += 22

                current_y += section_gap

            # ===== FOOTER =====
            self._draw_glow_line(card, current_y + 20, padding, card_width - padding,
                                NBA_COLORS['accent_electric'], width=1)

            brand = "SHOTPRO" if language == 'en-US' else "SHOTPRO"
            sub = "Basketball Shooting Analysis" if language == 'en-US' else "篮球投篮技术分析"
            draw.text((card_width // 2, current_y + 40), brand,
                     fill=NBA_COLORS['accent_electric'], font=self.font_h3, anchor="mt")
            draw.text((card_width // 2, current_y + 70), f"{sub}  |  {datetime.now().strftime('%Y.%m.%d')}",
                     fill=NBA_COLORS['text_dim'], font=self.font_caption, anchor="mt")

            # 保存
            output_path = self.output_dir / f"{task_id}_share_card.png"
            card.save(output_path, 'PNG')
            print(f"分享卡片已保存: {output_path}")
            return output_path

        except Exception as e:
            print(f"[ERROR] 导出分享卡片失败: {e}")
            import traceback
            traceback.print_exc()
            return None
