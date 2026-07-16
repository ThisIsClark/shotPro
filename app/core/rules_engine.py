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
    HAND_FOOT_SYNC_THRESHOLD = 5.0  # 膝盖角度变化超过此值认为有问题（角度减小表示继续弯曲）
    POWER_DISCONNECT_THRESHOLD = 165.0  # 最高持球点膝盖角度低于此值认为腿还没蹬伸完

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
        sync_issue = self._check_hand_foot_sync(key_frames)
        issues.append(sync_issue)

        # 检测发力脱节
        disconnect_issue = self._check_power_disconnect(key_frames)
        issues.append(disconnect_issue)

        return issues

    def _check_hand_foot_sync(
        self,
        key_frames: dict[ShootingPhase, Optional[FrameData]]
    ) -> CoordinationIssue:
        """
        检测手脚同步性问题

        逻辑：
        - 比较 SYNC_FRAME_1（沉球点）和 SYNC_FRAME_2（手上升后）的膝盖角度
        - 如果膝盖角度减小（SYNC_FRAME_2 < SYNC_FRAME_1），说明脚还在继续下蹲
        - 这意味着手上升时脚还在下蹲 → 手快脚慢

        Args:
            key_frames: 关键帧数据

        Returns:
            手脚同步性检测结果
        """
        sync_frame_1 = key_frames.get(ShootingPhase.SYNC_FRAME_1)
        sync_frame_2 = key_frames.get(ShootingPhase.SYNC_FRAME_2)

        issue = CoordinationIssue(
            issue_type=CoordinationIssueType.HAND_FOOT_SYNC,
            detected=False,
            severity=CoordinationSeverity.NONE,
            frame_1=sync_frame_1,
            frame_2=sync_frame_2
        )

        if sync_frame_1 and sync_frame_2:
            knee_1 = sync_frame_1.angles.knee_angle if sync_frame_1.angles else None
            knee_2 = sync_frame_2.angles.knee_angle if sync_frame_2.angles else None

            issue.knee_angle_1 = knee_1
            issue.knee_angle_2 = knee_2

            if knee_1 is not None and knee_2 is not None:
                # 膝盖角度变化：角度减小表示继续弯曲（下蹲）
                knee_change = knee_2 - knee_1

                print(f"[RulesEngine] Hand-foot sync: knee_1={knee_1:.1f}°, knee_2={knee_2:.1f}°, change={knee_change:.1f}°")

                # 如果膝盖角度减小超过阈值，说明脚还在继续下蹲
                if knee_change < -self.HAND_FOOT_SYNC_THRESHOLD:
                    issue.detected = True

                    # 根据变化程度确定严重程度
                    if knee_change < -15:
                        issue.severity = CoordinationSeverity.SEVERE
                    elif knee_change < -10:
                        issue.severity = CoordinationSeverity.MODERATE
                    else:
                        issue.severity = CoordinationSeverity.MINOR

                    # 生成描述和建议
                    issue.description = f"手脚同步问题：手开始上升时脚还在继续下蹲。沉球点膝盖角度{knee_1:.1f}°，手上升后膝盖角度{knee_2:.1f}°，角度减小{knee_change:.1f}°。这说明手上升太快，脚的下蹲还没完成。"
                    issue.description_en = f"Hand-foot sync issue: Foot continues to bend while hand starts rising. Knee angle at dip: {knee_1:.1f}°, after hand rise: {knee_2:.1f}°, decrease of {abs(knee_change):.1f}°. This indicates hand rises too fast before foot bending completes."

                    issue.suggestion = "建议：放慢手上升的速度，等待腿部下蹲动作完成后再开始举球。先完成蓄力，再开始发力，确保手脚同步协调。可以尝试练习'沉球等待'动作，感受腿部蓄力完成后再举球。"
                    issue.suggestion_en = "Suggestion: Slow down the hand rising speed, wait for leg bending to complete before starting to lift the ball. Complete power storage first, then start power release, ensuring hand-foot coordination. Try practicing 'dip and wait' motion, feel the leg power storage completion before lifting."

                    print(f"[RulesEngine] Hand-foot sync issue detected: severity={issue.severity.value}")
                else:
                    issue.detected = False
                    issue.severity = CoordinationSeverity.NONE
                    issue.description = f"手脚同步良好：手上升时脚已经开始蹬伸或停止下蹲。沉球点膝盖角度{knee_1:.1f}°，手上升后膝盖角度{knee_2:.1f}°。"
                    issue.description_en = f"Good hand-foot sync: Foot starts extending or stops bending when hand rises. Knee angle at dip: {knee_1:.1f}°, after hand rise: {knee_2:.1f}°."
                    issue.suggestion = ""
                    issue.suggestion_en = ""
                    print(f"[RulesEngine] Hand-foot sync: OK")
            else:
                # 膝盖数据不可用，无法检测
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