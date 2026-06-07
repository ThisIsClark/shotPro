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
    # 关键帧（4帧版本 - 发力连贯性检测）
    SYNC_FRAME_1 = "sync_frame_1"      # 手脚同步检测帧1：沉球点（手腕最低点后上升）
    SYNC_FRAME_2 = "sync_frame_2"      # 手脚同步检测帧2：手上升后（沉球点后N帧）
    MAX_HOLD_FRAME = "max_hold_frame"  # 发力脱节检测帧1：最高持球点（手腕高+肘角未伸展）
    RELEASE_FRAME = "release_frame"    # 发力脱节检测帧2：出手点（手腕最高+肘角伸展）


@dataclass
class PhaseThresholds:
    """阶段检测阈值"""
    # 准备阶段
    prep_max_knee_angle: float = 130.0      # 膝盖角度 < 此值认为在下蹲
    prep_max_elbow_angle: float = 90.0      # 肘部角度 < 此值认为手臂未展开（降低阈值）
    prep_max_trunk_angle: float = 20.0      # 躯干角度 < 此值认为身体直立
    prep_max_shoulder_angle: float = 45.0   # 肩部角度 < 此值认为手臂未抬起（新增）
    
    # 出手阶段
    release_min_elbow_angle: float = 150.0  # 肘部角度 > 此值认为手臂伸展
    release_min_shoulder_angle: float = 70.0  # 肩部角度 > 此值认为手臂抬高
    
    # 跟随阶段 (手腕高度开始下降)
    follow_wrist_drop_threshold: float = 0.02  # 手腕下降超过此值
    
    # 数据平滑
    smooth_window_size: int = 5  # 平滑窗口大小
    
    # 上升阶段
    wrist_rising_window: int = 3  # 手腕上升判断窗口大小（减小窗口以提高灵敏度）
    wrist_rising_threshold: float = 0.005  # 手腕上升阈值（降低阈值以更早检测上升）
    
    # 出手阶段
    release_window: int = 5  # 出手判断窗口大小（减小窗口）
    min_release_frames: int = 2  # 出手阶段最小帧数
    
    # 跟随阶段
    follow_min_frames: int = 5  # 跟随阶段最小帧数


@dataclass
class FrameData:
    """单帧数据"""
    frame_number: int
    timestamp: float  # 秒
    angles: Optional[ShootingAngles] = None
    wrist_y: Optional[float] = None  # 手腕 Y 坐标 (归一化，平滑后)
    raw_wrist_y: Optional[float] = None  # 手腕 Y 坐标 (归一化，原始未平滑) - 用于关键帧检测
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
    
    def _smooth_angles(self, current_angles: Optional[ShootingAngles]) -> Optional[ShootingAngles]:
        """
        平滑角度数据

        Args:
            current_angles: 当前角度（可为 None）

        Returns:
            平滑后的角度（可为 None）
        """
        if current_angles is None:
            return None

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
            angles: 当前帧的角度数据（可为 None）
            wrist_landmark: 手腕关键点
            confidence: 检测置信度

        Returns:
            当前阶段
        """
        wrist_y = wrist_landmark.y

        # 平滑数据
        smoothed_angles = self._smooth_angles(angles) if angles else None
        smoothed_wrist_y = self._smooth_wrist_y(wrist_y)

        # 创建帧数据（保存原始和平滑后的手腕Y值）
        # 即使角度为 None 也保存帧（用于关键帧检测）
        frame_data = FrameData(
            frame_number=frame_number,
            timestamp=timestamp,
            angles=smoothed_angles,
            wrist_y=smoothed_wrist_y,  # 平滑后的值（用于阶段判断）
            raw_wrist_y=wrist_y,  # 原始值（用于关键帧检测）
            confidence=confidence
        )

        # 判断阶段（如果角度可用）
        if smoothed_angles and smoothed_wrist_y:
            phase = self._determine_phase(smoothed_angles, smoothed_wrist_y)
            frame_data.phase = phase
        else:
            frame_data.phase = ShootingPhase.UNKNOWN

        # 更新历史（保存所有帧，用于关键帧检测）
        self.frame_history.append(frame_data)

        # 更新最高手腕位置（使用平滑值）
        if smoothed_wrist_y < self.max_wrist_y:
            self.max_wrist_y = smoothed_wrist_y

        return frame_data.phase
    
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
        prev_phase = self.frame_history[-1].phase if self.frame_history else ShootingPhase.UNKNOWN
        
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
        # 注意：不清空 frame_history，因为关键帧检测需要完整的历史数据
        if self.release_detected and self.follow_frames_count >= th.follow_min_frames:
            # 检查是否开始新的投篮（手腕重新上升）
            if is_wrist_rising and wrist_rising_speed > 0.01:
                # 只重置状态标志，不清空历史数据
                self.max_wrist_y = 1.0
                self.wrist_rising = False
                self.release_detected = False
                self.shooting_started = True
                self.follow_frames_count = 0
                # 不调用 self.reset()，因为会清空 frame_history
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
            # 优化：降低进入上升阶段的门槛，只要有明显上升趋势即可
            if wrist_rising_speed > 0.005:  # 降低速度阈值
                self.wrist_rising = True
                self.shooting_started = True
                return ShootingPhase.LIFTING
        
        # 准备阶段判断（增加躯干角度判断，使用and逻辑）
        # 检查关键点可见性（knee可能不在画面内）
        knee_bent = angles.knee_angle is not None and angles.knee_angle < th.prep_max_knee_angle
        elbow_bent = angles.elbow_angle is not None and angles.elbow_angle < th.prep_max_elbow_angle
        trunk_upright = angles.trunk_angle is not None and angles.trunk_angle < th.prep_max_trunk_angle
        arm_down = angles.shoulder_angle is not None and angles.shoulder_angle < th.prep_max_shoulder_angle  # 手臂低位

        # 至少膝盖或肘部弯曲，且躯干直立，且手臂低位，且手腕未上升
        # 优化：如果手腕已经在上升（即使速度不快），也不应判为准备阶段
        # 关键：手臂必须低位（肩角小）才是真正的准备阶段
        if (knee_bent or elbow_bent) and trunk_upright and arm_down and not is_wrist_rising and prev_phase not in (ShootingPhase.LIFTING, ShootingPhase.RELEASE, ShootingPhase.FOLLOW_THROUGH):
            self.shooting_started = True
            return ShootingPhase.PREPARATION
        
        # 如果手腕在下降但还没检测到出手（可能是出手检测延迟）
        if is_wrist_falling and self.wrist_rising:
            self.release_detected = True
            return ShootingPhase.RELEASE

        # 默认返回准备阶段或上升阶段
        if self.wrist_rising or (prev_phase == ShootingPhase.LIFTING and not self.release_detected):
            return ShootingPhase.LIFTING

        # 如果手臂已经抬起（肩角大），不应该返回 PREPARATION
        if angles.shoulder_angle is not None and angles.shoulder_angle > th.prep_max_shoulder_angle:
            # 手臂已抬起，根据手腕运动判断
            if is_wrist_rising:
                return ShootingPhase.LIFTING
            elif is_wrist_falling:
                return ShootingPhase.RELEASE
            else:
                # 手腕稳定但手臂抬起，可能是上升或出手
                if angles.elbow_angle > 110:
                    return ShootingPhase.RELEASE
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
        获取关键帧（4帧版本 - 发力连贯性检测）

        关键帧定义：
        - SYNC_FRAME_1 (沉球点): 手腕Y坐标最大值（物理位置最低）后开始上升的那一帧
          用于检测手脚同步性的基准点
        - SYNC_FRAME_2 (手上升后): 沉球点后3-5帧，用于检测手上升时膝盖状态
          如果 SYNC_FRAME_2.knee_angle < SYNC_FRAME_1.knee_angle → 手快脚慢
        - MAX_HOLD_FRAME (最高持球点): 手腕Y坐标最小值附近且肘角<160°的帧
          用于检测发力脱节：如果膝盖已伸直但手还在等待出手
        - RELEASE_FRAME (出手点): 手腕Y坐标最小值且肘角伸展（>160°）
          代表出手瞬间

        Returns:
            sync_frame_1, sync_frame_2, max_hold_frame, release_frame 四个关键帧
        """
        key_frames = {
            ShootingPhase.SYNC_FRAME_1: None,
            ShootingPhase.SYNC_FRAME_2: None,
            ShootingPhase.MAX_HOLD_FRAME: None,
            ShootingPhase.RELEASE_FRAME: None
        }

        if not self.frame_history:
            return key_frames

        # 获取所有有效帧（有手腕Y坐标和角度数据），按帧号排序
        valid_frames = sorted([
            f for f in self.frame_history
            if (f.raw_wrist_y is not None or f.wrist_y is not None) and f.angles is not None
        ], key=lambda f: f.frame_number)

        if not valid_frames:
            return key_frames

        # 辅助函数：获取手腕Y值（优先使用原始值，用于关键帧检测）
        def get_wrist_y(frame):
            return frame.raw_wrist_y if frame.raw_wrist_y is not None else frame.wrist_y

        # ===== 投篮动作关键帧检测逻辑 =====
        # 核心思路：
        # 1. 手腕Y值下降 = 物理位置上升（投篮动作）
        # 2. 手腕Y值上升 = 物理位置下降（出手后下落或沉球）
        # 3. 投篮过程：准备(手腕稳定) -> 沉球(手腕下降) -> 上升(手腕上升) -> 出手(手腕最高) -> 跟随(手腕下落)

        # ===== 找真正的手腕最高点（投篮动作的最高位置）=====
        # 方法：找手腕Y值曲线的第一个局部最小点（物理最高位置）

        # 计算每个帧的Y值变化趋势（使用原始值）
        wrist_trends = []
        for i in range(1, len(valid_frames) - 1):
            prev = valid_frames[i - 1]
            curr = valid_frames[i]
            next_f = valid_frames[i + 1]

            # 计算趋势：下降(-)、稳定(0)、上升(+)
            prev_diff = get_wrist_y(curr) - get_wrist_y(prev)  # Y值变化：负=上升，正=下降
            next_diff = get_wrist_y(next_f) - get_wrist_y(curr)

            # 判断是否是局部最小点（物理最高位置）
            # 特征：之前在下降(Y值减小)，之后开始上升(Y值增大)
            # 或者：之前下降明显，之后下降变缓或持平
            is_rising_before = prev_diff < 0  # 之前在上升（Y值减小）
            is_falling_after = next_diff > 0  # 之后开始下降（Y值增大）

            wrist_trends.append({
                'frame': curr,
                'prev_diff': prev_diff,
                'next_diff': next_diff,
                'is_peak_candidate': is_rising_before and (is_falling_after or next_diff >= 0)
            })

        print(f"[PhaseDetector] 手腕趋势分析:")
        for t in wrist_trends:
            fn = t['frame'].frame_number
            if t['is_peak_candidate']:
                print(f"  frame#{fn}: 峰值候选! prev_diff={t['prev_diff']:.4f}, next_diff={t['next_diff']:.4f}")

        # 找第一个峰值候选点（最早达到的最高位置）
        peak_candidates = [t for t in wrist_trends if t['is_peak_candidate']]

        true_peak_fn = None
        if peak_candidates:
            # 取手腕Y值最小的峰值候选点（物理位置最高的那个）
            best_peak = min(peak_candidates, key=lambda t: get_wrist_y(t['frame']))
            true_peak_fn = best_peak['frame'].frame_number
            min_wrist_y = get_wrist_y(best_peak['frame'])
            min_wrist_y_frame = best_peak['frame']
            print(f"[PhaseDetector] 真正的手腕最高点: frame#{true_peak_fn}, wrist_y={min_wrist_y:.4f}")
        else:
            # 如果没找到转折点，用全局最小Y值点，但要限制在视频的前半部分
            # 避免 stray 到出手后的稳定阶段
            half_frames = valid_frames[:len(valid_frames)//2 + len(valid_frames)//4]
            min_wrist_y_frame = min(half_frames, key=lambda f: get_wrist_y(f))
            min_wrist_y = get_wrist_y(min_wrist_y_frame)
            true_peak_fn = min_wrist_y_frame.frame_number
            print(f"[PhaseDetector] 使用前半部分最小Y值点: frame#{true_peak_fn}")

        # ===== 1. 检测沉球点 (SYNC_FRAME_1) =====
        # 沉球点：手腕下降到最低后开始上升的转折点
        # 在最高点之前寻找

        frames_before_peak = [
            f for f in valid_frames
            if f.frame_number < true_peak_fn
        ]

        sync_frame_1 = None
        if len(frames_before_peak) >= 5:
            # 在最高点之前找手腕Y值最大点（物理最低点）作为沉球候选
            # 注意：要找手腕先下降后上升的转折点（使用原始值）
            for i in range(3, len(frames_before_peak) - 2):
                prev2 = frames_before_peak[i - 2]
                prev1 = frames_before_peak[i - 1]
                curr = frames_before_peak[i]
                next1 = frames_before_peak[i + 1]
                next2 = frames_before_peak[i + 2]

                # 检查是否是"沉球后上升"的模式（使用原始值）
                # 特征：Y值先增大(手腕下降)，然后减小(手腕上升)
                if get_wrist_y(prev2) < get_wrist_y(prev1) and get_wrist_y(prev1) <= get_wrist_y(curr):
                    # 找到了下降到最低的区域
                    if get_wrist_y(curr) > get_wrist_y(next1):
                        # 确认开始上升了
                        sync_frame_1 = curr
                        print(f"[PhaseDetector] 找到沉球转折点: frame#{curr.frame_number}, wrist_y={get_wrist_y(curr):.4f}")
                        break

            # 如果没找到明显的转折点，取最高点前手腕Y值最大点（使用原始值）
            if sync_frame_1 is None:
                # 在最高点前1/3范围内找Y值最大点（排除准备阶段的稳定期）
                search_start = len(frames_before_peak) // 3
                search_frames = frames_before_peak[search_start:]
                if search_frames:
                    local_max = max(search_frames, key=lambda f: get_wrist_y(f))
                    sync_frame_1 = local_max
                    print(f"[PhaseDetector] 使用局部最大Y值点作为沉球点: frame#{local_max.frame_number}")

        key_frames[ShootingPhase.SYNC_FRAME_1] = sync_frame_1

        if sync_frame_1 and sync_frame_1.angles:
            knee_str = f"{sync_frame_1.angles.knee_angle:.1f}" if sync_frame_1.angles.knee_angle else "N/A"
            print(f"[PhaseDetector] SYNC_FRAME_1 keyframe: frame#{sync_frame_1.frame_number}, "
                  f"wrist_y={get_wrist_y(sync_frame_1):.4f}, "
                  f"elbow={sync_frame_1.angles.elbow_angle:.1f}°, "
                  f"knee={knee_str}°")

        # ===== 2. 检测手上升后 (SYNC_FRAME_2) =====
        # 沉球点后3-5帧（取沉球点后第4帧，约0.1秒）
        if sync_frame_1:
            target_frame_num = sync_frame_1.frame_number + 4
            # 找目标帧附近的有效帧（允许±2帧误差）
            candidate_frames = [
                f for f in valid_frames
                if abs(f.frame_number - target_frame_num) <= 2
                and f.frame_number > sync_frame_1.frame_number
            ]
            if candidate_frames:
                sync_frame_2 = candidate_frames[0]  # 取最接近的帧
                key_frames[ShootingPhase.SYNC_FRAME_2] = sync_frame_2

                if sync_frame_2.angles:
                    knee_str = f"{sync_frame_2.angles.knee_angle:.1f}" if sync_frame_2.angles.knee_angle else "N/A"
                    print(f"[PhaseDetector] SYNC_FRAME_2 keyframe: frame#{sync_frame_2.frame_number}, "
                          f"wrist_y={sync_frame_2.wrist_y:.4f}, "
                          f"knee={knee_str}°")

        # ===== 3. 检测最高持球点 (MAX_HOLD_FRAME) =====
        # 最高持球点：手腕最高位置附近，肘角未伸展的帧
        # 表示出手前手臂折叠最紧的状态

        max_hold_frame = None
        # 在真正的手腕最高点附近寻找（±5帧范围内）
        peak_near_frames = [
            f for f in valid_frames
            if abs(f.frame_number - true_peak_fn) <= 5
        ]

        # 先找肘角未伸展的帧（<160°）
        frames_with_unextended_elbow = [
            f for f in peak_near_frames
            if f.angles and f.angles.elbow_angle < 160
        ]

        if frames_with_unextended_elbow:
            # 取肘角最小的帧（手臂折叠最紧）
            # 且要确保在最高点之前或附近
            frames_before_or_near_peak = [
                f for f in frames_with_unextended_elbow
                if f.frame_number <= true_peak_fn
            ]
            if frames_before_or_near_peak:
                max_hold_frame = min(frames_before_or_near_peak, key=lambda f: f.angles.elbow_angle)
            else:
                max_hold_frame = min(frames_with_unextended_elbow, key=lambda f: f.angles.elbow_angle)
        else:
            # 如果没有肘角未伸展的帧，取最高点前最近的一帧
            if frames_before_peak:
                max_hold_frame = frames_before_peak[-1]

        key_frames[ShootingPhase.MAX_HOLD_FRAME] = max_hold_frame

        if max_hold_frame and max_hold_frame.angles:
            knee_str = f"{max_hold_frame.angles.knee_angle:.1f}" if max_hold_frame.angles.knee_angle else "N/A"
            print(f"[PhaseDetector] MAX_HOLD_FRAME keyframe: frame#{max_hold_frame.frame_number}, "
                  f"wrist_y={max_hold_frame.wrist_y:.4f}, "
                  f"elbow={max_hold_frame.angles.elbow_angle:.1f}°, "
                  f"knee={knee_str}°")

        # ===== 4. 检测出手点 (RELEASE_FRAME) =====
        # 出手点：手腕最高位置附近，肘角伸展（>160°）的帧
        # 表示手臂完全伸展的出手瞬间

        release_frame = None
        frames_with_extended_elbow = [
            f for f in peak_near_frames
            if f.angles and f.angles.elbow_angle >= 160
        ]

        if frames_with_extended_elbow:
            # 取肘角最大且在最高点附近或之后的帧
            frames_at_or_after_peak = [
                f for f in frames_with_extended_elbow
                if f.frame_number >= true_peak_fn - 2  # 允许最高点前2帧
            ]
            if frames_at_or_after_peak:
                release_frame = max(frames_at_or_after_peak, key=lambda f: f.angles.elbow_angle)
            else:
                release_frame = max(frames_with_extended_elbow, key=lambda f: f.angles.elbow_angle)
        else:
            # 如果没有肘角伸展的帧，使用真正的手腕最高点帧
            release_frame = min_wrist_y_frame

        key_frames[ShootingPhase.RELEASE_FRAME] = release_frame

        if release_frame and release_frame.angles:
            knee_str = f"{release_frame.angles.knee_angle:.1f}" if release_frame.angles.knee_angle else "N/A"
            print(f"[PhaseDetector] RELEASE_FRAME keyframe: frame#{release_frame.frame_number}, "
                  f"wrist_y={release_frame.wrist_y:.4f}, "
                  f"elbow={release_frame.angles.elbow_angle:.1f}°, "
                  f"knee={knee_str}°")

        return key_frames

    def get_sync_frame_1(self) -> Optional[FrameData]:
        """获取沉球点帧（SYNC_FRAME_1）"""
        key_frames = self.get_key_frames()
        return key_frames.get(ShootingPhase.SYNC_FRAME_1)

    def get_release_frame(self) -> Optional[FrameData]:
        """获取出手帧（RELEASE_FRAME）"""
        key_frames = self.get_key_frames()
        return key_frames.get(ShootingPhase.RELEASE_FRAME)

    def get_frames_after_sync(self, count: int = 10) -> list[FrameData]:
        """
        获取沉球点后的指定帧数

        Args:
            count: 要获取的帧数

        Returns:
            沉球点后的帧列表
        """
        key_frames = self.get_key_frames()
        sync_frame = key_frames.get(ShootingPhase.SYNC_FRAME_1)

        if not sync_frame:
            return []

        return [
            f for f in self.frame_history
            if f.frame_number > sync_frame.frame_number
        ][:count]

    def detect_coordination_issues(self) -> dict:
        """
        检测发力连贯性问题

        Returns:
            dict 包含两个问题的检测结果：
            - hand_foot_sync: 手脚同步性问题
            - power_disconnect: 发力脱节问题
        """
        key_frames = self.get_key_frames()

        result = {
            "hand_foot_sync": {
                "detected": False,
                "severity": "none",
                "frame_1": None,
                "frame_2": None,
                "knee_angle_1": None,
                "knee_angle_2": None,
                "knee_angle_change": None,
            },
            "power_disconnect": {
                "detected": False,
                "severity": "none",
                "frame_1": None,
                "frame_2": None,
                "knee_angle_1": None,
                "knee_angle_2": None,
                "knee_extension_at_hold": None,
            }
        }

        # ===== 问题1: 手脚同步性检测 =====
        # 检测手上升时脚是否还在继续下蹲
        sync_frame_1 = key_frames.get(ShootingPhase.SYNC_FRAME_1)
        sync_frame_2 = key_frames.get(ShootingPhase.SYNC_FRAME_2)

        if sync_frame_1 and sync_frame_2:
            knee_1 = sync_frame_1.angles.knee_angle if sync_frame_1.angles else None
            knee_2 = sync_frame_2.angles.knee_angle if sync_frame_2.angles else None

            result["hand_foot_sync"]["frame_1"] = sync_frame_1
            result["hand_foot_sync"]["frame_2"] = sync_frame_2
            result["hand_foot_sync"]["knee_angle_1"] = knee_1
            result["hand_foot_sync"]["knee_angle_2"] = knee_2

            if knee_1 is not None and knee_2 is not None:
                # 膝盖角度变化：角度减小表示继续弯曲（下蹲）
                # 膝盖角度增大表示伸展（蹬伸）
                knee_change = knee_2 - knee_1
                result["hand_foot_sync"]["knee_angle_change"] = knee_change

                print(f"[PhaseDetector] Hand-foot sync check: knee_1={knee_1:.1f}°, knee_2={knee_2:.1f}°, change={knee_change:.1f}°")

                # 如果膝盖角度减小超过阈值，说明脚还在继续下蹲
                # 这意味着手上升时脚还在下蹲 → 手快脚慢
                if knee_change < -5:  # 膝盖角度减小超过5°
                    result["hand_foot_sync"]["detected"] = True
                    if knee_change < -15:
                        result["hand_foot_sync"]["severity"] = "severe"
                    elif knee_change < -10:
                        result["hand_foot_sync"]["severity"] = "moderate"
                    else:
                        result["hand_foot_sync"]["severity"] = "minor"
                    print(f"[PhaseDetector] Hand-foot sync issue detected: severity={result['hand_foot_sync']['severity']}")
                else:
                    print(f"[PhaseDetector] Hand-foot sync: OK (knee extending during hand rise)")

        # ===== 问题2: 发力脱节检测 =====
        # 检测手举到最高点时腿是否已完成蹬伸
        max_hold_frame = key_frames.get(ShootingPhase.MAX_HOLD_FRAME)
        release_frame = key_frames.get(ShootingPhase.RELEASE_FRAME)

        if max_hold_frame:
            knee_hold = max_hold_frame.angles.knee_angle if max_hold_frame.angles else None

            result["power_disconnect"]["frame_1"] = max_hold_frame
            result["power_disconnect"]["frame_2"] = release_frame
            result["power_disconnect"]["knee_angle_1"] = knee_hold

            if release_frame and release_frame.angles:
                result["power_disconnect"]["knee_angle_2"] = release_frame.angles.knee_angle

            if knee_hold is not None:
                # 检查最高持球点时膝盖是否已伸直
                # 膝盖伸直的角度阈值：165°（接近完全伸直）
                # 如果膝盖角度 < 165°，说明腿还没蹬伸完 → 发力脱节
                result["power_disconnect"]["knee_extension_at_hold"] = knee_hold

                print(f"[PhaseDetector] Power disconnect check: knee at max_hold={knee_hold:.1f}°")

                if knee_hold < 165:  # 膝盖未伸直
                    result["power_disconnect"]["detected"] = True
                    if knee_hold < 140:
                        result["power_disconnect"]["severity"] = "severe"
                    elif knee_hold < 155:
                        result["power_disconnect"]["severity"] = "moderate"
                    else:
                        result["power_disconnect"]["severity"] = "minor"
                    print(f"[PhaseDetector] Power disconnect issue detected: severity={result['power_disconnect']['severity']}")
                else:
                    print(f"[PhaseDetector] Power disconnect: OK (knee extended at max hold)")

        return result
