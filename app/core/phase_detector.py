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
    prep_max_trunk_angle: float = 20.0      # 躯干角度 < 此值认为身体直立
    
    # 出手阶段
    release_min_elbow_angle: float = 150.0  # 肘部角度 > 此值认为手臂伸展
    release_min_shoulder_angle: float = 70.0  # 肩部角度 > 此值认为手臂抬高
    
    # 跟随阶段 (手腕高度开始下降)
    follow_wrist_drop_threshold: float = 0.02  # 手腕下降超过此值
    
    # 数据平滑
    smooth_window_size: int = 5  # 平滑窗口大小
    
    # 上升阶段
    wrist_rising_window: int = 5  # 手腕上升判断窗口大小
    wrist_rising_threshold: float = 0.02  # 手腕上升阈值
    
    # 出手阶段
    release_window: int = 7  # 出手判断窗口大小
    min_release_frames: int = 3  # 出手阶段最小帧数
    
    # 跟随阶段
    follow_min_frames: int = 5  # 跟随阶段最小帧数


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
        
        # 平滑后的数据
        self.angles_history: list[ShootingAngles] = []
        self.wrist_y_history: list[float] = []
        
        # 投篮检测状态
        self.shooting_started: bool = False
        self.follow_frames_count: int = 0
    
    def reset(self):
        """重置状态"""
        self.frame_history = []
        self.max_wrist_y = 1.0
        self.wrist_rising = False
        self.release_detected = False
        self.angles_history = []
        self.wrist_y_history = []
        self.shooting_started = False
        self.follow_frames_count = 0
    
    def _smooth_angles(self, current_angles: ShootingAngles) -> ShootingAngles:
        """
        平滑角度数据
        
        Args:
            current_angles: 当前角度
            
        Returns:
            平滑后的角度
        """
        self.angles_history.append(current_angles)
        window_size = self.thresholds.smooth_window_size
        
        if len(self.angles_history) > window_size:
            self.angles_history = self.angles_history[-window_size:]
        
        # 计算移动平均（过滤None值）
        def avg(values):
            valid = [v for v in values if v is not None]
            return sum(valid) / len(valid) if valid else 0.0
        
        def avg_or_none(values):
            valid = [v for v in values if v is not None]
            return sum(valid) / len(valid) if valid else None
        
        return ShootingAngles(
            elbow_angle=avg([a.elbow_angle for a in self.angles_history]),
            shoulder_angle=avg([a.shoulder_angle for a in self.angles_history]),
            knee_angle=avg_or_none([a.knee_angle for a in self.angles_history]),
            trunk_angle=avg([a.trunk_angle for a in self.angles_history]),
            wrist_angle=current_angles.wrist_angle,
            hip_angle=avg_or_none([a.hip_angle for a in self.angles_history])
        )
    
    def _smooth_wrist_y(self, current_wrist_y: float) -> float:
        """
        平滑手腕Y坐标
        
        Args:
            current_wrist_y: 当前手腕Y坐标
            
        Returns:
            平滑后的手腕Y坐标
        """
        self.wrist_y_history.append(current_wrist_y)
        window_size = self.thresholds.smooth_window_size
        
        if len(self.wrist_y_history) > window_size:
            self.wrist_y_history = self.wrist_y_history[-window_size:]
        
        return sum(self.wrist_y_history) / len(self.wrist_y_history)
    
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
        
        # 平滑数据
        smoothed_angles = self._smooth_angles(angles)
        smoothed_wrist_y = self._smooth_wrist_y(wrist_y)
        
        # 创建帧数据（使用平滑后的数据）
        frame_data = FrameData(
            frame_number=frame_number,
            timestamp=timestamp,
            angles=smoothed_angles,
            wrist_y=smoothed_wrist_y,
            confidence=confidence
        )
        
        # 判断阶段
        phase = self._determine_phase(smoothed_angles, smoothed_wrist_y)
        frame_data.phase = phase
        
        # 更新历史
        self.frame_history.append(frame_data)
        
        # 更新最高手腕位置
        if smoothed_wrist_y < self.max_wrist_y:
            self.max_wrist_y = smoothed_wrist_y
        
        return phase
    
    def _determine_phase(
        self,
        angles: ShootingAngles,
        wrist_y: float
    ) -> ShootingPhase:
        """
        根据角度和位置判断阶段
        
        判断逻辑:
        1. 准备阶段: 膝盖弯曲 + 肘部弯曲 + 躯干直立
        2. 上升阶段: 手腕 Y 坐标在上升 + 上升速度足够
        3. 出手阶段: 肘部接近伸直 + 手腕达到最高点 + 出手速度
        4. 跟随阶段: 手腕开始下降 + 持续下降
        """
        th = self.thresholds
        
        # 检查手腕运动趋势和速度
        is_wrist_rising = False
        is_wrist_falling = False
        wrist_rising_speed = 0.0
        
        if len(self.wrist_y_history) >= th.wrist_rising_window:
            recent_wrist_y = self.wrist_y_history[-th.wrist_rising_window:]
            if len(recent_wrist_y) >= 2:
                # 计算平均上升速度
                total_change = recent_wrist_y[-1] - recent_wrist_y[0]
                wrist_rising_speed = abs(total_change) / len(recent_wrist_y)
                
                # 判断上升或下降
                is_wrist_rising = total_change < -th.wrist_rising_threshold
                is_wrist_falling = total_change > th.wrist_rising_threshold
        
        # 检查是否达到最高点（手腕开始下降）
        at_peak = False
        if len(self.frame_history) >= th.release_window:
            recent = self.frame_history[-th.release_window:]
            wrist_positions = [f.wrist_y for f in recent if f.wrist_y is not None]
            if len(wrist_positions) >= th.release_window:
                mid = len(wrist_positions) // 2
                rising = wrist_positions[mid] < wrist_positions[0]
                falling = wrist_positions[-1] > wrist_positions[mid]
                at_peak = rising and falling
        
        # 自动重置检测：如果跟随阶段持续足够长，重置状态
        if self.release_detected and self.follow_frames_count >= th.follow_min_frames:
            # 检查是否开始新的投篮（手腕重新上升）
            if is_wrist_rising and wrist_rising_speed > 0.01:
                self.reset()
                self.shooting_started = True
                return ShootingPhase.PREPARATION
        
        # 跟随阶段判断
        if self.release_detected:
            self.follow_frames_count += 1
            # 独立判断：手腕持续下降
            if is_wrist_falling:
                return ShootingPhase.FOLLOW_THROUGH
            # 即使手腕暂时稳定，也认为是跟随阶段
            return ShootingPhase.FOLLOW_THROUGH
        
        # 出手阶段判断（降低条件要求）
        elbow_extended = angles.elbow_angle >= th.release_min_elbow_angle
        shoulder_raised = angles.shoulder_angle >= th.release_min_shoulder_angle
        
        # 增加出手速度判断
        is_releasing = False
        if at_peak or is_wrist_falling:
            # 手腕在最高点附近或开始下降
            if elbow_extended or shoulder_raised:
                # 只要肘部或肩部有一个满足条件，且手腕在下降
                is_releasing = True
        
        # 另一种出手判断：手腕上升后突然减速或开始下降
        if self.wrist_rising and (at_peak or is_wrist_falling):
            is_releasing = True
        
        if is_releasing:
            self.release_detected = True
            return ShootingPhase.RELEASE
        
        # 上升阶段判断（增加速度判断）
        if is_wrist_rising and not self.release_detected:
            # 手腕上升速度足够
            if wrist_rising_speed > 0.01:
                self.wrist_rising = True
                self.shooting_started = True
                return ShootingPhase.LIFTING
        
        # 准备阶段判断（增加躯干角度判断，使用and逻辑）
        # 检查关键点可见性（knee可能不在画面内）
        knee_bent = angles.knee_angle is not None and angles.knee_angle < th.prep_max_knee_angle
        elbow_bent = angles.elbow_angle is not None and angles.elbow_angle < th.prep_max_elbow_angle
        trunk_upright = angles.trunk_angle is not None and angles.trunk_angle < th.prep_max_trunk_angle
        
        # 至少膝盖或肘部弯曲，且躯干直立，且手腕未上升
        if (knee_bent or elbow_bent) and trunk_upright and not self.wrist_rising:
            self.shooting_started = True
            return ShootingPhase.PREPARATION
        
        # 如果手腕在下降但还没检测到出手（可能是出手检测延迟）
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
                # 如果膝盖不可见，使用中间帧
                frames_with_knee = [f for f in segment.frames if f.angles and f.angles.knee_angle is not None]
                if frames_with_knee:
                    min_knee_frame = min(frames_with_knee, key=lambda f: f.angles.knee_angle)
                    key_frames[ShootingPhase.PREPARATION] = min_knee_frame
                elif segment.frames:
                    # 膝盖不可见时，取中间帧
                    key_frames[ShootingPhase.PREPARATION] = segment.frames[len(segment.frames) // 2]
            
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
