"""
MediaPipe Pose Detection Module
使用 MediaPipe 进行人体姿态检测
"""

import cv2
import numpy as np
import mediapipe as mp
from dataclasses import dataclass
from typing import Optional
from enum import IntEnum


class PoseLandmark(IntEnum):
    """MediaPipe Pose 关键点索引"""
    # 面部
    NOSE = 0
    LEFT_EYE_INNER = 1
    LEFT_EYE = 2
    LEFT_EYE_OUTER = 3
    RIGHT_EYE_INNER = 4
    RIGHT_EYE = 5
    RIGHT_EYE_OUTER = 6
    LEFT_EAR = 7
    RIGHT_EAR = 8
    MOUTH_LEFT = 9
    MOUTH_RIGHT = 10
    
    # 上肢
    LEFT_SHOULDER = 11
    RIGHT_SHOULDER = 12
    LEFT_ELBOW = 13
    RIGHT_ELBOW = 14
    LEFT_WRIST = 15
    RIGHT_WRIST = 16
    LEFT_PINKY = 17
    RIGHT_PINKY = 18
    LEFT_INDEX = 19
    RIGHT_INDEX = 20
    LEFT_THUMB = 21
    RIGHT_THUMB = 22
    
    # 下肢
    LEFT_HIP = 23
    RIGHT_HIP = 24
    LEFT_KNEE = 25
    RIGHT_KNEE = 26
    LEFT_ANKLE = 27
    RIGHT_ANKLE = 28
    LEFT_HEEL = 29
    RIGHT_HEEL = 30
    LEFT_FOOT_INDEX = 31
    RIGHT_FOOT_INDEX = 32


@dataclass
class Landmark:
    """单个关键点"""
    x: float  # 归一化坐标 [0, 1]
    y: float
    z: float  # 深度估计
    visibility: float  # 可见度置信度
    
    def to_pixel(self, width: int, height: int) -> tuple[int, int]:
        """转换为像素坐标"""
        return int(self.x * width), int(self.y * height)
    
    def to_array(self) -> np.ndarray:
        """转换为 numpy 数组"""
        return np.array([self.x, self.y, self.z])


@dataclass
class PoseResult:
    """姿态检测结果"""
    landmarks: dict[int, Landmark]  # 关键点字典
    confidence: float  # 整体置信度
    image_width: int
    image_height: int
    raw_landmarks: Optional[any] = None  # 原始 MediaPipe landmarks 对象
    
    def get_landmark(self, idx: PoseLandmark) -> Optional[Landmark]:
        """获取指定关键点"""
        return self.landmarks.get(int(idx))
    
    def get_pixel_coords(self, idx: PoseLandmark) -> Optional[tuple[int, int]]:
        """获取指定关键点的像素坐标"""
        landmark = self.get_landmark(idx)
        if landmark:
            return landmark.to_pixel(self.image_width, self.image_height)
        return None
    
    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            int(idx): {
                "x": lm.x,
                "y": lm.y,
                "z": lm.z,
                "visibility": lm.visibility
            }
            for idx, lm in self.landmarks.items()
        }


class PoseDetector:
    """姿态检测器"""
    
    def __init__(
        self,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        model_complexity: int = 1
    ):
        """
        初始化姿态检测器
        
        Args:
            min_detection_confidence: 最小检测置信度
            min_tracking_confidence: 最小跟踪置信度
            model_complexity: 模型复杂度 (0, 1, 2)
        """
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,  # 视频模式
            model_complexity=model_complexity,
            smooth_landmarks=True,
            enable_segmentation=False,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )
        
        # 投篮分析需要的关键点
        self.shooting_landmarks = [
            PoseLandmark.LEFT_SHOULDER,
            PoseLandmark.RIGHT_SHOULDER,
            PoseLandmark.LEFT_ELBOW,
            PoseLandmark.RIGHT_ELBOW,
            PoseLandmark.LEFT_WRIST,
            PoseLandmark.RIGHT_WRIST,
            PoseLandmark.LEFT_INDEX,
            PoseLandmark.RIGHT_INDEX,
            PoseLandmark.LEFT_HIP,
            PoseLandmark.RIGHT_HIP,
            PoseLandmark.LEFT_KNEE,
            PoseLandmark.RIGHT_KNEE,
            PoseLandmark.LEFT_ANKLE,
            PoseLandmark.RIGHT_ANKLE,
        ]
    
    def detect(self, frame: np.ndarray) -> Optional[PoseResult]:
        """
        检测单帧图像中的人体姿态
        
        Args:
            frame: BGR 格式的图像
            
        Returns:
            PoseResult 或 None (如果未检测到)
        """
        height, width = frame.shape[:2]
        
        # 转换为 RGB (MediaPipe 需要 RGB 输入)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # 检测
        results = self.pose.process(rgb_frame)
        
        if not results.pose_landmarks:
            return None
        
        # 提取关键点
        landmarks = {}
        total_visibility = 0.0
        
        for idx, landmark in enumerate(results.pose_landmarks.landmark):
            landmarks[idx] = Landmark(
                x=landmark.x,
                y=landmark.y,
                z=landmark.z,
                visibility=landmark.visibility
            )
            total_visibility += landmark.visibility
        
        # 计算平均置信度
        avg_confidence = total_visibility / len(landmarks) if landmarks else 0.0
        
        return PoseResult(
            landmarks=landmarks,
            confidence=avg_confidence,
            image_width=width,
            image_height=height,
            raw_landmarks=results.pose_landmarks  # 保存原始对象
        )
    
    def draw_landmarks(
        self,
        frame: np.ndarray,
        pose_result: PoseResult,
        draw_connections: bool = True,
        highlight_shooting_arm: bool = True,
        shooting_hand: str = "right"
    ) -> np.ndarray:
        """
        在图像上绘制关键点和骨骼连接
        
        Args:
            frame: BGR 格式的图像
            pose_result: 姿态检测结果
            draw_connections: 是否绘制骨骼连接
            highlight_shooting_arm: 是否高亮投篮手臂
            shooting_hand: 投篮手 ("left" 或 "right")
            
        Returns:
            绘制后的图像
        """
        annotated = frame.copy()
        
        # 使用 MediaPipe 的绘制工具（使用原始的 landmarks 对象）
        if draw_connections and pose_result.raw_landmarks:
            self.mp_drawing.draw_landmarks(
                annotated,
                pose_result.raw_landmarks,
                self.mp_pose.POSE_CONNECTIONS,
                landmark_drawing_spec=self.mp_drawing_styles.get_default_pose_landmarks_style()
            )
        
        # 高亮投篮手臂
        if highlight_shooting_arm:
            if shooting_hand == "right":
                arm_landmarks = [
                    PoseLandmark.RIGHT_SHOULDER,
                    PoseLandmark.RIGHT_ELBOW,
                    PoseLandmark.RIGHT_WRIST,
                    PoseLandmark.RIGHT_INDEX
                ]
            else:
                arm_landmarks = [
                    PoseLandmark.LEFT_SHOULDER,
                    PoseLandmark.LEFT_ELBOW,
                    PoseLandmark.LEFT_WRIST,
                    PoseLandmark.LEFT_INDEX
                ]
            
            # 绘制高亮的投篮手臂
            points = []
            for idx in arm_landmarks:
                coords = pose_result.get_pixel_coords(idx)
                if coords:
                    points.append(coords)
                    # 绘制关键点
                    cv2.circle(annotated, coords, 8, (0, 255, 255), -1)  # 黄色
                    cv2.circle(annotated, coords, 10, (0, 200, 200), 2)
            
            # 绘制连接线
            for i in range(len(points) - 1):
                cv2.line(annotated, points[i], points[i + 1], (0, 255, 255), 3)
        
        return annotated
    
    def draw_angles(
        self,
        frame: np.ndarray,
        pose_result: PoseResult,
        angles: dict,
        shooting_hand: str = "right"
    ) -> np.ndarray:
        """
        在图像上绘制角度信息
        
        Args:
            frame: BGR 格式的图像
            pose_result: 姿态检测结果
            angles: 角度字典
            shooting_hand: 投篮手
            
        Returns:
            绘制后的图像
        """
        annotated = frame.copy()
        
        # 获取关键点位置
        if shooting_hand == "right":
            elbow_idx = PoseLandmark.RIGHT_ELBOW
            knee_idx = PoseLandmark.RIGHT_KNEE
        else:
            elbow_idx = PoseLandmark.LEFT_ELBOW
            knee_idx = PoseLandmark.LEFT_KNEE
        
        # 在肘部位置显示肘部角度
        elbow_coords = pose_result.get_pixel_coords(elbow_idx)
        if elbow_coords and "elbow_angle" in angles:
            text = f"Elbow: {angles['elbow_angle']:.1f}deg"
            cv2.putText(
                annotated, text,
                (elbow_coords[0] + 10, elbow_coords[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2
            )
        
        # 在膝盖位置显示膝盖角度
        knee_coords = pose_result.get_pixel_coords(knee_idx)
        if knee_coords and "knee_angle" in angles:
            text = f"Knee: {angles['knee_angle']:.1f}deg"
            cv2.putText(
                annotated, text,
                (knee_coords[0] + 10, knee_coords[1] + 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2
            )
        
        # 在图像顶部显示所有角度
        y_offset = 30
        for name, value in angles.items():
            if value is not None:
                text = f"{name}: {value:.1f}deg"
                cv2.putText(
                    annotated, text,
                    (10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1
                )
                y_offset += 25
        
        return annotated
    
    def get_shooting_landmarks(
        self,
        pose_result: PoseResult,
        shooting_hand: str = "right"
    ) -> dict:
        """
        获取投篮分析需要的关键点
        
        Args:
            pose_result: 姿态检测结果
            shooting_hand: 投篮手
            
        Returns:
            关键点字典
        """
        if shooting_hand == "right":
            mapping = {
                "shoulder": PoseLandmark.RIGHT_SHOULDER,
                "elbow": PoseLandmark.RIGHT_ELBOW,
                "wrist": PoseLandmark.RIGHT_WRIST,
                "index": PoseLandmark.RIGHT_INDEX,
                "hip": PoseLandmark.RIGHT_HIP,
                "knee": PoseLandmark.RIGHT_KNEE,
                "ankle": PoseLandmark.RIGHT_ANKLE,
                "opposite_shoulder": PoseLandmark.LEFT_SHOULDER,
                "opposite_hip": PoseLandmark.LEFT_HIP,
            }
        else:
            mapping = {
                "shoulder": PoseLandmark.LEFT_SHOULDER,
                "elbow": PoseLandmark.LEFT_ELBOW,
                "wrist": PoseLandmark.LEFT_WRIST,
                "index": PoseLandmark.LEFT_INDEX,
                "hip": PoseLandmark.LEFT_HIP,
                "knee": PoseLandmark.LEFT_KNEE,
                "ankle": PoseLandmark.LEFT_ANKLE,
                "opposite_shoulder": PoseLandmark.RIGHT_SHOULDER,
                "opposite_hip": PoseLandmark.RIGHT_HIP,
            }
        
        result = {}
        for name, idx in mapping.items():
            landmark = pose_result.get_landmark(idx)
            if landmark:
                result[name] = landmark
        
        return result
    
    def close(self):
        """释放资源"""
        self.pose.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
