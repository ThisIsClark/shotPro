"""
Analysis Service Module
投篮分析服务：整合所有核心模块进行完整分析
"""

from __future__ import annotations

import uuid
import json
import cv2
import numpy as np
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable
from datetime import datetime

from ..config import settings
from ..core.pose_detector import PoseDetector, PoseResult, PoseLandmark
from ..core.angle_calculator import AngleCalculator, ShootingAngles
from ..core.phase_detector import PhaseDetector, ShootingPhase, FrameData
from ..core.rules_engine import RulesEngine, CoordinationIssue
from ..core.video_processor import VideoProcessor, VideoInfo, AnnotationRenderer


@dataclass
class AnalysisConfig:
    """分析配置"""
    shooting_hand: str = "right"  # "left" or "right"
    shooting_style: str = "one_motion"  # "one_motion" or "two_motion"
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5
    generate_annotated_video: bool = False  # 默认不生成标注视频（提高速度）
    generate_skeleton_video: bool = False  # 生成纯骨骼运动视频
    generate_key_frames: bool = True
    generate_evaluation: bool = True  # 是否生成评分和建议
    smooth_angles: bool = True
    smooth_window: int = 5
    generate_frame_data: bool = True  # 是否持久化 per-frame 时序数据（供曲线图使用）


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
    coordination_issues: list[CoordinationIssue]  # 发力连贯性检测结果
    key_frames: list[KeyFrameInfo]
    annotated_video_path: Optional[str] = None
    skeleton_video_path: Optional[str] = None  # 骨骼运动视频路径
    template_comparison: Optional[dict] = None  # 模板对比结果
    frame_data_url: Optional[str] = None  # per-frame 时序数据 JSON 文件的访问 URL（供曲线图按需 fetch）
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        """转换为字典"""
        result = {
            "task_id": self.task_id,
            "video_filename": self.video_filename
        }

        # 创建 frame_number -> image_url 的映射（更可靠的匹配方式）
        frame_num_to_image_url = {
            kf.frame_number: kf.image_path
            for kf in self.key_frames
        }

        # 创建 phase -> image_url 的映射
        phase_to_image_url = {
            kf.phase: kf.image_path
            for kf in self.key_frames
        }

        # 发力连贯性检测结果
        result["coordination_issues"] = [
            {
                "issue_type": issue.issue_type.value,
                "detected": issue.detected,
                "severity": issue.severity.value,
                "frame_1": {
                    "phase": issue.frame_1.phase.value if issue.frame_1 else None,
                    "frame_number": issue.frame_1.frame_number if issue.frame_1 else None,
                    "timestamp": issue.frame_1.timestamp if issue.frame_1 else None,
                    # 使用 frame_number 匹配获取正确的 image_url
                    "image_url": frame_num_to_image_url.get(issue.frame_1.frame_number) if issue.frame_1 else None,
                    "angles": issue.frame_1.angles.to_dict() if issue.frame_1 and issue.frame_1.angles else None
                } if issue.frame_1 else None,
                "frame_2": {
                    "phase": issue.frame_2.phase.value if issue.frame_2 else None,
                    "frame_number": issue.frame_2.frame_number if issue.frame_2 else None,
                    "timestamp": issue.frame_2.timestamp if issue.frame_2 else None,
                    # 使用 frame_number 匹配获取正确的 image_url
                    "image_url": frame_num_to_image_url.get(issue.frame_2.frame_number) if issue.frame_2 else None,
                    "angles": issue.frame_2.angles.to_dict() if issue.frame_2 and issue.frame_2.angles else None
                } if issue.frame_2 else None,
                "knee_angle_1": issue.knee_angle_1,
                "knee_angle_2": issue.knee_angle_2,
                "description": issue.description,
                "description_en": issue.description_en,
                "suggestion": issue.suggestion,
                "suggestion_en": issue.suggestion_en,
                "skipped": issue.skipped,
                "skip_reason": issue.skip_reason
            }
            for issue in self.coordination_issues
        ]

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
            "skeleton_video_url": self.skeleton_video_path,
            "total_frames": self.video_info.total_frames,
            "fps": self.video_info.fps,
            "duration": self.video_info.duration,
            "created_at": self.created_at,
            "template_comparison": self.template_comparison,
            "frame_data_url": self.frame_data_url
        })

        return result


class AnalysisService:
    """投篮分析服务"""

    # 阶段名称映射（4帧版本 - 发力连贯性检测）
    PHASE_NAMES = {
        ShootingPhase.SYNC_FRAME_1: "Dip Point",
        ShootingPhase.SYNC_FRAME_2: "Hand Rise",
        ShootingPhase.MAX_HOLD_FRAME: "Max Hold",
        ShootingPhase.RELEASE_FRAME: "Release",
        ShootingPhase.KNEE_MIN_FRAME: "Deep Squat",
        ShootingPhase.ELBOW_MIN_FRAME: "Elbow Tuck",
        ShootingPhase.WRIST_PEAK_FRAME: "Wrist Peak",
        ShootingPhase.FOLLOW_THROUGH_FRAME: "Follow-thru",
        ShootingPhase.PREPARATION: "Preparation",
        ShootingPhase.LIFTING: "Lifting",
        ShootingPhase.RELEASE: "Release",
        ShootingPhase.FOLLOW_THROUGH: "Follow-through",
        ShootingPhase.UNKNOWN: "Unknown"
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
        self.rules_engine = RulesEngine()
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
        self._report_progress(progress_callback, "info", 0, 1, "Getting video info...")
        video_info = self.video_processor.get_video_info(video_path)
        
        # 第一阶段：检测姿态和计算角度
        self._report_progress(progress_callback, "detection", 0, video_info.total_frames, "Detecting pose...")
        
        frame_data_list: list[FrameData] = []
        pose_results: dict[int, PoseResult] = {}
        frame_cache: dict[int, np.ndarray] = {}

        for processed_frame in self.video_processor.read_frames(video_path):
            # 缓存帧图像，避免后续extract_frame因视频编解码器关键帧机制导致帧不一致
            frame_cache[processed_frame.frame_number] = processed_frame.original

            # 检测姿态
            pose_result = self.pose_detector.detect(processed_frame.original)
            
            if pose_result:
                pose_results[processed_frame.frame_number] = pose_result
                
                # 计算角度（原始值，不在此处平滑——PhaseDetector内部会做平滑）
                angles = self.angle_calculator.calculate_all_angles(
                    pose_result,
                    self.config.shooting_hand
                )

                # 获取手腕关键点（总是调用detect_phase以保存原始手腕Y值）
                wrist_idx = (PoseLandmark.RIGHT_WRIST
                            if self.config.shooting_hand == "right"
                            else PoseLandmark.LEFT_WRIST)
                wrist = pose_result.get_landmark(wrist_idx)

                if wrist:
                    # 检测阶段（即使角度为None也调用，以保存手腕Y值用于关键帧检测）
                    # 传入原始angles，PhaseDetector内部会做平滑处理
                    phase = self.phase_detector.detect_phase(
                        processed_frame.frame_number,
                        processed_frame.timestamp,
                        angles,  # 原始值，可能为None
                        wrist,
                        pose_result.confidence
                    )

                    # 从PhaseDetector获取平滑后的角度（避免双重平滑）
                    smoothed_angles = self.phase_detector.frame_history[-1].angles if self.phase_detector.frame_history else None

                    # 保存帧数据（只在角度存在时保存完整数据）
                    if smoothed_angles:
                        frame_data = FrameData(
                            frame_number=processed_frame.frame_number,
                            timestamp=processed_frame.timestamp,
                            angles=smoothed_angles,
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
                f"Processing frame {processed_frame.frame_number}/{video_info.total_frames}"
            )
        
        # 第二阶段：检测发力连贯性（如果需要）
        coordination_issues = []
        if self.config.generate_evaluation:
            self._report_progress(progress_callback, "evaluation", 0, 1, "Detecting coordination issues...")
            key_frame_data = self.phase_detector.get_key_frames()
            coordination_issues = self.rules_engine.evaluate_coordination(key_frame_data, frame_data_list)
        
        # 第三阶段：生成关键帧（4帧版本 - 发力连贯性检测）
        key_frames: list[KeyFrameInfo] = []

        if self.config.generate_key_frames:
            self._report_progress(progress_callback, "keyframes", 0, 8, "Generating keyframes...")

            key_frame_data = self.phase_detector.get_key_frames()

            # 预先计算统一裁剪区域（8 帧取并集 bbox），所有关键帧共用 -> 构图统一、人物放大
            # crop_info 保证骨骼/角度坐标重映射对齐，裁剪不会导致骨骼错位
            crop_frame_nums = [
                fd.frame_number for fd in key_frame_data.values()
                if fd and fd.phase != ShootingPhase.UNKNOWN
            ]
            crop_info = self.video_processor.compute_person_crop_region(
                pose_results, frame_cache, crop_frame_nums
            )

            for i, (phase, frame_data) in enumerate(key_frame_data.items()):
                if frame_data and phase != ShootingPhase.UNKNOWN:
                    # 从缓存获取帧图像（避免extract_frame因编解码器关键帧机制返回错误帧）
                    frame = frame_cache.get(frame_data.frame_number)
                    if frame is None:
                        frame = self.video_processor.extract_frame(video_path, frame_data.frame_number)

                    if frame is not None:
                        # 获取该帧的姿态结果
                        pose_result = pose_results.get(frame_data.frame_number)

                        if pose_result:
                            # 统一裁剪到人物区域（crop_info 已含坐标重映射，骨骼不会错位）
                            if crop_info:
                                draw_frame = frame[
                                    crop_info['crop_y1']:crop_info['crop_y2'],
                                    crop_info['crop_x1']:crop_info['crop_x2']
                                ].copy()
                                draw_crop_info = crop_info
                            else:
                                draw_frame, draw_crop_info = frame, None

                            annotated = self.pose_detector.draw_landmarks(
                                draw_frame,
                                pose_result,
                                highlight_shooting_arm=True,
                                shooting_hand=self.config.shooting_hand,
                                crop_info=draw_crop_info
                            )

                            # 绘制角度
                            if frame_data.angles:
                                annotated = self.pose_detector.draw_angles(
                                    annotated,
                                    pose_result,
                                    frame_data.angles.to_dict(),
                                    self.config.shooting_hand,
                                    crop_info=draw_crop_info
                                )

                            # 绘制阶段信息（画在裁剪后的帧上，尺寸已适配）
                            annotated = AnnotationRenderer.draw_phase_indicator(
                                annotated,
                                phase.value,
                                self.PHASE_NAMES.get(phase, phase.value)
                            )
                        else:
                            annotated = frame

                        # 保存关键帧（使用PNG格式以保留骨骼点颜色）
                        image_filename = f"keyframe_{phase.value}.png"
                        image_path = result_dir / image_filename
                        self.video_processor.save_frame(annotated, image_path)

                        key_frames.append(KeyFrameInfo(
                            phase=phase,
                            frame_number=frame_data.frame_number,
                            timestamp=frame_data.timestamp,
                            image_path=f"/results/{task_id}/{image_filename}",
                            angles=frame_data.angles
                        ))

                self._report_progress(progress_callback, "keyframes", i + 1, 8, f"Generating keyframe {i + 1}/8")

            # 确保关键帧按照时间顺序排列（按frame_number排序）
            key_frames.sort(key=lambda kf: kf.frame_number)
        
        # 第四阶段：生成标注视频
        annotated_video_path = None
        
        if self.config.generate_annotated_video:
            self._report_progress(progress_callback, "video", 0, video_info.total_frames, "Generating annotated video...")
            
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

        # 第五阶段：生成骨骼运动视频
        skeleton_video_path = None

        if self.config.generate_skeleton_video:
            self._report_progress(progress_callback, "skeleton", 0, video_info.total_frames, "Generating skeleton video...")

            output_skeleton_path = result_dir / "skeleton.mp4"

            # 预先建立帧数据索引（优化性能）
            frame_data_dict = {fd.frame_number: fd for fd in frame_data_list}

            # 创建骨骼绘制函数
            def draw_skeleton(frame: cv2.Mat, frame_number: int, timestamp: float) -> cv2.Mat:
                # frame 已经是黑色背景，直接在上面绘制
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

                    # 查找对应的帧数据
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

                # 绘制信息面板
                info = {
                    "Frame": f"{frame_number}",
                    "Time": f"{timestamp:.2f}s"
                }
                annotated = AnnotationRenderer.draw_info_panel(annotated, info, "bottom-left")

                return annotated

            def skeleton_progress(current, total):
                self._report_progress(
                    progress_callback,
                    "skeleton",
                    current,
                    total,
                    f"生成骨骼视频帧 {current}/{total}"
                )

            success = self.video_processor.create_skeleton_video(
                video_path,
                output_skeleton_path,
                pose_results,
                draw_skeleton,
                skeleton_progress
            )

            if success:
                skeleton_video_path = f"/results/{task_id}/skeleton.mp4"

        # 完成
        self._report_progress(progress_callback, "done", 1, 1, "Analysis complete")

        # 持久化 per-frame 时序数据（供曲线图使用）
        frame_data_url = None
        if self.config.generate_frame_data and frame_data_list:
            frame_data_path = result_dir / "frame_data.json"
            serialized = [
                {
                    "frame_number": fd.frame_number,
                    "timestamp": fd.timestamp,
                    "phase": fd.phase.value,
                    "angles": fd.angles.to_dict() if fd.angles else None,
                    "wrist_y": fd.wrist_y,
                    "confidence": fd.confidence
                }
                for fd in frame_data_list
            ]
            with open(frame_data_path, 'w', encoding='utf-8') as f:
                json.dump(serialized, f, ensure_ascii=False)
            frame_data_url = f"/results/{task_id}/frame_data.json"

        return FullAnalysisResult(
            task_id=task_id,
            video_filename=video_path.name,
            video_info=video_info,
            coordination_issues=coordination_issues,
            key_frames=key_frames,
            annotated_video_path=annotated_video_path,
            skeleton_video_path=skeleton_video_path,
            frame_data_url=frame_data_url
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
                "detection": (5, 50),
                "evaluation": (50, 55),
                "keyframes": (55, 65),
                "video": (65, 82),
                "skeleton": (82, 100),
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
