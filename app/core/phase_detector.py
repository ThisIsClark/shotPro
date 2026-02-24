"""
Phase Detector Module
检测投篮的各个阶段
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

from .angle_calculator import ShootingAngles
from .pose_detector import PoseResult, Landmark


class ShootingPhase(str, Enum):
    """投篮阶段"""
    UNKNOWN = "unknown"              # 未知
    PREPARATION = "preparation"      # 准备阶段: 持球、屈膝蓄力
    LIFTING = "lifting"              # 上升阶段: 手臂上抬
    RELEASE = "release"              # 出手阶段: 最高点出手
    FOLLOW_THROUGH = "follow_through"  # 跟随阶段: 出手后保持


@dataclass
class PhaseThresholds:
    """阶段检测阈值"""
    # 准备阶段
    prep_max_knee_angle: float = 130.0      # 膝盖角度 < 此值认为在下蹲
    prep_max_elbow_angle: float = 110.0     # 肘部角度 < 此值认为手臂未展开
    
    # 出手阶段
    release_min_elbow_angle: float = 150.0  # 肘部角度 > 此值认为手臂伸展
    release_min_shoulder_angle: float = 70.0  # 肩部角度 > 此值认为手臂抬高
    
    # 跟随阶段 (手腕高度开始下降)
    follow_wrist_drop_threshold: float = 0.02  # 手腕下降超过此值


@dataclass
class FrameData:
    """单帧数据"""
    frame_number: int
    timestamp: float  # 秒
    angles: Optional[ShootingAngles] = None
    wrist_y: Optional[float] = None  # 手腕 Y 坐标 (归一化)
    phase: ShootingPhase = ShootingPhase.UNKNOWN
    confidence: float = 0.0


@dataclass
class PhaseSegment:
    """阶段片段"""
    phase: ShootingPhase
    start_frame: int
    end_frame: int
    start_time: float
    end_time: float
    frames: list[FrameData] = field(default_factory=list)
    
    @property
    def duration(self) -> float:
        """阶段持续时间（秒）"""
        return self.end_time - self.start_time
    
    @property
    def frame_count(self) -> int:
        """帧数"""
        return self.end_frame - self.start_frame + 1


class PhaseDetector:
    """投篮阶段检测器"""
    
    def __init__(self, thresholds: Optional[PhaseThresholds] = None):
        """
        初始化阶段检测器
        
        Args:
            thresholds: 检测阈值，如果为 None 则使用默认值
        """
        self.thresholds = thresholds or PhaseThresholds()
        
        # 历史数据用于状态跟踪
        self.frame_history: list[FrameData] = []
        self.max_wrist_y: float = 1.0  # 最高手腕位置 (y 值越小越高)
        self.wrist_rising: bool = False
        self.release_detected: bool = False
    
    def reset(self):
        """重置状态"""
        self.frame_history = []
        self.max_wrist_y = 1.0
        self.wrist_rising = False
        self.release_detected = False
    
    def detect_phase(
        self,
        frame_number: int,
        timestamp: float,
        angles: ShootingAngles,
        wrist_landmark: Landmark,
        confidence: float = 1.0
    ) -> ShootingPhase:
        """
        检测当前帧的投篮阶段
        
        Args:
            frame_number: 帧号
            timestamp: 时间戳（秒）
            angles: 当前帧的角度数据
            wrist_landmark: 手腕关键点
            confidence: 检测置信度
            
        Returns:
            当前阶段
        """
        wrist_y = wrist_landmark.y
        
        # 创建帧数据
        frame_data = FrameData(
            frame_number=frame_number,
            timestamp=timestamp,
            angles=angles,
            wrist_y=wrist_y,
            confidence=confidence
        )
        
        # 判断阶段
        phase = self._determine_phase(angles, wrist_y)
        frame_data.phase = phase
        
        # 更新历史
        self.frame_history.append(frame_data)
        
        # 更新最高手腕位置
        if wrist_y < self.max_wrist_y:
            self.max_wrist_y = wrist_y
        
        return phase
    
    def _determine_phase(
        self,
        angles: ShootingAngles,
        wrist_y: float
    ) -> ShootingPhase:
        """
        根据角度和位置判断阶段
        
        判断逻辑:
        1. 准备阶段: 膝盖弯曲 + 肘部弯曲
        2. 上升阶段: 手腕 Y 坐标在上升
        3. 出手阶段: 肘部接近伸直 + 手腕达到最高点
        4. 跟随阶段: 手腕开始下降
        """
        th = self.thresholds
        
        # 检查手腕是否在上升
        is_wrist_rising = False
        is_wrist_falling = False
        
        if len(self.frame_history) >= 3:
            recent_wrist_y = [f.wrist_y for f in self.frame_history[-3:] if f.wrist_y is not None]
            if len(recent_wrist_y) >= 2:
                # Y 坐标减小意味着手腕在上升（屏幕坐标系 Y 轴向下）
                is_wrist_rising = recent_wrist_y[-1] < recent_wrist_y[0] - 0.01
                is_wrist_falling = recent_wrist_y[-1] > recent_wrist_y[0] + 0.01
        
        # 如果已经检测到出手，后续都是跟随阶段
        if self.release_detected:
            return ShootingPhase.FOLLOW_THROUGH
        
        # 判断是否是出手阶段
        elbow_extended = angles.elbow_angle >= th.release_min_elbow_angle
        shoulder_raised = angles.shoulder_angle >= th.release_min_shoulder_angle
        
        # 检查是否达到最高点（手腕开始下降）
        at_peak = False
        if len(self.frame_history) >= 5:
            recent = self.frame_history[-5:]
            wrist_positions = [f.wrist_y for f in recent if f.wrist_y is not None]
            if len(wrist_positions) >= 5:
                # 前几帧在上升，后几帧开始下降
                mid = len(wrist_positions) // 2
                rising = wrist_positions[mid] < wrist_positions[0]
                falling = wrist_positions[-1] > wrist_positions[mid]
                at_peak = rising and falling
        
        if elbow_extended and shoulder_raised and (at_peak or is_wrist_falling):
            self.release_detected = True
            return ShootingPhase.RELEASE
        
        # 判断是否是上升阶段
        if is_wrist_rising and not self.release_detected:
            self.wrist_rising = True
            return ShootingPhase.LIFTING
        
        # 判断是否是准备阶段
        knee_bent = angles.knee_angle < th.prep_max_knee_angle
        elbow_bent = angles.elbow_angle < th.prep_max_elbow_angle
        
        if (knee_bent or elbow_bent) and not self.wrist_rising:
            return ShootingPhase.PREPARATION
        
        # 如果手腕在下降但还没检测到出手
        if is_wrist_falling and self.wrist_rising:
            self.release_detected = True
            return ShootingPhase.RELEASE
        
        # 默认返回准备阶段或上升阶段
        if self.wrist_rising:
            return ShootingPhase.LIFTING
        
        return ShootingPhase.PREPARATION
    
    def get_phase_segments(self) -> list[PhaseSegment]:
        """
        获取阶段划分结果
        
        Returns:
            阶段片段列表
        """
        if not self.frame_history:
            return []
        
        segments = []
        current_phase = None
        current_start_frame = 0
        current_start_time = 0.0
        current_frames = []
        
        for frame_data in self.frame_history:
            if current_phase is None:
                current_phase = frame_data.phase
                current_start_frame = frame_data.frame_number
                current_start_time = frame_data.timestamp
                current_frames = [frame_data]
            elif frame_data.phase != current_phase:
                # 保存当前阶段
                segments.append(PhaseSegment(
                    phase=current_phase,
                    start_frame=current_start_frame,
                    end_frame=frame_data.frame_number - 1,
                    start_time=current_start_time,
                    end_time=frame_data.timestamp,
                    frames=current_frames
                ))
                
                # 开始新阶段
                current_phase = frame_data.phase
                current_start_frame = frame_data.frame_number
                current_start_time = frame_data.timestamp
                current_frames = [frame_data]
            else:
                current_frames.append(frame_data)
        
        # 保存最后一个阶段
        if current_phase is not None and self.frame_history:
            last_frame = self.frame_history[-1]
            segments.append(PhaseSegment(
                phase=current_phase,
                start_frame=current_start_frame,
                end_frame=last_frame.frame_number,
                start_time=current_start_time,
                end_time=last_frame.timestamp,
                frames=current_frames
            ))
        
        return segments
    
    def get_key_frames(self) -> dict[ShootingPhase, Optional[FrameData]]:
        """
        获取各阶段的关键帧
        
        Returns:
            每个阶段的代表帧
        """
        key_frames = {
            ShootingPhase.PREPARATION: None,
            ShootingPhase.LIFTING: None,
            ShootingPhase.RELEASE: None,
            ShootingPhase.FOLLOW_THROUGH: None
        }
        
        segments = self.get_phase_segments()
        
        for segment in segments:
            if segment.phase == ShootingPhase.UNKNOWN:
                continue
            
            if segment.phase == ShootingPhase.PREPARATION:
                # 准备阶段取膝盖角度最小的帧（下蹲最深）
                min_knee_frame = min(
                    segment.frames,
                    key=lambda f: f.angles.knee_angle if f.angles else 180
                )
                key_frames[ShootingPhase.PREPARATION] = min_knee_frame
            
            elif segment.phase == ShootingPhase.LIFTING:
                # 上升阶段取中间帧
                mid_idx = len(segment.frames) // 2
                key_frames[ShootingPhase.LIFTING] = segment.frames[mid_idx]
            
            elif segment.phase == ShootingPhase.RELEASE:
                # 出手阶段取手腕最高的帧
                min_wrist_frame = min(
                    segment.frames,
                    key=lambda f: f.wrist_y if f.wrist_y else 1.0
                )
                key_frames[ShootingPhase.RELEASE] = min_wrist_frame
            
            elif segment.phase == ShootingPhase.FOLLOW_THROUGH:
                # 跟随阶段取第一帧
                if segment.frames:
                    key_frames[ShootingPhase.FOLLOW_THROUGH] = segment.frames[0]
        
        return key_frames
    
    def get_release_frame(self) -> Optional[FrameData]:
        """获取出手帧"""
        key_frames = self.get_key_frames()
        return key_frames.get(ShootingPhase.RELEASE)
