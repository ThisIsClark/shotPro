"""
Analysis Service Module
投篮分析服务：整合所有核心模块进行完整分析
"""

from __future__ import annotations

import uuid
import cv2
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable
from datetime import datetime

from ..config import settings
from ..core.pose_detector import PoseDetector, PoseResult, PoseLandmark
from ..core.angle_calculator import AngleCalculator, ShootingAngles
from ..core.phase_detector import PhaseDetector, ShootingPhase, FrameData
from ..core.rules_engine import RulesEngine, EvaluationResult
from ..core.video_processor import VideoProcessor, VideoInfo, AnnotationRenderer


@dataclass
class AnalysisConfig:
    """分析配置"""
    shooting_hand: str = "right"  # "left" or "right"
    shooting_style: str = "one_motion"  # "one_motion" or "two_motion"
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    generate_annotated_video: bool = False  # 默认不生成标注视频（提高速度）
    generate_key_frames: bool = True
    generate_evaluation: bool = True  # 是否生成评分和建议
    smooth_angles: bool = True
    smooth_window: int = 5


@dataclass
class KeyFrameInfo:
    """关键帧信息"""
    phase: ShootingPhase
    frame_number: int
    timestamp: float
    image_path: str
    angles: Optional[ShootingAngles] = None


@dataclass
class AnalysisProgress:
    """分析进度"""
    stage: str
    current: int
    total: int
    percentage: int
    message: str


@dataclass
class FullAnalysisResult:
    """完整分析结果"""
    task_id: str
    video_filename: str
    video_info: VideoInfo
    evaluation: Optional[EvaluationResult]  # 可选：创建模板时不生成评估
    key_frames: list[KeyFrameInfo]
    annotated_video_path: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> dict:
        """转换为字典"""
        result = {
            "task_id": self.task_id,
            "video_filename": self.video_filename
        }
        
        # 如果有评估结果，添加评估相关字段
        if self.evaluation:
            result.update({
                "overall_score": self.evaluation.overall_score,
                "rating": self.evaluation.rating,
                "dimension_scores": [
                    {
                        "name": ds.name,
                        "name_en": ds.name_en,
                        "score": ds.score,
                        "weight": ds.weight,
                        "weighted_score": ds.weighted_score,
                        "feedback": ds.feedback,
                        "feedback_en": ds.feedback_en
                    }
                    for ds in self.evaluation.dimension_scores
                ],
                "phases": [],  # TODO: 添加阶段数据
                "issues": [
                    {
                        "type": issue.type.value,
                        "severity": issue.severity.value,
                        "description": issue.description,
                        "description_en": issue.description_en,
                        "phase": issue.phase.value if issue.phase else None,
                        "suggestion": issue.suggestion,
                        "suggestion_en": issue.suggestion_en
                    }
                    for issue in self.evaluation.issues
                ],
                "suggestions": self.evaluation.suggestions
            })
        
        # 关键帧数据（总是包含）
        result["key_frames"] = [
            {
                "phase": kf.phase.value,
                "frame_number": kf.frame_number,
                "timestamp": kf.timestamp,
                "image_url": kf.image_path,
                "angles": kf.angles.to_dict() if kf.angles else None
            }
            for kf in self.key_frames
        ]
        
        # 其他通用字段
        result.update({
            "annotated_video_url": self.annotated_video_path,
            "total_frames": self.video_info.total_frames,
            "fps": self.video_info.fps,
            "duration": self.video_info.duration,
            "created_at": self.created_at
        })
        
        return result


class AnalysisService:
    """投篮分析服务"""
    
    # 阶段名称映射
    PHASE_NAMES = {
        ShootingPhase.PREPARATION: "准备阶段",
        ShootingPhase.LIFTING: "上升阶段",
        ShootingPhase.RELEASE: "出手阶段",
        ShootingPhase.FOLLOW_THROUGH: "跟随阶段",
        ShootingPhase.UNKNOWN: "未知"
    }
    
    def __init__(self, config: Optional[AnalysisConfig] = None):
        """
        初始化分析服务
        
        Args:
            config: 分析配置
        """
        self.config = config or AnalysisConfig()
        
        # 初始化各模块
        self.pose_detector = PoseDetector(
            min_detection_confidence=self.config.min_detection_confidence,
            min_tracking_confidence=self.config.min_tracking_confidence
        )
        self.angle_calculator = AngleCalculator()
        self.phase_detector = PhaseDetector()
        # 根据投篮方式初始化规则引擎
        from ..core.rules_engine import ShootingStyle
        shooting_style_val = ShootingStyle.ONE_MOTION if self.config.shooting_style == "one_motion" else ShootingStyle.TWO_MOTION
        self.rules_engine = RulesEngine(shooting_style=shooting_style_val)
        self.video_processor = VideoProcessor(target_fps=settings.target_fps)
    
    def analyze_video(
        self,
        video_path: str | Path,
        task_id: Optional[str] = None,
        progress_callback: Optional[Callable[[AnalysisProgress], None]] = None
    ) -> FullAnalysisResult:
        """
        分析投篮视频
        
        Args:
            video_path: 视频文件路径
            task_id: 任务ID，如果不提供则自动生成
            progress_callback: 进度回调函数
            
        Returns:
            完整分析结果
        """
        video_path = Path(video_path)
        task_id = task_id or str(uuid.uuid4())
        
        # 创建结果目录
        result_dir = settings.results_dir / task_id
        result_dir.mkdir(parents=True, exist_ok=True)
        
        # 重置状态
        self.phase_detector.reset()
        
        # 获取视频信息
        self._report_progress(progress_callback, "info", 0, 1, "获取视频信息...")
        video_info = self.video_processor.get_video_info(video_path)
        
        # 第一阶段：检测姿态和计算角度
        self._report_progress(progress_callback, "detection", 0, video_info.total_frames, "检测人体姿态...")
        
        frame_data_list: list[FrameData] = []
        pose_results: dict[int, PoseResult] = {}
        angles_history: list[ShootingAngles] = []
        
        for processed_frame in self.video_processor.read_frames(video_path):
            # 检测姿态
            pose_result = self.pose_detector.detect(processed_frame.original)
            
            if pose_result:
                pose_results[processed_frame.frame_number] = pose_result
                
                # 计算角度
                angles = self.angle_calculator.calculate_all_angles(
                    pose_result,
                    self.config.shooting_hand
                )
                
                if angles:
                    # 平滑处理
                    if self.config.smooth_angles and angles_history:
                        angles_history.append(angles)
                        smoothed = self.angle_calculator.smooth_angles(
                            angles_history,
                            self.config.smooth_window
                        )
                    else:
                        angles_history.append(angles)
                        smoothed = angles
                    
                    # 获取手腕关键点
                    wrist_idx = (PoseLandmark.RIGHT_WRIST 
                                if self.config.shooting_hand == "right" 
                                else PoseLandmark.LEFT_WRIST)
                    wrist = pose_result.get_landmark(wrist_idx)
                    
                    if wrist:
                        # 检测阶段
                        phase = self.phase_detector.detect_phase(
                            processed_frame.frame_number,
                            processed_frame.timestamp,
                            smoothed,
                            wrist,
                            pose_result.confidence
                        )
                        
                        # 保存帧数据
                        frame_data = FrameData(
                            frame_number=processed_frame.frame_number,
                            timestamp=processed_frame.timestamp,
                            angles=smoothed,
                            wrist_y=wrist.y,
                            phase=phase,
                            confidence=pose_result.confidence
                        )
                        frame_data_list.append(frame_data)
            
            # 更新进度
            self._report_progress(
                progress_callback, 
                "detection", 
                processed_frame.frame_number, 
                video_info.total_frames,
                f"处理帧 {processed_frame.frame_number}/{video_info.total_frames}"
            )
        
        # 第二阶段：评估（如果需要）
        evaluation = None
        if self.config.generate_evaluation:
            self._report_progress(progress_callback, "evaluation", 0, 1, "评估投篮姿势...")
            phase_segments = self.phase_detector.get_phase_segments()
            evaluation = self.rules_engine.evaluate(phase_segments, frame_data_list)
        
        # 第三阶段：生成关键帧
        key_frames: list[KeyFrameInfo] = []
        
        if self.config.generate_key_frames:
            self._report_progress(progress_callback, "keyframes", 0, 4, "生成关键帧...")
            
            key_frame_data = self.phase_detector.get_key_frames()
            
            for i, (phase, frame_data) in enumerate(key_frame_data.items()):
                if frame_data and phase != ShootingPhase.UNKNOWN:
                    # 提取帧
                    frame = self.video_processor.extract_frame(video_path, frame_data.frame_number)
                    
                    if frame is not None:
                        # 获取该帧的姿态结果
                        pose_result = pose_results.get(frame_data.frame_number)
                        
                        if pose_result:
                            # 绘制标注
                            annotated = self.pose_detector.draw_landmarks(
                                frame,
                                pose_result,
                                highlight_shooting_arm=True,
                                shooting_hand=self.config.shooting_hand
                            )
                            
                            # 绘制角度
                            if frame_data.angles:
                                annotated = self.pose_detector.draw_angles(
                                    annotated,
                                    pose_result,
                                    frame_data.angles.to_dict(),
                                    self.config.shooting_hand
                                )
                            
                            # 绘制阶段信息
                            annotated = AnnotationRenderer.draw_phase_indicator(
                                annotated,
                                phase.value,
                                self.PHASE_NAMES[phase]
                            )
                            
                            # 裁剪图像，只保留人物部分（确保标注文字不被裁切）
                            annotated = self.video_processor.crop_to_person(
                                annotated,
                                pose_result,
                                padding_ratio=0.35,  # 上下边距
                                horizontal_padding_ratio=0.5,  # 左右边距（更大）
                                text_margin=180  # 额外的文字标注边距（像素）
                            )
                        else:
                            annotated = frame
                        
                        # 保存关键帧
                        image_filename = f"keyframe_{phase.value}.jpg"
                        image_path = result_dir / image_filename
                        self.video_processor.save_frame(annotated, image_path)
                        
                        key_frames.append(KeyFrameInfo(
                            phase=phase,
                            frame_number=frame_data.frame_number,
                            timestamp=frame_data.timestamp,
                            image_path=f"/results/{task_id}/{image_filename}",
                            angles=frame_data.angles
                        ))
                
                self._report_progress(progress_callback, "keyframes", i + 1, 4, f"生成关键帧 {i + 1}/4")
            
            # 确保关键帧按照时间顺序排列（按frame_number排序）
            key_frames.sort(key=lambda kf: kf.frame_number)
        
        # 第四阶段：生成标注视频
        annotated_video_path = None
        
        if self.config.generate_annotated_video:
            self._report_progress(progress_callback, "video", 0, video_info.total_frames, "生成标注视频...")
            
            output_video_path = result_dir / "annotated.mp4"
            
            # 预先建立帧数据索引（优化性能）
            frame_data_dict = {fd.frame_number: fd for fd in frame_data_list}
            
            # 创建标注函数
            def annotate_frame(frame: cv2.Mat, frame_number: int, timestamp: float) -> cv2.Mat:
                annotated = frame.copy()
                
                # 获取姿态结果
                pose_result = pose_results.get(frame_number)
                
                if pose_result:
                    # 绘制骨骼
                    annotated = self.pose_detector.draw_landmarks(
                        annotated,
                        pose_result,
                        highlight_shooting_arm=True,
                        shooting_hand=self.config.shooting_hand
                    )
                    
                    # 查找对应的帧数据（使用字典索引，O(1) 复杂度）
                    frame_data = frame_data_dict.get(frame_number)
                    
                    if frame_data:
                        # 绘制角度
                        if frame_data.angles:
                            annotated = self.pose_detector.draw_angles(
                                annotated,
                                pose_result,
                                frame_data.angles.to_dict(),
                                self.config.shooting_hand
                            )
                        
                        # 绘制阶段指示
                        annotated = AnnotationRenderer.draw_phase_indicator(
                            annotated,
                            frame_data.phase.value,
                            self.PHASE_NAMES[frame_data.phase]
                        )
                
                # 绘制分数（右上角）
                annotated = AnnotationRenderer.draw_score_badge(
                    annotated,
                    evaluation.overall_score,
                    evaluation.rating
                )
                
                # 绘制信息面板
                info = {
                    "Frame": f"{frame_number}",
                    "Time": f"{timestamp:.2f}s"
                }
                annotated = AnnotationRenderer.draw_info_panel(annotated, info, "bottom-left")
                
                return annotated
            
            def video_progress(current, total):
                self._report_progress(
                    progress_callback,
                    "video",
                    current,
                    total,
                    f"生成视频帧 {current}/{total}"
                )
            
            success = self.video_processor.create_annotated_video(
                video_path,
                output_video_path,
                annotate_frame,
                video_progress
            )
            
            if success:
                annotated_video_path = f"/results/{task_id}/annotated.mp4"
        
        # 完成
        self._report_progress(progress_callback, "done", 1, 1, "分析完成")
        
        return FullAnalysisResult(
            task_id=task_id,
            video_filename=video_path.name,
            video_info=video_info,
            evaluation=evaluation,
            key_frames=key_frames,
            annotated_video_path=annotated_video_path
        )
    
    def _report_progress(
        self,
        callback: Optional[Callable[[AnalysisProgress], None]],
        stage: str,
        current: int,
        total: int,
        message: str
    ):
        """报告进度"""
        if callback:
            percentage = int(current / total * 100) if total > 0 else 0
            
            # 根据阶段调整总体进度
            stage_weights = {
                "info": (0, 5),
                "detection": (5, 60),
                "evaluation": (60, 65),
                "keyframes": (65, 80),
                "video": (80, 100),
                "done": (100, 100)
            }
            
            start, end = stage_weights.get(stage, (0, 100))
            overall_percentage = start + (end - start) * percentage // 100
            
            callback(AnalysisProgress(
                stage=stage,
                current=current,
                total=total,
                percentage=overall_percentage,
                message=message
            ))
    
    def close(self):
        """释放资源"""
        self.pose_detector.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
