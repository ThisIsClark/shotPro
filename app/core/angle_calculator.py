"""
Angle Calculator Module
计算投篮姿势相关的各种角度
"""

import numpy as np
from typing import Optional
from dataclasses import dataclass

from .pose_detector import Landmark, PoseResult, PoseLandmark


@dataclass
class ShootingAngles:
    """投篮相关角度（无默认值的字段必须放在有默认值字段之前）"""
    elbow_angle: float          # 肘部角度 (肩-肘-腕)
    shoulder_angle: float       # 肩部角度 (髋-肩-肘)
    trunk_angle: float          # 躯干倾斜角度 (相对垂直线)
    knee_angle: Optional[float] = None   # 膝盖角度 (髋-膝-踝)，下半身不可见时为 None
    wrist_angle: Optional[float] = None  # 手腕角度 (肘-腕-食指)
    hip_angle: Optional[float] = None   # 髋部角度 (肩-髋-膝)
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "elbow_angle": self.elbow_angle,
            "shoulder_angle": self.shoulder_angle,
            "knee_angle": self.knee_angle,
            "trunk_angle": self.trunk_angle,
            "wrist_angle": self.wrist_angle,
            "hip_angle": self.hip_angle,
        }


class AngleCalculator:
    """角度计算器"""
    
    @staticmethod
    def calculate_angle_3points(
        point1: np.ndarray,
        point2: np.ndarray,
        point3: np.ndarray
    ) -> float:
        """
        计算三个点形成的角度
        point2 是顶点（角的顶点）
        
        Args:
            point1: 第一个点 [x, y] 或 [x, y, z]
            point2: 顶点 [x, y] 或 [x, y, z]
            point3: 第三个点 [x, y] 或 [x, y, z]
            
        Returns:
            角度 (0-180度)
        """
        # 使用 2D 坐标计算 (忽略 z)
        p1 = np.array(point1[:2])
        p2 = np.array(point2[:2])
        p3 = np.array(point3[:2])
        
        # 计算向量
        vector1 = p1 - p2
        vector2 = p3 - p2
        
        # 计算向量模长
        norm1 = np.linalg.norm(vector1)
        norm2 = np.linalg.norm(vector2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        # 计算夹角余弦值
        cos_angle = np.dot(vector1, vector2) / (norm1 * norm2)
        
        # 限制在 [-1, 1] 范围内，避免数值误差
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        
        # 计算角度
        angle = np.degrees(np.arccos(cos_angle))
        
        return angle
    
    @staticmethod
    def calculate_angle_to_vertical(
        point1: np.ndarray,
        point2: np.ndarray
    ) -> float:
        """
        计算两点连线与垂直线的夹角
        
        Args:
            point1: 上方的点 [x, y]
            point2: 下方的点 [x, y]
            
        Returns:
            角度 (0-90度)，0度表示完全垂直
        """
        p1 = np.array(point1[:2])
        p2 = np.array(point2[:2])
        
        # 两点形成的向量
        vector = p1 - p2
        
        # 垂直向量 (向上)
        vertical = np.array([0, -1])
        
        # 计算夹角
        norm = np.linalg.norm(vector)
        if norm == 0:
            return 0.0
        
        cos_angle = np.dot(vector, vertical) / norm
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        
        angle = np.degrees(np.arccos(cos_angle))
        
        return angle
    
    @staticmethod
    def landmark_to_array(landmark: Landmark) -> np.ndarray:
        """将 Landmark 转换为 numpy 数组"""
        return np.array([landmark.x, landmark.y, landmark.z])
    
    def calculate_elbow_angle(
        self,
        shoulder: Landmark,
        elbow: Landmark,
        wrist: Landmark
    ) -> float:
        """
        计算肘部角度
        
        Args:
            shoulder: 肩部关键点
            elbow: 肘部关键点
            wrist: 手腕关键点
            
        Returns:
            肘部角度 (度)
        """
        return self.calculate_angle_3points(
            self.landmark_to_array(shoulder),
            self.landmark_to_array(elbow),
            self.landmark_to_array(wrist)
        )
    
    def calculate_shoulder_angle(
        self,
        hip: Landmark,
        shoulder: Landmark,
        elbow: Landmark
    ) -> float:
        """
        计算肩部角度（手臂抬起的角度）
        
        Args:
            hip: 髋部关键点
            shoulder: 肩部关键点
            elbow: 肘部关键点
            
        Returns:
            肩部角度 (度)
        """
        return self.calculate_angle_3points(
            self.landmark_to_array(hip),
            self.landmark_to_array(shoulder),
            self.landmark_to_array(elbow)
        )
    
    def calculate_knee_angle(
        self,
        hip: Landmark,
        knee: Landmark,
        ankle: Landmark
    ) -> float:
        """
        计算膝盖角度
        
        Args:
            hip: 髋部关键点
            knee: 膝盖关键点
            ankle: 脚踝关键点
            
        Returns:
            膝盖角度 (度)
        """
        return self.calculate_angle_3points(
            self.landmark_to_array(hip),
            self.landmark_to_array(knee),
            self.landmark_to_array(ankle)
        )
    
    def calculate_trunk_angle(
        self,
        shoulder: Landmark,
        hip: Landmark
    ) -> float:
        """
        计算躯干倾斜角度
        
        Args:
            shoulder: 肩部关键点
            hip: 髋部关键点
            
        Returns:
            躯干倾斜角度 (度)，0表示完全直立
        """
        return self.calculate_angle_to_vertical(
            self.landmark_to_array(shoulder),
            self.landmark_to_array(hip)
        )
    
    def calculate_wrist_angle(
        self,
        elbow: Landmark,
        wrist: Landmark,
        index: Landmark
    ) -> float:
        """
        计算手腕角度
        
        Args:
            elbow: 肘部关键点
            wrist: 手腕关键点
            index: 食指关键点
            
        Returns:
            手腕角度 (度)
        """
        return self.calculate_angle_3points(
            self.landmark_to_array(elbow),
            self.landmark_to_array(wrist),
            self.landmark_to_array(index)
        )
    
    def calculate_hip_angle(
        self,
        shoulder: Landmark,
        hip: Landmark,
        knee: Landmark
    ) -> float:
        """
        计算髋部角度
        
        Args:
            shoulder: 肩部关键点
            hip: 髋部关键点
            knee: 膝盖关键点
            
        Returns:
            髋部角度 (度)
        """
        return self.calculate_angle_3points(
            self.landmark_to_array(shoulder),
            self.landmark_to_array(hip),
            self.landmark_to_array(knee)
        )
    
    def calculate_all_angles(
        self,
        pose_result: PoseResult,
        shooting_hand: str = "right"
    ) -> Optional[ShootingAngles]:
        """
        计算所有投篮相关角度
        
        Args:
            pose_result: 姿态检测结果
            shooting_hand: 投篮手 ("left" 或 "right")
            
        Returns:
            ShootingAngles 或 None
        """
        # 获取关键点索引
        if shooting_hand == "right":
            shoulder_idx = PoseLandmark.RIGHT_SHOULDER
            elbow_idx = PoseLandmark.RIGHT_ELBOW
            wrist_idx = PoseLandmark.RIGHT_WRIST
            index_idx = PoseLandmark.RIGHT_INDEX
            hip_idx = PoseLandmark.RIGHT_HIP
            knee_idx = PoseLandmark.RIGHT_KNEE
            ankle_idx = PoseLandmark.RIGHT_ANKLE
        else:
            shoulder_idx = PoseLandmark.LEFT_SHOULDER
            elbow_idx = PoseLandmark.LEFT_ELBOW
            wrist_idx = PoseLandmark.LEFT_WRIST
            index_idx = PoseLandmark.LEFT_INDEX
            hip_idx = PoseLandmark.LEFT_HIP
            knee_idx = PoseLandmark.LEFT_KNEE
            ankle_idx = PoseLandmark.LEFT_ANKLE
        
        # 获取关键点
        shoulder = pose_result.get_landmark(shoulder_idx)
        elbow = pose_result.get_landmark(elbow_idx)
        wrist = pose_result.get_landmark(wrist_idx)
        index = pose_result.get_landmark(index_idx)
        hip = pose_result.get_landmark(hip_idx)
        knee = pose_result.get_landmark(knee_idx)
        ankle = pose_result.get_landmark(ankle_idx)
        
        # 可见性阈值
        min_visibility = 0.5
        
        # 检查核心上半身关键点（肩、肘、腕必须可见）
        upper_body_visible = (
            shoulder and shoulder.visibility >= min_visibility and
            elbow and elbow.visibility >= min_visibility and
            wrist and wrist.visibility >= min_visibility and
            hip and hip.visibility >= min_visibility
        )
        
        # 如果上半身不可见，无法分析投篮动作
        if not upper_body_visible:
            return None
        
        # 部分计算角度（根据可见性）
        elbow_angle = self.calculate_elbow_angle(shoulder, elbow, wrist)
        shoulder_angle = self.calculate_shoulder_angle(hip, shoulder, elbow)
        trunk_angle = self.calculate_trunk_angle(shoulder, hip)
        
        # 膝盖角度：需要hip, knee, ankle都可见
        knee_angle = None
        if (knee and knee.visibility >= min_visibility and 
            ankle and ankle.visibility >= min_visibility):
            knee_angle = self.calculate_knee_angle(hip, knee, ankle)
        
        # 髋部角度：需要knee可见
        hip_angle = None
        if knee and knee.visibility >= min_visibility:
            hip_angle = self.calculate_hip_angle(shoulder, hip, knee)
        
        # 手腕角度：需要index可见
        wrist_angle = None
        if index and index.visibility >= min_visibility:
            wrist_angle = self.calculate_wrist_angle(elbow, wrist, index)
        
        return ShootingAngles(
            elbow_angle=elbow_angle,
            shoulder_angle=shoulder_angle,
            knee_angle=knee_angle,
            trunk_angle=trunk_angle,
            wrist_angle=wrist_angle,
            hip_angle=hip_angle
        )
    
    def smooth_angles(
        self,
        angles_history: list[ShootingAngles],
        window_size: int = 5
    ) -> ShootingAngles:
        """
        使用移动平均平滑角度数据
        
        Args:
            angles_history: 历史角度数据
            window_size: 窗口大小
            
        Returns:
            平滑后的角度
        """
        if len(angles_history) == 0:
            raise ValueError("angles_history cannot be empty")
        
        if len(angles_history) < window_size:
            window_size = len(angles_history)
        
        recent = angles_history[-window_size:]
        
        def avg_with_none(values):
            valid = [v for v in values if v is not None]
            return sum(valid) / len(valid) if valid else None
        
        return ShootingAngles(
            elbow_angle=avg_with_none([a.elbow_angle for a in recent]) or 0.0,
            shoulder_angle=avg_with_none([a.shoulder_angle for a in recent]) or 0.0,
            knee_angle=avg_with_none([a.knee_angle for a in recent]),
            trunk_angle=avg_with_none([a.trunk_angle for a in recent]) or 0.0,
            wrist_angle=avg_with_none([a.wrist_angle for a in recent]),
            hip_angle=avg_with_none([a.hip_angle for a in recent])
        )
