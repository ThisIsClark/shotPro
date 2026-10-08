"""
Rules Engine Module
投篮发力连贯性检测规则引擎

专注于两个核心问题：
1. 手脚同步性：检测手上升时脚是否还在继续下蹲
2. 发力脱节：检测手举到最高点时腿是否已完成蹬伸
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List
from enum import Enum

from .angle_calculator import ShootingAngles
from .phase_detector import PhaseSegment, ShootingPhase, FrameData, PhaseDetector


# NBA球星参考数据（用于模板对比）
NBA_PLAYER_REFERENCES = {
    "knee_bend": {
        "name": "膝盖弯曲（准备阶段）",
        "name_en": "Knee Bend (Preparation)",
        "players": [
            {
                "name": "Stephen Curry",
                "name_zh": "斯蒂芬·库里",
                "value": "约115-125°",
                "note": "适度弯曲，快速发力，一段式投篮代表",
                "note_en": "Moderate bend, quick release, one-motion shooting"
            },
            {
                "name": "Kobe Bryant",
                "name_zh": "科比·布莱恩特",
                "value": "约105-115°",
                "note": "弯曲较深，二段式投篮，强调蓄力",
                "note_en": "Deeper bend, two-motion shooting, emphasis on power"
            },
            {
                "name": "Devin Booker",
                "name_zh": "德文·布克",
                "value": "约110-120°",
                "note": "中等深度，平衡型投篮",
                "note_en": "Medium depth, balanced shooting form"
            }
        ]
    },
    "knee_extension": {
        "name": "膝盖伸展（出手时）",
        "name_en": "Knee Extension (Release)",
        "players": [
            {
                "name": "Stephen Curry",
                "name_zh": "斯蒂芬·库里",
                "value": "约170-175°",
                "note": "完全蹬伸，力量传递充分",
                "note_en": "Full extension, complete power transfer"
            },
            {
                "name": "Klay Thompson",
                "name_zh": "克莱·汤普森",
                "value": "约172-176°",
                "note": "完全伸展，极其稳定",
                "note_en": "Full extension, extremely stable"
            }
        ]
    }
}


class CoordinationSeverity(str, Enum):
    """发力连贯性问题严重程度"""
    NONE = "none"          # 无问题
    MINOR = "minor"        # 轻微问题
    MODERATE = "moderate"  # 中等问题
    SEVERE = "severe"      # 严重问题


class CoordinationIssueType(str, Enum):
    """发力连贯性问题类型"""
    HAND_FOOT_SYNC = "hand_foot_sync"       # 手脚同步性
    POWER_DISCONNECT = "power_disconnect"   # 发力脱节


@dataclass
class CoordinationIssue:
    """发力连贯性问题检测结果"""
    issue_type: CoordinationIssueType
    detected: bool
    severity: CoordinationSeverity
    frame_1: Optional[FrameData] = None  # 检测用的第一帧
    frame_2: Optional[FrameData] = None  # 检测用的第二帧
    knee_angle_1: Optional[float] = None  # 第一帧膝盖角度
    knee_angle_2: Optional[float] = None  # 第二帧膝盖角度
    description: str = ""
    description_en: str = ""
    suggestion: str = ""
    suggestion_en: str = ""
    skipped: bool = False  # 是否因数据不足而跳过检测
    skip_reason: str = ""  # 跳过原因


class RulesEngine:
    """投篮发力连贯性检测规则引擎"""

    # 检测阈值
    HAND_FOOT_SYNC_THRESHOLD = 8.0  # 手上升初期膝盖角度减小超过此值认为脚还在明显下蹲。
                                    # 正常反向运动（stretch-shorten cycle）会让膝盖在
                                    # 起球初期再弯 5~8°，低于此幅度不算问题
    POWER_DISCONNECT_THRESHOLD = 165.0  # 最高持球点膝盖角度低于此值认为腿还没蹬伸完
    # 手快脚慢时序检测阈值（全部归一化为"举球全程 dip→hold 的比例"，
    # 对慢动作视频/不同出手节奏免疫，不使用绝对秒数）
    HAND_FOOT_LAG_DETECT = 0.50   # 膝蹬伸起点晚于举球全程此比例 → 判定手快脚慢
    HAND_FOOT_LAG_MODERATE = 0.60  # 超过此比例为中度
    HAND_FOOT_LAG_SEVERE = 0.75    # 超过此比例为重度
    KNEE_EXT_WINDOW = 4    # 蹬伸起点后的验证窗口（帧）
    KNEE_EXT_SUSTAINED = 12.0  # 验证窗口内膝角需持续上升的总量（°），过滤蹲底小回弹
    KNEE_PROGRESS_SUPPRESS = 0.20  # 球升到一半时膝蹬伸进度低于此值 → 视为正常同步（抑制时序信号）
                                   # 一段式好投篮在球半程时膝盖常仍在蹲底附近（约0~0.1），不构成问题

    def __init__(self):
        """初始化规则引擎"""
        pass

    def evaluate_coordination(
        self,
        key_frames: dict[ShootingPhase, Optional[FrameData]],
        frame_data_list: list[FrameData]
    ) -> list[CoordinationIssue]:
        """
        评估发力连贯性

        Args:
            key_frames: 关键帧数据（从 PhaseDetector.get_key_frames() 获取）
            frame_data_list: 所有帧数据列表

        Returns:
            发力连贯性问题列表
        """
        issues = []

        # 检测手脚同步性
        sync_issue = self._check_hand_foot_sync(key_frames, frame_data_list)
        issues.append(sync_issue)

        # 检测发力脱节
        disconnect_issue = self._check_power_disconnect(key_frames)
        issues.append(disconnect_issue)

        return issues

    def _check_hand_foot_sync(
        self,
        key_frames: dict[ShootingPhase, Optional[FrameData]],
        frame_data_list: list[FrameData]
    ) -> CoordinationIssue:
        """
        检测手脚同步性问题（手快脚慢）

        两路信号，任一触发即判定有问题：
        1. 时序信号（主）：沉球点（手开始上升）→ 膝盖开始蹬伸 的延迟。
           手快脚慢的本质是时序错位——球先走，腿还停在蹲底没发力，膝盖角度
           变化可能接近 0，单看角度差会漏检，必须比较时间。
        2. 角度差信号（辅）：手上升初期膝盖角度仍在减小（脚还在继续下蹲）。

        Args:
            key_frames: 关键帧数据
            frame_data_list: 全部帧数据（平滑后角度）

        Returns:
            手脚同步性检测结果
        """
        sync_frame_1 = key_frames.get(ShootingPhase.SYNC_FRAME_1)
        sync_frame_2 = key_frames.get(ShootingPhase.SYNC_FRAME_2)
        knee_min_frame = key_frames.get(ShootingPhase.KNEE_MIN_FRAME)

        # frame_2 用于前端展示：优先用蹲底帧（带关键帧图片，语义为"腿还在蹲底"）
        display_frame_2 = knee_min_frame or sync_frame_2

        issue = CoordinationIssue(
            issue_type=CoordinationIssueType.HAND_FOOT_SYNC,
            detected=False,
            severity=CoordinationSeverity.NONE,
            frame_1=sync_frame_1,
            frame_2=display_frame_2
        )

        if not sync_frame_1:
            # 无沉球点，无法检测
            issue.skipped = True
            issue.skip_reason = "dip_point_not_found"
            issue.description = "未能定位沉球点，无法检测手脚同步性。请确保视频包含完整的下蹲-举球-出手过程。"
            issue.description_en = "Dip point not found. Unable to detect hand-foot sync. Please ensure the video contains the full dip-lift-release motion."
            return issue

        knee_1 = sync_frame_1.angles.knee_angle if sync_frame_1.angles else None
        issue.knee_angle_1 = knee_1
        if display_frame_2 and display_frame_2.angles:
            issue.knee_angle_2 = display_frame_2.angles.knee_angle

        # ===== 信号1：时序检测（手上升 vs 膝蹬伸的相对时序，归一化） =====
        lag_seconds = None
        ext_norm = None           # 膝蹬伸起点在举球全程(dip→hold)中的位置比例
        ext_start_frame = None
        knee_progress_mid = None  # 球升到一半时，膝蹬伸已完成的比例
        max_hold = key_frames.get(ShootingPhase.MAX_HOLD_FRAME)
        wrist_peak = key_frames.get(ShootingPhase.WRIST_PEAK_FRAME)

        if frame_data_list and max_hold and max_hold.angles:
            knee_hold = max_hold.angles.knee_angle
            lift_duration = max_hold.timestamp - sync_frame_1.timestamp

            if knee_hold is not None and lift_duration > 0.05:
                # 出手边界：膝角搜索限制在出手前（防止把落地后的下蹲算进来）
                boundary_fn = None
                for phase in (ShootingPhase.WRIST_PEAK_FRAME, ShootingPhase.RELEASE_FRAME):
                    kf = key_frames.get(phase)
                    if kf:
                        boundary_fn = kf.frame_number
                        break

                knee_points = sorted(
                    (fd.frame_number, fd.timestamp, fd.angles.knee_angle)
                    for fd in frame_data_list
                    if fd.angles and fd.angles.knee_angle is not None
                    and (boundary_fn is None or fd.frame_number <= boundary_fn)
                )

                if len(knee_points) >= 6:
                    # 蹲底 = 边界内膝角最小的帧
                    min_idx = min(range(len(knee_points)), key=lambda i: knee_points[i][2])
                    knee_min = knee_points[min_idx][2]

                    # 蹬伸起点 = 蹲底之后，KNEE_EXT_WINDOW 帧内膝角持续上升且总量
                    # 达到 KNEE_EXT_SUSTAINED 的起点。"持续上升（无回落）"约束用于
                    # 过滤蹲底的小回弹（膝角先弹起几度又落回，随后才真正蹬伸）。
                    for j in range(min_idx, len(knee_points) - self.KNEE_EXT_WINDOW):
                        window = knee_points[j + 1: j + 1 + self.KNEE_EXT_WINDOW]
                        window_angles = [p[2] for p in window]
                        if min(window_angles) >= knee_points[j][2] and \
                           window_angles[-1] - knee_points[j][2] >= self.KNEE_EXT_SUSTAINED:
                            ext_start_frame = knee_points[j]
                            break

                    # 膝蹬伸进度抑制指标：球升到一半时膝角离蹲底有多远。
                    # 一段式好投篮（如 Curry）在球半程时膝盖常仍在蹲底附近
                    # （膝角随举球同步渐进），这是正常同步，不算手快脚慢。
                    if wrist_peak and wrist_peak.wrist_y is not None and knee_hold > knee_min + 2:
                        y_dip = sync_frame_1.wrist_y
                        y_top = wrist_peak.wrist_y
                        mid_target = (y_dip + y_top) / 2
                        wrist_frames = sorted(
                            (fd.frame_number, fd.wrist_y) for fd in frame_data_list
                            if fd.wrist_y is not None
                            and sync_frame_1.frame_number < fd.frame_number <= boundary_fn
                        ) if boundary_fn else []
                        mid_frame_fn = None
                        for fn, wy in wrist_frames:
                            if wy <= mid_target:
                                mid_frame_fn = fn
                                break
                        if mid_frame_fn is not None:
                            near = [p for p in knee_points if abs(p[0] - mid_frame_fn) <= 2]
                            if near:
                                knee_mid = near[0][2]
                                knee_progress_mid = (knee_mid - knee_min) / (knee_hold - knee_min)

                    if ext_start_frame is not None:
                        lag_seconds = ext_start_frame[1] - sync_frame_1.timestamp
                        ext_norm = lag_seconds / lift_duration
                        print(f"[RulesEngine] Hand-foot timing: dip={sync_frame_1.timestamp:.2f}s, "
                              f"knee ext start={ext_start_frame[1]:.2f}s, lag={lag_seconds:.2f}s "
                              f"(ext at {ext_norm:.0%} of lift), knee progress at mid-rise="
                              f"{knee_progress_mid if knee_progress_mid is None else f'{knee_progress_mid:.0%}'}")

        # ===== 信号2：角度差检测（手上升初期膝盖是否仍在下蹲） =====
        knee_change = None
        if sync_frame_1 and sync_frame_2:
            knee_2 = sync_frame_2.angles.knee_angle if sync_frame_2.angles else None
            if knee_1 is not None and knee_2 is not None:
                knee_change = knee_2 - knee_1
                print(f"[RulesEngine] Hand-foot angle check: knee_1={knee_1:.1f}°, "
                      f"knee_2={knee_2:.1f}°, change={knee_change:.1f}°")

        # ===== 综合判定 =====
        # 时序信号需同时满足：膝蹬伸起点晚于举球全程的 HAND_FOOT_LAG_DETECT，
        # 且球半程时膝蹬伸进度未低于 KNEE_PROGRESS_SUPPRESS（后者排除
        # "膝随举球同步渐进"的正常一段式节奏）
        timing_detected = (
            ext_norm is not None
            and ext_norm > self.HAND_FOOT_LAG_DETECT
            and knee_progress_mid is not None
            and knee_progress_mid >= self.KNEE_PROGRESS_SUPPRESS
        )
        angle_detected = knee_change is not None and knee_change < -self.HAND_FOOT_SYNC_THRESHOLD

        if timing_detected or angle_detected:
            issue.detected = True

            # 严重程度：取两路信号中更重的一档
            timing_severity = CoordinationSeverity.NONE
            if timing_detected:
                if ext_norm > self.HAND_FOOT_LAG_SEVERE:
                    timing_severity = CoordinationSeverity.SEVERE
                elif ext_norm > self.HAND_FOOT_LAG_MODERATE:
                    timing_severity = CoordinationSeverity.MODERATE
                else:
                    timing_severity = CoordinationSeverity.MINOR

            angle_severity = CoordinationSeverity.NONE
            if angle_detected:
                if knee_change < -15:
                    angle_severity = CoordinationSeverity.SEVERE
                elif knee_change < -10:
                    angle_severity = CoordinationSeverity.MODERATE
                else:
                    angle_severity = CoordinationSeverity.MINOR

            issue.severity = max(
                [timing_severity, angle_severity],
                key=lambda s: [CoordinationSeverity.NONE, CoordinationSeverity.MINOR,
                               CoordinationSeverity.MODERATE, CoordinationSeverity.SEVERE].index(s)
            )

            # 生成描述和建议（时序信号优先呈现，因为它更贴近"手快脚慢"的本质）
            if timing_detected:
                issue.description = (
                    f"手快脚慢：沉球点({sync_frame_1.timestamp:.2f}s)手已开始上升，"
                    f"但膝盖直到举球进行到{ext_norm:.0%}时（{ext_start_frame[1]:.2f}s）才开始蹬伸，"
                    f"腿部发力比举球晚了{lag_seconds:.2f}秒。球先走、腿后蹬，"
                    f"力量无法顺着蹬伸链条传递到出手。"
                )
                issue.description_en = (
                    f"Hand-foot sync issue: Hand starts rising at the dip ({sync_frame_1.timestamp:.2f}s), "
                    f"but knee extension doesn't begin until the lift is {ext_norm:.0%} complete "
                    f"({ext_start_frame[1]:.2f}s) — legs fire {lag_seconds:.2f}s behind the lift. "
                    f"The ball moves first and the legs drive late, breaking the power chain into the release."
                )
            else:
                if knee_change is not None:
                    issue.description = (
                        f"手脚同步问题：手开始上升时脚还在继续下蹲。沉球点膝盖角度{knee_1:.1f}°，"
                        f"手上升后膝盖角度{sync_frame_2.angles.knee_angle:.1f}°，角度减小{abs(knee_change):.1f}°。"
                        "手上升太快，脚的下蹲还没完成。"
                    )
                    issue.description_en = (
                        f"Hand-foot sync issue: Foot continues to bend while hand starts rising. "
                        f"Knee angle at dip: {knee_1:.1f}°, after hand rise: {sync_frame_2.angles.knee_angle:.1f}°, "
                        f"decrease of {abs(knee_change):.1f}°. Hand rises too fast before foot bending completes."
                    )

            issue.suggestion = "建议：放慢手上升的速度，等待腿部下蹲蓄力完成后再开始举球。先蓄力、再发力，让膝盖蹬伸和举球同时启动。可以尝试练习'沉球等待'动作：沉球到底后停半拍，感受腿部蹬伸带着球走。"
            issue.suggestion_en = "Suggestion: Slow down the hand rising speed, wait for the leg loading to complete before lifting the ball. Store power first, then release it — let the knee extension and the lift start together. Try the 'dip and wait' drill: pause a beat at the bottom of the dip, then feel the leg drive carry the ball up."

            print(f"[RulesEngine] Hand-foot sync issue detected: severity={issue.severity.value}")
        else:
            # 无问题
            if lag_seconds is not None and ext_norm is not None:
                if knee_progress_mid is not None and knee_progress_mid < self.KNEE_PROGRESS_SUPPRESS:
                    # 膝盖随举球同步渐进伸展，蹬伸加速点偏晚但整体节奏正常
                    issue.description = "手脚同步良好：膝盖随举球同步渐进伸展，蹬伸与举球衔接正常。"
                    issue.description_en = "Good hand-foot sync: Knee extends gradually along with the lift, well-coordinated timing."
                else:
                    issue.description = (
                        f"手脚同步良好：膝盖蹬伸在举球{max(0.0, ext_norm):.0%}处启动，与举球节奏匹配。"
                    )
                    issue.description_en = (
                        f"Good hand-foot sync: Knee extension starts at {max(0.0, ext_norm):.0%} of the lift, well-matched timing."
                    )
            elif knee_change is not None:
                issue.description = f"手脚同步良好：手上升时脚已经开始蹬伸或停止下蹲。沉球点膝盖角度{knee_1:.1f}°，手上升后膝盖角度{sync_frame_2.angles.knee_angle:.1f}°。"
                issue.description_en = f"Good hand-foot sync: Foot starts extending or stops bending when hand rises. Knee angle at dip: {knee_1:.1f}°, after hand rise: {sync_frame_2.angles.knee_angle:.1f}°."
            print(f"[RulesEngine] Hand-foot sync: OK")

        # 两路信号都缺数据时标记跳过
        if lag_seconds is None and knee_change is None:
            issue.skipped = True
            issue.skip_reason = "knee_data_unavailable"
            issue.description = "膝盖数据不可用（可见度不足或膝盖不在画面内），无法检测手脚同步性。请确保拍摄时膝盖完整出现在画面中。"
            issue.description_en = "Knee data unavailable (visibility too low or knee not in frame). Unable to detect hand-foot sync. Please ensure the knee is fully visible in the video."
            print(f"[RulesEngine] Hand-foot sync: skipped (knee data unavailable)")

        return issue

    def _check_power_disconnect(
        self,
        key_frames: dict[ShootingPhase, Optional[FrameData]]
    ) -> CoordinationIssue:
        """
        检测发力脱节问题

        逻辑：
        - 检查 MAX_HOLD_FRAME（最高持球点）时的膝盖角度
        - 如果膝盖角度 < 165°，说明腿还没蹬伸完
        - 这意味着手举到最高点时腿还在蹬伸 → 发力脱节（手等待脚）

        Args:
            key_frames: 关键帧数据

        Returns:
            发力脱节检测结果
        """
        max_hold_frame = key_frames.get(ShootingPhase.MAX_HOLD_FRAME)
        release_frame = key_frames.get(ShootingPhase.RELEASE_FRAME)

        issue = CoordinationIssue(
            issue_type=CoordinationIssueType.POWER_DISCONNECT,
            detected=False,
            severity=CoordinationSeverity.NONE,
            frame_1=max_hold_frame,
            frame_2=release_frame
        )

        if max_hold_frame:
            knee_hold = max_hold_frame.angles.knee_angle if max_hold_frame.angles else None
            knee_release = release_frame.angles.knee_angle if release_frame and release_frame.angles else None

            issue.knee_angle_1 = knee_hold
            issue.knee_angle_2 = knee_release

            if knee_hold is not None:
                print(f"[RulesEngine] Power disconnect: knee at max_hold={knee_hold:.1f}°, threshold={self.POWER_DISCONNECT_THRESHOLD}°")

                # 检查最高持球点时膝盖是否已伸直
                if knee_hold < self.POWER_DISCONNECT_THRESHOLD:
                    issue.detected = True

                    # 根据膝盖角度确定严重程度
                    if knee_hold < 140:
                        issue.severity = CoordinationSeverity.SEVERE
                    elif knee_hold < 155:
                        issue.severity = CoordinationSeverity.MODERATE
                    else:
                        issue.severity = CoordinationSeverity.MINOR

                    # 生成描述和建议
                    issue.description = f"发力脱节问题：手举到最高点时腿还没完成蹬伸。最高持球点膝盖角度{knee_hold:.1f}°，低于正常值（>165°）。这说明手举球太快，腿的蹬伸还没完成，导致力量传递中断。"
                    issue.description_en = f"Power disconnect issue: Leg hasn't completed extension when hand reaches highest point. Knee angle at max hold: {knee_hold:.1f}°, below normal (>165°). This indicates hand lifts too fast, leg extension incomplete, causing power transfer interruption."

                    issue.suggestion = "建议：放慢举球速度，确保腿部蹬伸完成后再出手。可以尝试'坐等蹬伸'的感觉——在最高点稍等一下让腿蹬伸完成。理想情况下，最高持球点时膝盖应该接近完全伸直（>165°），这样力量才能顺畅传递到出手。"
                    issue.suggestion_en = "Suggestion: Slow down the ball lifting speed, ensure leg extension completes before release. Try the 'sit and wait for extension' feeling—wait briefly at the highest point for leg extension to complete. Ideally, knee should be near full extension (>165°) at max hold for smooth power transfer to release."

                    print(f"[RulesEngine] Power disconnect issue detected: severity={issue.severity.value}")
                else:
                    issue.detected = False
                    issue.severity = CoordinationSeverity.NONE
                    issue.description = f"发力连贯良好：手举到最高点时腿已完成蹬伸。最高持球点膝盖角度{knee_hold:.1f}°，接近完全伸直。"
                    issue.description_en = f"Good power connection: Leg has completed extension when hand reaches highest point. Knee angle at max hold: {knee_hold:.1f}°, near full extension."
                    issue.suggestion = ""
                    issue.suggestion_en = ""
                    print(f"[RulesEngine] Power disconnect: OK")
            else:
                # 膝盖数据不可用，无法检测
                issue.skipped = True
                issue.skip_reason = "knee_data_unavailable"
                issue.description = "膝盖数据不可用（可见度不足或膝盖不在画面内），无法检测发力脱节。请确保拍摄时膝盖完整出现在画面中。"
                issue.description_en = "Knee data unavailable (visibility too low or knee not in frame). Unable to detect power disconnect. Please ensure the knee is fully visible in the video."
                print(f"[RulesEngine] Power disconnect: skipped (knee data unavailable)")

        return issue