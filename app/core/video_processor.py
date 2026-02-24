"""
Video Processor Module
视频处理模块：读取、处理和标注视频
"""

from __future__ import annotations

import cv2
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Generator, Callable
from PIL import Image, ImageDraw, ImageFont

from .pose_detector import PoseDetector, PoseResult


@dataclass
class VideoInfo:
    """视频信息"""
    path: Path
    width: int
    height: int
    fps: float
    total_frames: int
    duration: float  # 秒
    codec: str


@dataclass
class ProcessedFrame:
    """处理后的帧"""
    frame_number: int
    timestamp: float
    original: np.ndarray
    annotated: Optional[np.ndarray] = None
    pose_result: Optional[PoseResult] = None


class VideoProcessor:
    """视频处理器"""
    
    def __init__(self, target_fps: Optional[int] = None):
        """
        初始化视频处理器
        
        Args:
            target_fps: 目标帧率，如果设置则会降采样
        """
        self.target_fps = target_fps
    
    def get_video_info(self, video_path: str | Path) -> VideoInfo:
        """
        获取视频信息
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            VideoInfo 对象
        """
        video_path = Path(video_path)
        
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        try:
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
            
            # 解码 fourcc
            codec = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
            
            duration = total_frames / fps if fps > 0 else 0
            
            return VideoInfo(
                path=video_path,
                width=width,
                height=height,
                fps=fps,
                total_frames=total_frames,
                duration=duration,
                codec=codec
            )
        finally:
            cap.release()
    
    def read_frames(
        self,
        video_path: str | Path,
        start_frame: int = 0,
        end_frame: Optional[int] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Generator[ProcessedFrame, None, None]:
        """
        读取视频帧
        
        Args:
            video_path: 视频文件路径
            start_frame: 起始帧
            end_frame: 结束帧，None 表示读到结尾
            progress_callback: 进度回调函数 (current, total)
            
        Yields:
            ProcessedFrame 对象
        """
        video_path = Path(video_path)
        cap = cv2.VideoCapture(str(video_path))
        
        if not cap.isOpened():
            raise ValueError(f"Cannot open video: {video_path}")
        
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            if end_frame is None:
                end_frame = total_frames
            
            # 计算采样间隔
            sample_interval = 1
            if self.target_fps and fps > self.target_fps:
                sample_interval = int(fps / self.target_fps)
            
            # 跳到起始帧
            if start_frame > 0:
                cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            
            frame_number = start_frame
            frames_processed = 0
            
            while frame_number < end_frame:
                ret, frame = cap.read()
                if not ret:
                    break
                
                # 采样
                if (frame_number - start_frame) % sample_interval == 0:
                    timestamp = frame_number / fps if fps > 0 else 0
                    
                    yield ProcessedFrame(
                        frame_number=frame_number,
                        timestamp=timestamp,
                        original=frame
                    )
                    
                    frames_processed += 1
                    
                    if progress_callback:
                        progress_callback(frame_number - start_frame, end_frame - start_frame)
                
                frame_number += 1
        
        finally:
            cap.release()
    
    def extract_frame(
        self,
        video_path: str | Path,
        frame_number: int
    ) -> Optional[np.ndarray]:
        """
        提取指定帧
        
        Args:
            video_path: 视频文件路径
            frame_number: 帧号
            
        Returns:
            帧图像或 None
        """
        cap = cv2.VideoCapture(str(video_path))
        
        if not cap.isOpened():
            return None
        
        try:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = cap.read()
            return frame if ret else None
        finally:
            cap.release()
    
    def save_frame(
        self,
        frame: np.ndarray,
        output_path: str | Path,
        quality: int = 95
    ) -> bool:
        """
        保存帧为图片
        
        Args:
            frame: 帧图像
            output_path: 输出路径
            quality: JPEG 质量
            
        Returns:
            是否成功
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if output_path.suffix.lower() in ['.jpg', '.jpeg']:
            params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        else:
            params = []
        
        return cv2.imwrite(str(output_path), frame, params)
    
    def crop_to_person(
        self,
        frame: np.ndarray,
        pose_result: PoseResult,
        padding_ratio: float = 0.15,
        horizontal_padding_ratio: Optional[float] = None,
        text_margin: int = 150
    ) -> np.ndarray:
        """
        根据姿态关键点裁剪图像，只保留人物部分
        
        Args:
            frame: 原始帧图像
            pose_result: 姿态检测结果
            padding_ratio: 垂直边距比例（相对于人物高度）
            horizontal_padding_ratio: 水平边距比例（相对于人物宽度），如果为None则使用padding_ratio
            text_margin: 额外的文字标注边距（像素），确保标注文字不被裁切
            
        Returns:
            裁剪后的图像
        """
        if not pose_result or not pose_result.landmarks:
            return frame
        
        height, width = frame.shape[:2]
        
        # 收集所有可见关键点的坐标
        x_coords = []
        y_coords = []
        
        # pose_result.landmarks 是一个字典，遍历其值
        for landmark in pose_result.landmarks.values():
            if landmark.visibility > 0.5:  # 只考虑可见度高的关键点
                x_coords.append(landmark.x * width)
                y_coords.append(landmark.y * height)
        
        if not x_coords or not y_coords:
            return frame
        
        # 计算边界框
        min_x = int(min(x_coords))
        max_x = int(max(x_coords))
        min_y = int(min(y_coords))
        max_y = int(max(y_coords))
        
        # 计算人物的宽度和高度
        person_width = max_x - min_x
        person_height = max_y - min_y
        
        # 添加边距（左右可以和上下不同）
        h_padding = horizontal_padding_ratio if horizontal_padding_ratio is not None else padding_ratio
        padding_x = int(person_width * h_padding)
        padding_y = int(person_height * padding_ratio)
        
        # 应用边距并确保不超出图像边界
        # 右侧和下方额外增加文字边距，因为标注通常在关键点的右侧或下方
        crop_x1 = max(0, min_x - padding_x)
        crop_x2 = min(width, max_x + padding_x + text_margin)  # 右侧额外加文字边距
        crop_y1 = max(0, min_y - padding_y - int(text_margin * 0.5))  # 上方也加一些边距（阶段标签在顶部）
        crop_y2 = min(height, max_y + padding_y + int(text_margin * 0.3))  # 下方加少量边距
        
        # 裁剪图像
        cropped = frame[crop_y1:crop_y2, crop_x1:crop_x2]
        
        return cropped
    
    def create_annotated_video(
        self,
        video_path: str | Path,
        output_path: str | Path,
        annotate_func: Callable[[np.ndarray, int, float], np.ndarray],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> bool:
        """
        创建标注视频
        
        Args:
            video_path: 输入视频路径
            output_path: 输出视频路径
            annotate_func: 标注函数 (frame, frame_number, timestamp) -> annotated_frame
            progress_callback: 进度回调
            
        Returns:
            是否成功
        """
        video_info = self.get_video_info(video_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 使用 H.264 编码（浏览器兼容性更好）
        # 尝试多个编码选项，按优先级排序
        codecs = [
            ('avc1', 'H.264 - 最佳浏览器兼容性'),
            ('H264', 'H.264 备选'),
            ('X264', 'x264 编码'),
            ('mp4v', 'MPEG-4 Part 2')
        ]
        
        fourcc = None
        for codec, desc in codecs:
            try:
                test_fourcc = cv2.VideoWriter_fourcc(*codec)
                fourcc = test_fourcc
                break
            except:
                continue
        
        if fourcc is None:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # 最后的备选
        
        out = cv2.VideoWriter(
            str(output_path),
            fourcc,
            video_info.fps,
            (video_info.width, video_info.height)
        )
        
        if not out.isOpened():
            return False
        
        try:
            cap = cv2.VideoCapture(str(video_path))
            frame_number = 0
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                timestamp = frame_number / video_info.fps
                
                # 应用标注
                annotated = annotate_func(frame, frame_number, timestamp)
                out.write(annotated)
                
                frame_number += 1
                
                if progress_callback:
                    progress_callback(frame_number, video_info.total_frames)
            
            return True
        
        finally:
            cap.release()
            out.release()


class AnnotationRenderer:
    """标注渲染器"""
    
    # 颜色定义 (BGR)
    COLORS = {
        "primary": (0, 255, 255),      # 黄色
        "secondary": (255, 165, 0),    # 橙色
        "success": (0, 255, 0),        # 绿色
        "warning": (0, 165, 255),      # 橙色
        "danger": (0, 0, 255),         # 红色
        "info": (255, 255, 0),         # 青色
        "white": (255, 255, 255),
        "black": (0, 0, 0)
    }
    
    @classmethod
    def draw_info_panel(
        cls,
        frame: np.ndarray,
        info: dict,
        position: str = "top-left",
        bg_alpha: float = 0.7
    ) -> np.ndarray:
        """
        绘制信息面板
        
        Args:
            frame: 帧图像
            info: 信息字典 {标签: 值}
            position: 位置 ("top-left", "top-right", "bottom-left", "bottom-right")
            bg_alpha: 背景透明度
            
        Returns:
            绘制后的图像
        """
        result = frame.copy()
        
        # 计算面板大小
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        thickness = 1
        line_height = 25
        padding = 10
        
        max_width = 0
        for label, value in info.items():
            text = f"{label}: {value}"
            (w, h), _ = cv2.getTextSize(text, font, font_scale, thickness)
            max_width = max(max_width, w)
        
        panel_width = max_width + padding * 2
        panel_height = len(info) * line_height + padding * 2
        
        # 确定位置
        h, w = frame.shape[:2]
        if position == "top-left":
            x, y = 10, 10
        elif position == "top-right":
            x, y = w - panel_width - 10, 10
        elif position == "bottom-left":
            x, y = 10, h - panel_height - 10
        else:  # bottom-right
            x, y = w - panel_width - 10, h - panel_height - 10
        
        # 绘制半透明背景
        overlay = result.copy()
        cv2.rectangle(overlay, (x, y), (x + panel_width, y + panel_height), (0, 0, 0), -1)
        result = cv2.addWeighted(overlay, bg_alpha, result, 1 - bg_alpha, 0)
        
        # 绘制文字
        text_y = y + padding + 15
        for label, value in info.items():
            text = f"{label}: {value}"
            cv2.putText(result, text, (x + padding, text_y), font, font_scale, cls.COLORS["white"], thickness)
            text_y += line_height
        
        return result
    
    @classmethod
    def _put_chinese_text(
        cls,
        img: np.ndarray,
        text: str,
        position: tuple[int, int],
        font_size: int,
        color: tuple[int, int, int]
    ) -> np.ndarray:
        """
        使用PIL在图像上绘制中文文本
        
        Args:
            img: OpenCV图像 (BGR格式)
            text: 要绘制的文本
            position: 文本左上角位置 (x, y)
            font_size: 字体大小
            color: 颜色 (BGR格式)
            
        Returns:
            绘制后的图像
        """
        # 转换为PIL图像 (RGB)
        img_pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(img_pil)
        
        # 尝试加载中文字体
        font = None
        font_paths = [
            '/System/Library/Fonts/PingFang.ttc',  # macOS
            '/System/Library/Fonts/STHeiti Medium.ttc',  # macOS
            '/System/Library/Fonts/Hiragino Sans GB.ttc',  # macOS
            'C:/Windows/Fonts/msyh.ttc',  # Windows 微软雅黑
            'C:/Windows/Fonts/simhei.ttf',  # Windows 黑体
            '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',  # Linux
        ]
        
        for font_path in font_paths:
            try:
                if Path(font_path).exists():
                    font = ImageFont.truetype(font_path, font_size)
                    break
            except:
                continue
        
        # 如果无法加载字体，使用默认字体
        if font is None:
            try:
                font = ImageFont.load_default()
            except:
                font = None
        
        # PIL使用RGB颜色，需要从BGR转换
        color_rgb = (color[2], color[1], color[0])
        
        # 绘制文本
        if font:
            draw.text(position, text, font=font, fill=color_rgb)
        else:
            draw.text(position, text, fill=color_rgb)
        
        # 转换回OpenCV图像 (BGR)
        img_cv = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
        
        return img_cv
    
    @classmethod
    def draw_phase_indicator(
        cls,
        frame: np.ndarray,
        phase: str,
        phase_cn: str
    ) -> np.ndarray:
        """
        绘制阶段指示器
        
        Args:
            frame: 帧图像
            phase: 阶段名称（英文）
            phase_cn: 阶段名称（中文）
            
        Returns:
            绘制后的图像
        """
        result = frame.copy()
        h, w = frame.shape[:2]
        
        # 阶段颜色
        phase_colors = {
            "preparation": cls.COLORS["info"],
            "lifting": cls.COLORS["warning"],
            "release": cls.COLORS["success"],
            "follow_through": cls.COLORS["primary"],
            "unknown": cls.COLORS["white"]
        }
        
        color = phase_colors.get(phase.lower(), cls.COLORS["white"])
        
        # 文本内容（直接使用中文）
        text = phase_cn
        font_size = 32
        
        # 使用PIL测量文本大小
        temp_img = Image.new('RGB', (w, h))
        temp_draw = ImageDraw.Draw(temp_img)
        
        # 加载字体
        font = None
        font_paths = [
            '/System/Library/Fonts/PingFang.ttc',
            '/System/Library/Fonts/STHeiti Medium.ttc',
            'C:/Windows/Fonts/msyh.ttc',
        ]
        
        for font_path in font_paths:
            try:
                if Path(font_path).exists():
                    font = ImageFont.truetype(font_path, font_size)
                    break
            except:
                continue
        
        if font is None:
            font = ImageFont.load_default()
        
        # 获取文本大小
        bbox = temp_draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        
        # 居中显示在顶部
        padding = 15
        x = (w - text_w) // 2 - padding
        y = 20
        
        # 绘制背景矩形
        cv2.rectangle(
            result,
            (x, y),
            (x + text_w + padding * 2, y + text_h + padding * 2),
            (0, 0, 0),
            -1
        )
        
        # 绘制边框
        cv2.rectangle(
            result,
            (x, y),
            (x + text_w + padding * 2, y + text_h + padding * 2),
            color,
            3
        )
        
        # 使用PIL绘制中文文本
        result = cls._put_chinese_text(
            result, 
            text, 
            (x + padding, y + padding), 
            font_size, 
            color
        )
        
        return result
    
    @classmethod
    def draw_score_badge(
        cls,
        frame: np.ndarray,
        score: float,
        rating: str
    ) -> np.ndarray:
        """
        绘制分数徽章
        
        Args:
            frame: 帧图像
            score: 分数
            rating: 评级
            
        Returns:
            绘制后的图像
        """
        result = frame.copy()
        h, w = frame.shape[:2]
        
        # 颜色根据评级
        if rating == "excellent":
            color = cls.COLORS["success"]
        elif rating == "good":
            color = cls.COLORS["primary"]
        elif rating == "fair":
            color = cls.COLORS["warning"]
        else:
            color = cls.COLORS["danger"]
        
        # 绘制圆形背景
        center = (w - 60, 60)
        radius = 45
        cv2.circle(result, center, radius, (0, 0, 0), -1)
        cv2.circle(result, center, radius, color, 3)
        
        # 绘制分数
        text = f"{score:.0f}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 1.2
        thickness = 2
        
        (text_w, text_h), _ = cv2.getTextSize(text, font, font_scale, thickness)
        text_x = center[0] - text_w // 2
        text_y = center[1] + text_h // 2
        
        cv2.putText(result, text, (text_x, text_y), font, font_scale, color, thickness)
        
        return result
    
    @classmethod
    def draw_angle_arc(
        cls,
        frame: np.ndarray,
        center: tuple[int, int],
        point1: tuple[int, int],
        point2: tuple[int, int],
        angle: float,
        color: tuple[int, int, int] = (0, 255, 255),
        show_value: bool = True
    ) -> np.ndarray:
        """
        绘制角度弧线
        
        Args:
            frame: 帧图像
            center: 角的顶点
            point1: 第一条边的端点
            point2: 第二条边的端点
            angle: 角度值
            color: 颜色
            show_value: 是否显示数值
            
        Returns:
            绘制后的图像
        """
        result = frame.copy()
        
        # 计算起始和结束角度
        angle1 = np.arctan2(point1[1] - center[1], point1[0] - center[0])
        angle2 = np.arctan2(point2[1] - center[1], point2[0] - center[0])
        
        start_angle = np.degrees(angle1)
        end_angle = np.degrees(angle2)
        
        # 绘制弧线
        radius = 30
        cv2.ellipse(
            result,
            center,
            (radius, radius),
            0,
            start_angle,
            end_angle,
            color,
            2
        )
        
        # 显示角度值
        if show_value:
            # 在弧线中间位置显示
            mid_angle = (angle1 + angle2) / 2
            text_x = int(center[0] + (radius + 15) * np.cos(mid_angle))
            text_y = int(center[1] + (radius + 15) * np.sin(mid_angle))
            
            text = f"{angle:.0f}deg"
            cv2.putText(
                result, text,
                (text_x - 15, text_y + 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5, color, 1
            )
        
        return result
