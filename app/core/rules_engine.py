"""
Rules Engine Module
投篮姿势评估规则引擎

Based on:
- BEEF Method (Balance, Eyes, Elbows, Follow-through) - Professional coaching standard
- Biomechanical research on proficient shooters (≥70% accuracy)
- Elite shooter mechanics (NBA analysis)
- Sports science research on shooting accuracy factors
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, List
from enum import Enum

from .angle_calculator import ShootingAngles
from .phase_detector import PhaseSegment, ShootingPhase, FrameData


# NBA球星参考数据
# 注意：这些数据来自公开视频分析和教练分析，是近似值而非精确实验室测量
# 不同来源和不同投篮可能略有差异，仅供参考
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
            },
            {
                "name": "Damian Lillard",
                "name_zh": "达米安·利拉德",
                "value": "约120-130°",
                "note": "弯曲较浅，快速出手",
                "note_en": "Shallower bend, quick release"
            }
        ]
    },
    "elbow_extension": {
        "name": "肘部伸展（出手时）",
        "name_en": "Elbow Extension (Release)",
        "players": [
            {
                "name": "Stephen Curry",
                "name_zh": "斯蒂芬·库里",
                "value": "约175-178°",
                "note": "接近完全伸展，教科书式出手",
                "note_en": "Near-complete extension, textbook release"
            },
            {
                "name": "Klay Thompson",
                "name_zh": "克莱·汤普森",
                "value": "约172-176°",
                "note": "完全伸展，极其稳定",
                "note_en": "Full extension, extremely stable"
            },
            {
                "name": "Ray Allen",
                "name_zh": "雷·阿伦",
                "value": "约170-175°",
                "note": "经典投手，完全伸展",
                "note_en": "Classic shooter, full extension"
            }
        ]
    },
    "release_height": {
        "name": "出手点高度（肩部角度）",
        "name_en": "Release Height (Shoulder Angle)",
        "players": [
            {
                "name": "Stephen Curry",
                "name_zh": "斯蒂芬·库里",
                "value": "约92-96°",
                "note": "高出手点，眉毛位置",
                "note_en": "High release, eyebrow level"
            },
            {
                "name": "Kevin Durant",
                "name_zh": "凯文·杜兰特",
                "value": "约95-100°",
                "note": "极高出手点，结合身高优势",
                "note_en": "Very high release, combined with height advantage"
            },
            {
                "name": "Dirk Nowitzki",
                "name_zh": "德克·诺维茨基",
                "value": "约98-105°",
                "note": "标志性高出手，后仰投篮",
                "note_en": "Signature high release, fadeaway shot"
            }
        ]
    },
    "body_balance": {
        "name": "身体平衡（躯干倾斜）",
        "name_en": "Body Balance (Trunk Lean)",
        "players": [
            {
                "name": "Klay Thompson",
                "name_zh": "克莱·汤普森",
                "value": "约2-4°",
                "note": "几乎完全垂直，极佳平衡",
                "note_en": "Nearly vertical, excellent balance"
            },
            {
                "name": "Stephen Curry",
                "name_zh": "斯蒂芬·库里",
                "value": "约3-6°",
                "note": "接近垂直，动态平衡",
                "note_en": "Near vertical, dynamic balance"
            },
            {
                "name": "Steve Nash",
                "name_zh": "史蒂夫·纳什",
                "value": "约2-5°",
                "note": "优秀的身体控制",
                "note_en": "Excellent body control"
            }
        ]
    }
}


class IssueSeverity(str, Enum):
    """问题严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class IssueType(str, Enum):
    """问题类型"""
    ELBOW_FLARE = "elbow_flare"
    WRIST_FLIP = "wrist_flip"
    NO_FOLLOW_THROUGH = "no_follow_through"
    BODY_LEAN = "body_lean"
    LOW_RELEASE = "low_release"
    KNEE_COLLAPSE = "knee_collapse"
    INSUFFICIENT_KNEE_BEND = "insufficient_knee_bend"
    ARM_NOT_EXTENDED = "arm_not_extended"
    RUSHED_SHOT = "rushed_shot"
    NO_LEG_DRIVE = "no_leg_drive"
    HAND_FAST_FOOT_SLOW = "hand_fast_foot_slow"


@dataclass
class Issue:
    """检测到的问题"""
    type: IssueType
    severity: IssueSeverity
    description: str
    description_en: str
    frame: Optional[int] = None
    phase: Optional[ShootingPhase] = None
    suggestion: str = ""
    suggestion_en: str = ""
    reference: str = ""  # 权威依据
    reference_en: str = ""  # 权威依据（英文）


@dataclass
class DimensionScore:
    """单项评分"""
    name: str
    name_en: str
    score: float  # 0-100
    weight: float  # 权重
    feedback: str
    feedback_en: str
    
    @property
    def weighted_score(self) -> float:
        return self.score * self.weight


class ShootingStyle(str, Enum):
    """投篮方式"""
    ONE_MOTION = "one_motion"      # 一段式（流畅型）
    TWO_MOTION = "two_motion"      # 二段式（传统型）


@dataclass
class RuleThresholds:
    """
    规则阈值配置
    
    Based on professional standards:
    - BEEF Method (Professional coaching standard)
    - Biomechanical research on elite shooters
    - NBA shooting form analysis
    - Shooting style differences (one-motion vs two-motion)
    """
    shooting_style: ShootingStyle = ShootingStyle.ONE_MOTION
    
    # 肘部 (Elbow) - BEEF Method: Elbow under ball, forms L-shape at ~90°
    elbow_release_min: float = 160.0      # 出手时肘部最小角度
    elbow_release_ideal: float = 175.0    # 理想出手肘部角度
    elbow_l_shape: float = 90.0           # 准备时的L型标准角度
    
    # 膝盖 (Knee) - BEEF Method: Balance with bent knees
    # 注意：具体角度范围是经验性参考，非科学验证的绝对值
    # 研究证明：控制性（较低角速度）比具体角度更重要
    knee_prep_max: float = 130.0          # 准备时膝盖参考最大角度（过浅）
    knee_prep_ideal: float = 115.0        # 参考理想范围中点（100-130°）
    knee_prep_min: float = 90.0           # 最小角度（过深蹲，降低控制）
    
    # 躯干 (Trunk) - Research: Less forward lean = better accuracy
    trunk_max_lean: float = 10.0          # 最大躯干倾斜
    trunk_ideal: float = 3.0              # 理想躯干角度
    
    # 肩部 (Shoulder) - Release height affects shooting success
    shoulder_release_min: float = 75.0    # 出手时肩部最小角度
    shoulder_release_ideal: float = 95.0  # 理想出手肩部角度
    
    # 手腕 (Wrist) - BEEF Method: Follow-through with wrist snap
    wrist_follow_min: float = 140.0       # 跟随时手腕最小角度（弯曲）
    wrist_follow_ideal: float = 120.0     # 理想手腕下压角度
    
    @classmethod
    def for_one_motion(cls) -> 'RuleThresholds':
        """
        一段式投篮标准（如Stephen Curry）
        特点：流畅、快速、从下到上一气呵成
        """
        return cls(
            shooting_style=ShootingStyle.ONE_MOTION,
            # 一段式：肘部可以不那么伸展，更注重流畅性
            elbow_release_min=155.0,
            elbow_release_ideal=170.0,
            # 一段式：膝盖弯曲相对较浅，快速发力（参考范围）
            knee_prep_max=135.0,
            knee_prep_ideal=120.0,
            knee_prep_min=100.0,
            # 一段式：允许略微前倾，配合动作流畅性
            trunk_max_lean=12.0,
            trunk_ideal=5.0,
            # 一段式：出手点可以稍低，速度更快
            shoulder_release_min=70.0,
            shoulder_release_ideal=90.0,
            # 一段式：手腕跟随很重要
            wrist_follow_min=140.0,
            wrist_follow_ideal=120.0,
        )
    
    @classmethod
    def for_two_motion(cls) -> 'RuleThresholds':
        """
        二段式投篮标准（传统投篮）
        特点：稳定、有停顿、举球-出手两个明确阶段
        """
        return cls(
            shooting_style=ShootingStyle.TWO_MOTION,
            # 二段式：要求完全伸展，更稳定
            elbow_release_min=165.0,
            elbow_release_ideal=178.0,
            # 二段式：膝盖弯曲相对较深，蓄力充分（参考范围）
            knee_prep_max=125.0,
            knee_prep_ideal=110.0,
            knee_prep_min=95.0,
            # 二段式：要求严格垂直，更稳定
            trunk_max_lean=8.0,
            trunk_ideal=2.0,
            # 二段式：出手点更高
            shoulder_release_min=80.0,
            shoulder_release_ideal=98.0,
            # 二段式：手腕跟随同样重要
            wrist_follow_min=140.0,
            wrist_follow_ideal=115.0,
        )


@dataclass
class EvaluationResult:
    """评估结果"""
    overall_score: float
    rating: str
    dimension_scores: list[DimensionScore]
    issues: list[Issue]
    suggestions: list[dict]


class RulesEngine:
    """规则引擎"""
    
    # 评级定义
    RATINGS = {
        "excellent": {"min": 90, "label": "优秀", "label_en": "Excellent"},
        "good": {"min": 75, "label": "良好", "label_en": "Good"},
        "fair": {"min": 60, "label": "一般", "label_en": "Fair"},
        "needs_improvement": {"min": 0, "label": "需改进", "label_en": "Needs Improvement"}
    }
    
    # 规则定义 - Based on BEEF Method and biomechanical research
    RULES = {
        "elbow_alignment": {
            "name": "肘部伸展",
            "name_en": "Elbow Extension",
            "description": "出手时手臂伸展程度 (BEEF: Elbow alignment)",
            "description_en": "Arm extension at release (BEEF: Elbow alignment)",
            "weight": 0.25,  # 增加权重，肘部对准确性影响最大
            "reference": "BEEF Method - 肘部应在球下方，出手时完全伸展"
        },
        "knee_drive": {
            "name": "腿部稳定",
            "name_en": "Leg Stability",
            "description": "膝盖弯曲和腿部控制 (BEEF: Balance)",
            "description_en": "Knee bend and leg control (BEEF: Balance)",
            "weight": 0.15,
            "reference": "研究表明：优秀射手膝盖角速度更低，控制更好"
        },
        "body_balance": {
            "name": "身体平衡",
            "name_en": "Body Balance",
            "description": "躯干垂直度 (BEEF: Balance)",
            "description_en": "Trunk verticality (BEEF: Balance)",
            "weight": 0.20,  # 增加权重，研究显示这对准确性很关键
            "reference": "研究发现：优秀射手出手时躯干倾斜显著更小"
        },
        "release_point": {
            "name": "出手点高度",
            "name_en": "Release Height",
            "description": "出手位置和高度",
            "description_en": "Release position and height",
            "weight": 0.20,
            "reference": "研究表明：更高的出手点与更高命中率相关"
        },
        "follow_through": {
            "name": "跟随动作",
            "name_en": "Follow Through",
            "description": "出手后手腕下压 (BEEF: Follow-through)",
            "description_en": "Wrist snap after release (BEEF: Follow-through)",
            "weight": 0.12,
            "reference": "BEEF Method - 手臂完全伸展，手腕下压，手指指向篮筐"
        },
        "fluidity": {
            "name": "动作流畅",
            "name_en": "Motion Fluidity",
            "description": "整体动作流畅性和节奏",
            "description_en": "Overall motion smoothness and rhythm",
            "weight": 0.08,
            "reference": "研究显示：动态补偿比机械重复更重要"
        },
        "hand_foot_coordination": {
            "name": "手脚协调",
            "name_en": "Hand-Foot Coordination",
            "description": "手部举球与腿部发力的协调性",
            "description_en": "Coordination between hand lift and leg drive",
            "weight": 0.0,  # 初始权重为0，会从其他维度分配
            "reference": "正确的投篮应该是腿部发力和手部举球同步或先腿后手，避免手快脚慢"
        }
    }
    
    def __init__(self, thresholds: Optional[RuleThresholds] = None, shooting_style: ShootingStyle = ShootingStyle.ONE_MOTION):
        """
        初始化规则引擎
        
        Args:
            thresholds: 规则阈值配置
            shooting_style: 投篮方式（一段式或二段式）
        """
        if thresholds is None:
            # 根据投篮方式选择默认阈值
            if shooting_style == ShootingStyle.ONE_MOTION:
                self.thresholds = RuleThresholds.for_one_motion()
            else:
                self.thresholds = RuleThresholds.for_two_motion()
        else:
            self.thresholds = thresholds
        
        self.shooting_style = self.thresholds.shooting_style
    
    def _get_player_reference_text(self, category: str, language: str = "zh") -> str:
        """
        获取NBA球星参考数据文本
        
        Args:
            category: 数据类别 (knee_bend, elbow_extension, release_height, body_balance)
            language: 语言 ('zh' 或 'en')
        
        Returns:
            格式化的球星参考文本
        """
        if category not in NBA_PLAYER_REFERENCES:
            return ""
        
        ref_data = NBA_PLAYER_REFERENCES[category]
        players = ref_data["players"]
        
        if language == "zh":
            lines = ["\n\n📊 NBA球星参考数据（视频分析，近似值）："]
            for player in players[:3]:  # 最多显示3个球星
                lines.append(f"  • {player['name_zh']} ({player['name']}): {player['value']}")
                lines.append(f"    {player['note']}")
        else:
            lines = ["\n\n📊 NBA Player References (Video analysis, approximate):"]
            for player in players[:3]:
                lines.append(f"  • {player['name']}: {player['value']}")
                lines.append(f"    {player['note_en']}")
        
        lines.append("\n※ 数据来源于公开视频分析，仅供参考" if language == "zh" else "\n※ Data from public video analysis, for reference only")
        
        return "\n".join(lines)
    
    def evaluate(
        self,
        phase_segments: list[PhaseSegment],
        frame_data_list: list[FrameData]
    ) -> EvaluationResult:
        """
        评估投篮姿势
        
        Args:
            phase_segments: 阶段片段列表
            frame_data_list: 所有帧数据
            
        Returns:
            评估结果
        """
        issues = []
        dimension_scores = []
        
        # 获取各阶段数据
        prep_segment = self._get_segment(phase_segments, ShootingPhase.PREPARATION)
        lift_segment = self._get_segment(phase_segments, ShootingPhase.LIFTING)
        release_segment = self._get_segment(phase_segments, ShootingPhase.RELEASE)
        follow_segment = self._get_segment(phase_segments, ShootingPhase.FOLLOW_THROUGH)
        
        # 1. 评估肘部伸展
        elbow_score, elbow_issues = self._evaluate_elbow(release_segment)
        dimension_scores.append(DimensionScore(
            name=self.RULES["elbow_alignment"]["name"],
            name_en=self.RULES["elbow_alignment"]["name_en"],
            score=elbow_score,
            weight=self.RULES["elbow_alignment"]["weight"],
            feedback=self._get_elbow_feedback(elbow_score),
            feedback_en=self._get_elbow_feedback_en(elbow_score)
        ))
        issues.extend(elbow_issues)
        
        # 2. 评估腿部发力
        knee_score, knee_issues = self._evaluate_knee(prep_segment)
        dimension_scores.append(DimensionScore(
            name=self.RULES["knee_drive"]["name"],
            name_en=self.RULES["knee_drive"]["name_en"],
            score=knee_score,
            weight=self.RULES["knee_drive"]["weight"],
            feedback=self._get_knee_feedback(knee_score),
            feedback_en=self._get_knee_feedback_en(knee_score)
        ))
        issues.extend(knee_issues)
        
        # 3. 评估身体平衡
        balance_score, balance_issues = self._evaluate_balance(release_segment)
        dimension_scores.append(DimensionScore(
            name=self.RULES["body_balance"]["name"],
            name_en=self.RULES["body_balance"]["name_en"],
            score=balance_score,
            weight=self.RULES["body_balance"]["weight"],
            feedback=self._get_balance_feedback(balance_score),
            feedback_en=self._get_balance_feedback_en(balance_score)
        ))
        issues.extend(balance_issues)
        
        # 4. 评估出手点
        release_score, release_issues = self._evaluate_release_point(release_segment)
        dimension_scores.append(DimensionScore(
            name=self.RULES["release_point"]["name"],
            name_en=self.RULES["release_point"]["name_en"],
            score=release_score,
            weight=self.RULES["release_point"]["weight"],
            feedback=self._get_release_feedback(release_score),
            feedback_en=self._get_release_feedback_en(release_score)
        ))
        issues.extend(release_issues)
        
        # 5. 评估跟随动作
        follow_score, follow_issues = self._evaluate_follow_through(follow_segment)
        dimension_scores.append(DimensionScore(
            name=self.RULES["follow_through"]["name"],
            name_en=self.RULES["follow_through"]["name_en"],
            score=follow_score,
            weight=self.RULES["follow_through"]["weight"],
            feedback=self._get_follow_feedback(follow_score),
            feedback_en=self._get_follow_feedback_en(follow_score)
        ))
        issues.extend(follow_issues)
        
        # 6. 评估动作连贯性（根据投篮方式调整权重）
        fluidity_score, fluidity_issues = self._evaluate_fluidity(phase_segments)
        
        # 7. 评估手脚协调
        coordination_score, coordination_issues = self._evaluate_hand_foot_coordination(
            prep_segment, lift_segment, frame_data_list
        )
        
        # 根据投篮方式调整权重（保持总和为100%）
        if self.shooting_style == ShootingStyle.ONE_MOTION:
            # 一段式：流畅性和协调性更重要
            elbow_weight = 0.22  # 25% -> 22%
            balance_weight = 0.17  # 20% -> 17%
            fluidity_weight = 0.10  # 8% -> 10%
            coordination_weight = 0.06  # 新增6%
        else:
            # 二段式：使用默认权重，协调性稍微不那么重要
            elbow_weight = dimension_scores[0].weight
            balance_weight = dimension_scores[2].weight
            fluidity_weight = self.RULES["fluidity"]["weight"]
            coordination_weight = 0.04  # 4%
        
        # 更新权重
        dimension_scores[0].weight = elbow_weight  # 肘部
        dimension_scores[2].weight = balance_weight  # 平衡
        
        dimension_scores.append(DimensionScore(
            name=self.RULES["fluidity"]["name"],
            name_en=self.RULES["fluidity"]["name_en"],
            score=fluidity_score,
            weight=fluidity_weight,
            feedback=self._get_fluidity_feedback(fluidity_score),
            feedback_en=self._get_fluidity_feedback_en(fluidity_score)
        ))
        issues.extend(fluidity_issues)
        
        dimension_scores.append(DimensionScore(
            name=self.RULES["hand_foot_coordination"]["name"],
            name_en=self.RULES["hand_foot_coordination"]["name_en"],
            score=coordination_score,
            weight=coordination_weight,
            feedback=self._get_coordination_feedback(coordination_score),
            feedback_en=self._get_coordination_feedback_en(coordination_score)
        ))
        issues.extend(coordination_issues)
        
        # 计算总分
        overall_score = sum(ds.weighted_score for ds in dimension_scores)
        
        # 确定评级
        rating = self._get_rating(overall_score)
        
        # 生成建议
        suggestions = self._generate_suggestions(issues)
        
        return EvaluationResult(
            overall_score=overall_score,
            rating=rating,
            dimension_scores=dimension_scores,
            issues=issues,
            suggestions=suggestions
        )
    
    def _get_segment(
        self,
        segments: list[PhaseSegment],
        phase: ShootingPhase
    ) -> Optional[PhaseSegment]:
        """获取指定阶段的片段"""
        for segment in segments:
            if segment.phase == phase:
                return segment
        return None
    
    def _get_avg_angle(
        self,
        segment: Optional[PhaseSegment],
        angle_name: str
    ) -> Optional[float]:
        """获取阶段的平均角度"""
        if not segment or not segment.frames:
            return None
        
        angles = []
        for frame in segment.frames:
            if frame.angles:
                value = getattr(frame.angles, angle_name, None)
                if value is not None:
                    angles.append(value)
        
        return sum(angles) / len(angles) if angles else None
    
    def _evaluate_elbow(
        self,
        release_segment: Optional[PhaseSegment]
    ) -> tuple[float, list[Issue]]:
        """评估肘部伸展"""
        issues = []
        
        if not release_segment:
            return 60.0, issues
        
        avg_elbow = self._get_avg_angle(release_segment, "elbow_angle")
        if avg_elbow is None:
            return 60.0, issues
        
        th = self.thresholds
        
        # 计算得分
        if avg_elbow >= th.elbow_release_ideal:
            score = 100.0
        elif avg_elbow >= th.elbow_release_min:
            # 线性插值
            ratio = (avg_elbow - th.elbow_release_min) / (th.elbow_release_ideal - th.elbow_release_min)
            score = 70.0 + ratio * 30.0
        else:
            # 角度不足
            ratio = avg_elbow / th.elbow_release_min
            score = ratio * 70.0
            
            # 获取球星参考
            player_ref_zh = self._get_player_reference_text("elbow_extension", "zh")
            player_ref_en = self._get_player_reference_text("elbow_extension", "en")
            
            issues.append(Issue(
                type=IssueType.ARM_NOT_EXTENDED,
                severity=IssueSeverity.MEDIUM if avg_elbow > 145 else IssueSeverity.HIGH,
                description=f"出手时手臂未完全伸展，肘部角度仅 {avg_elbow:.1f}° (标准: >160°)",
                description_en=f"Arm not fully extended at release, elbow angle only {avg_elbow:.1f}° (Standard: >160°)",
                phase=ShootingPhase.RELEASE,
                suggestion=f"出手时将手臂完全伸直，肘部应接近175°。想象用手指'放'球进筐，而不是'推'球{player_ref_zh}",
                suggestion_en=f"Fully extend your arm at release, elbow should be near 175°. Imagine 'placing' the ball in the hoop with your fingers, not 'pushing' it{player_ref_en}",
                reference="BEEF Method: 肘部在球下方，出手时完全伸展形成直线。研究表明完全伸展的手臂能提高出手稳定性和准确度",
                reference_en="BEEF Method: Elbow under ball, fully extended at release. Research shows full arm extension improves shot stability and accuracy"
            ))
        
        return score, issues
    
    def _evaluate_knee(
        self,
        prep_segment: Optional[PhaseSegment]
    ) -> tuple[float, list[Issue]]:
        """评估腿部发力"""
        issues = []
        
        if not prep_segment:
            return 60.0, issues
        
        # 找最小膝盖角度（最深下蹲）
        # 如果膝盖不在画面内（knee_angle=None），跳过这个评估维度
        min_knee = None
        for frame in prep_segment.frames:
            if frame.angles and frame.angles.knee_angle is not None:
                knee = frame.angles.knee_angle
                if min_knee is None or knee < min_knee:
                    min_knee = knee
        
        # 如果膝盖不可见，返回中等分数（不扣分也不加分）
        if min_knee is None:
            return 75.0, issues
        
        th = self.thresholds
        
        # 计算得分
        if min_knee <= th.knee_prep_ideal:
            score = 100.0
        elif min_knee <= th.knee_prep_max:
            ratio = (th.knee_prep_max - min_knee) / (th.knee_prep_max - th.knee_prep_ideal)
            score = 70.0 + ratio * 30.0
        else:
            # 下蹲不够 - 仅计算分数，不生成问题提示（用户反馈：这个标准没什么用）
            ratio = th.knee_prep_max / min_knee if min_knee > 0 else 0
            score = ratio * 70.0
            
            # 不再生成膝盖弯曲度的问题提示
            # issues.append(Issue(...))
        
        return score, issues
    
    def _evaluate_balance(
        self,
        release_segment: Optional[PhaseSegment]
    ) -> tuple[float, list[Issue]]:
        """评估身体平衡"""
        issues = []
        
        if not release_segment:
            return 60.0, issues
        
        avg_trunk = self._get_avg_angle(release_segment, "trunk_angle")
        if avg_trunk is None:
            return 60.0, issues
        
        th = self.thresholds
        
        # 计算得分
        if avg_trunk <= th.trunk_ideal:
            score = 100.0
        elif avg_trunk <= th.trunk_max_lean:
            ratio = (th.trunk_max_lean - avg_trunk) / (th.trunk_max_lean - th.trunk_ideal)
            score = 70.0 + ratio * 30.0
        else:
            # 身体倾斜过大
            ratio = th.trunk_max_lean / avg_trunk if avg_trunk > 0 else 0
            score = ratio * 70.0
            
            # 获取球星参考
            player_ref_zh = self._get_player_reference_text("body_balance", "zh")
            player_ref_en = self._get_player_reference_text("body_balance", "en")
            
            issues.append(Issue(
                type=IssueType.BODY_LEAN,
                severity=IssueSeverity.MEDIUM if avg_trunk < 15 else IssueSeverity.HIGH,
                description=f"出手时身体倾斜过大，角度为 {avg_trunk:.1f}° (优秀标准: <10°)",
                description_en=f"Excessive body lean at release, angle is {avg_trunk:.1f}° (Elite standard: <10°)",
                phase=ShootingPhase.RELEASE,
                suggestion=f"出手时保持躯干接近垂直（<10°倾斜）。核心收紧，想象头顶有一条垂直线。身体平衡是BEEF方法的基础{player_ref_zh}",
                suggestion_en=f"Keep trunk nearly vertical at release (<10° lean). Engage core, imagine a vertical line through your head. Balance is the foundation of BEEF method{player_ref_en}",
                reference="生物力学研究（Frontiers in Sports 2023）：优秀射手（≥70%命中率）在出手时显示出显著更小的躯干前倾",
                reference_en="Biomechanical research (Frontiers in Sports 2023): Proficient shooters (≥70% accuracy) show significantly less forward trunk lean at release"
            ))
        
        return score, issues
    
    def _evaluate_release_point(
        self,
        release_segment: Optional[PhaseSegment]
    ) -> tuple[float, list[Issue]]:
        """评估出手点"""
        issues = []
        
        if not release_segment:
            return 60.0, issues
        
        avg_shoulder = self._get_avg_angle(release_segment, "shoulder_angle")
        if avg_shoulder is None:
            return 60.0, issues
        
        th = self.thresholds
        
        # 计算得分
        if avg_shoulder >= th.shoulder_release_ideal:
            score = 100.0
        elif avg_shoulder >= th.shoulder_release_min:
            ratio = (avg_shoulder - th.shoulder_release_min) / (th.shoulder_release_ideal - th.shoulder_release_min)
            score = 70.0 + ratio * 30.0
        else:
            ratio = avg_shoulder / th.shoulder_release_min if th.shoulder_release_min > 0 else 0
            score = ratio * 70.0
            
            # 获取球星参考
            player_ref_zh = self._get_player_reference_text("release_height", "zh")
            player_ref_en = self._get_player_reference_text("release_height", "en")
            
            issues.append(Issue(
                type=IssueType.LOW_RELEASE,
                severity=IssueSeverity.HIGH if avg_shoulder < 65 else IssueSeverity.MEDIUM,
                description=f"出手点偏低，肩部角度为 {avg_shoulder:.1f}° (理想: >90°)",
                description_en=f"Low release point, shoulder angle is {avg_shoulder:.1f}° (Ideal: >90°)",
                phase=ShootingPhase.RELEASE,
                suggestion=f"将球举到投篮眼上方（眉毛位置）再出手。出手点应在头顶上方，肩部角度>90°。更高的出手点意味着更难被防守{player_ref_zh}",
                suggestion_en=f"Raise the ball above your shooting eye (eyebrow level) before release. Release point should be above head, shoulder angle >90°. Higher release = harder to block{player_ref_en}",
                reference="研究证实优秀射手的出手高度显著更高。Stephen Curry的出手点在其右眼正上方，肩部角度接近95°",
                reference_en="Research confirms proficient shooters achieve significantly greater release height. Stephen Curry's release point is directly above his right eye, shoulder angle near 95°"
            ))
        
        return score, issues
    
    def _evaluate_follow_through(
        self,
        follow_segment: Optional[PhaseSegment]
    ) -> tuple[float, list[Issue]]:
        """评估跟随动作"""
        issues = []
        
        if not follow_segment:
            # 没有检测到跟随阶段
            issues.append(Issue(
                type=IssueType.NO_FOLLOW_THROUGH,
                severity=IssueSeverity.HIGH,
                description="未检测到明显的跟随动作 - 这是BEEF方法的关键要素",
                description_en="No clear follow-through detected - this is a key element of BEEF method",
                phase=ShootingPhase.FOLLOW_THROUGH,
                suggestion="出手后手臂保持伸展，手腕自然下压（如'掏饼干罐'），手指指向目标。保持此姿势1-2秒，确保完整的跟随动作",
                suggestion_en="After release, keep arm extended, wrist naturally snapped down (like 'reaching into cookie jar'), fingers pointing at target. Hold this position 1-2 seconds for complete follow-through",
                reference="BEEF Method - Follow Through: 这是投篮四要素之一。完整的跟随动作确保球的后旋稳定，研究表明球旋转的稳定性是横向准确度的重要预测因素",
                reference_en="BEEF Method - Follow Through: One of the four fundamentals. Complete follow-through ensures stable ball backspin. Research shows spin stability is a strong predictor of lateral accuracy"
            ))
            return 50.0, issues
        
        # 检查是否有手腕角度数据
        wrist_angles = []
        for frame in follow_segment.frames:
            if frame.angles and frame.angles.wrist_angle is not None:
                wrist_angles.append(frame.angles.wrist_angle)
        
        if not wrist_angles:
            return 70.0, issues
        
        avg_wrist = sum(wrist_angles) / len(wrist_angles)
        th = self.thresholds
        
        # 手腕角度越小表示弯曲越多
        if avg_wrist <= th.wrist_follow_min:
            score = 100.0
        else:
            ratio = th.wrist_follow_min / avg_wrist if avg_wrist > 0 else 0
            score = ratio * 100.0
        
        return score, issues
    
    def _evaluate_fluidity(
        self,
        segments: list[PhaseSegment]
    ) -> tuple[float, list[Issue]]:
        """评估动作连贯性"""
        issues = []
        
        # 检查是否有完整的阶段
        phases_found = [s.phase for s in segments]
        
        required_phases = [
            ShootingPhase.PREPARATION,
            ShootingPhase.LIFTING,
            ShootingPhase.RELEASE
        ]
        
        missing_phases = [p for p in required_phases if p not in phases_found]
        
        if missing_phases:
            issues.append(Issue(
                type=IssueType.RUSHED_SHOT,
                severity=IssueSeverity.MEDIUM,
                description="投篮动作可能过于仓促，未检测到完整阶段。缺失阶段可能影响节奏和准确性",
                description_en="Shot may be rushed, incomplete phases detected. Missing phases may affect rhythm and accuracy",
                suggestion="建立完整的投篮节奏：1)准备姿势(下蹲) 2)向上举球 3)高点出手 4)手腕跟随。每个阶段都很重要，不要急于出手",
                suggestion_en="Establish complete shooting rhythm: 1)Set stance(dip) 2)Lift ball 3)Release at apex 4)Follow through. Each phase matters, don't rush the shot",
                reference="运动科学研究表明：流畅的动作序列比机械重复更重要。优秀射手使用动态补偿来确保最终出手的稳定性",
                reference_en="Sports science research shows: Smooth motion sequence is more important than mechanical repetition. Elite shooters use dynamic compensation to ensure final release stability"
            ))
            score = 60.0
        else:
            # 检查阶段顺序
            phase_order = [s.phase for s in segments if s.phase != ShootingPhase.UNKNOWN]
            
            expected_order = [
                ShootingPhase.PREPARATION,
                ShootingPhase.LIFTING,
                ShootingPhase.RELEASE,
                ShootingPhase.FOLLOW_THROUGH
            ]
            
            # 简单的顺序检查
            is_ordered = True
            last_idx = -1
            for phase in phase_order:
                if phase in expected_order:
                    idx = expected_order.index(phase)
                    if idx < last_idx:
                        is_ordered = False
                        break
                    last_idx = idx
            
            if is_ordered:
                score = 90.0
            else:
                score = 70.0
                issues.append(Issue(
                    type=IssueType.RUSHED_SHOT,
                    severity=IssueSeverity.LOW,
                    description="动作阶段顺序可能不够连贯",
                    description_en="Phase sequence may not be smooth",
                    suggestion="练习流畅的投篮动作，从下蹲到出手一气呵成",
                    suggestion_en="Practice a fluid shooting motion, from dip to release in one smooth motion"
                ))
        
        return score, issues
    
    def _evaluate_hand_foot_coordination(
        self,
        prep_segment: Optional[PhaseSegment],
        lift_segment: Optional[PhaseSegment],
        frame_data_list: list[FrameData]
    ) -> tuple[float, list[Issue]]:
        """
        评估手脚协调性（检测是否手快脚慢）
        
        手快脚慢：腿部还在下蹲或刚开始伸展时，手部已经开始向上举球
        正确的协调：腿部发力和手部举球应该同步或先腿后手
        """
        issues = []
        
        if not prep_segment or not lift_segment:
            return 70.0, issues
        
        # 获取准备阶段到上升阶段的过渡期帧数据
        transition_start = prep_segment.end_frame - 5  # 准备阶段末尾5帧
        transition_end = lift_segment.start_frame + 10  # 上升阶段开始10帧
        
        transition_frames = [
            fd for fd in frame_data_list 
            if transition_start <= fd.frame_number <= transition_end and fd.angles
        ]
        
        if len(transition_frames) < 5:
            return 70.0, issues
        
        # 分析手腕高度变化和膝盖角度变化
        hand_lift_start = None  # 手开始上举的帧
        leg_extend_start = None  # 腿开始伸展的帧
        
        for i in range(1, len(transition_frames)):
            prev_frame = transition_frames[i - 1]
            curr_frame = transition_frames[i]
            
            # 检测手部开始上举（手腕Y坐标减小，表示向上移动）
            if hand_lift_start is None:
                wrist_delta = curr_frame.wrist_y - prev_frame.wrist_y
                if wrist_delta < -0.015:  # 手腕明显向上移动
                    hand_lift_start = curr_frame.frame_number
            
            # 检测腿部开始伸展（膝盖角度增大）
            # 只有当膝盖可见时才检测
            if leg_extend_start is None:
                if (curr_frame.angles.knee_angle is not None and 
                    prev_frame.angles.knee_angle is not None):
                    knee_delta = curr_frame.angles.knee_angle - prev_frame.angles.knee_angle
                    if knee_delta > 3.0:  # 膝盖角度明显增大（伸展）
                        leg_extend_start = curr_frame.frame_number
        
        # 判断协调性
        # 如果膝盖不可见（leg_extend_start为None），跳过手脚协调评估
        if not leg_extend_start:
            # 膝盖不在画面内，无法评估下肢动作，返回中等分数
            return 75.0, issues
        
        if hand_lift_start and leg_extend_start:
            coordination_gap = hand_lift_start - leg_extend_start
            
            if coordination_gap > 5:  # 手比腿早5帧以上
                # 手快脚慢
                issues.append(Issue(
                    type=IssueType.HAND_FAST_FOOT_SLOW,
                    severity=IssueSeverity.HIGH,
                    description=f"存在明显的手快脚慢问题：手部在腿部发力前约{coordination_gap}帧就开始上举",
                    description_en=f"Clear hand-fast-foot-slow issue: hands lift ~{coordination_gap} frames before leg drive",
                    suggestion="投篮时注意手脚协调：应该先感受腿部向上发力，然后手部跟随举球。可以练习：1)下蹲时球保持在胸前低位 2)腿部开始向上蹬地 3)同时或稍后手臂开始上举。避免腿还在蹲时手就开始举球",
                    suggestion_en="Focus on hand-foot coordination: Feel leg drive first, then hands follow. Practice: 1)Keep ball low at chest during dip 2)Push up with legs 3)Lift arms simultaneously or slightly after. Avoid lifting hands while legs are still dipping",
                    reference="专业教练强调：投篮是一个由下至上的发力链，腿部力量应该传导到手部。手快脚慢会导致上下身脱节，影响力量传递和出手稳定性",
                    reference_en="Professional coaches emphasize: Shooting is a bottom-up kinetic chain, leg power should transfer to hands. Hand-fast-foot-slow causes disconnection between upper and lower body, affecting power transfer and release stability",
                    frame=hand_lift_start,
                    phase=ShootingPhase.LIFTING
                ))
                score = max(40.0, 100.0 - coordination_gap * 5)  # 每帧差扣5分
            elif coordination_gap > 2:  # 手比腿早2-5帧
                # 轻微手快脚慢
                issues.append(Issue(
                    type=IssueType.HAND_FAST_FOOT_SLOW,
                    severity=IssueSeverity.MEDIUM,
                    description="手脚协调有轻微问题，手部略早于腿部发力",
                    description_en="Minor hand-foot coordination issue, hands slightly early",
                    suggestion="尝试让腿部发力和手部举球更同步，感受腿部向上蹬地的力量",
                    suggestion_en="Try to synchronize leg drive and hand lift better, feel the upward push from legs",
                    reference="良好的协调可以提高力量传递效率",
                    reference_en="Good coordination improves power transfer efficiency",
                    frame=hand_lift_start,
                    phase=ShootingPhase.LIFTING
                ))
                score = max(70.0, 100.0 - coordination_gap * 5)
            elif -2 <= coordination_gap <= 2:  # 基本同步
                score = 100.0
            else:  # 腿先发力（coordination_gap < -2）
                # 这是好的，腿先发力
                score = 95.0
        else:
            # 无法检测到明确的启动点
            score = 75.0
        
        return score, issues
    
    def _get_rating(self, score: float) -> str:
        """根据分数获取评级"""
        for rating, info in self.RATINGS.items():
            if score >= info["min"]:
                return rating
        return "needs_improvement"
    
    def _generate_suggestions(self, issues: list[Issue]) -> list[dict]:
        """生成改进建议"""
        suggestions = []
        
        # 按严重程度排序
        severity_order = {IssueSeverity.HIGH: 0, IssueSeverity.MEDIUM: 1, IssueSeverity.LOW: 2}
        sorted_issues = sorted(issues, key=lambda x: severity_order.get(x.severity, 3))
        
        for i, issue in enumerate(sorted_issues[:5]):  # 最多5条建议
            suggestions.append({
                "priority": i + 1,
                "title": self._get_suggestion_title(issue.type),
                "title_en": self._get_suggestion_title_en(issue.type),
                "description": issue.suggestion,
                "description_en": issue.suggestion_en,
                "related_issue": issue.type.value
            })
        
        return suggestions
    
    def _get_suggestion_title(self, issue_type: IssueType) -> str:
        """获取建议标题"""
        titles = {
            IssueType.ELBOW_FLARE: "保持肘部内收",
            IssueType.ARM_NOT_EXTENDED: "完全伸展手臂",
            IssueType.INSUFFICIENT_KNEE_BEND: "加深膝盖弯曲",
            IssueType.BODY_LEAN: "保持身体平衡",
            IssueType.LOW_RELEASE: "提高出手点",
            IssueType.NO_FOLLOW_THROUGH: "增加跟随动作",
            IssueType.RUSHED_SHOT: "放慢投篮节奏",
            IssueType.NO_LEG_DRIVE: "利用腿部力量",
            IssueType.HAND_FAST_FOOT_SLOW: "改善手脚协调",
        }
        return titles.get(issue_type, "改进投篮姿势")
    
    def _get_suggestion_title_en(self, issue_type: IssueType) -> str:
        """获取建议标题（英文）"""
        titles = {
            IssueType.ELBOW_FLARE: "Keep Elbow In",
            IssueType.ARM_NOT_EXTENDED: "Fully Extend Arm",
            IssueType.INSUFFICIENT_KNEE_BEND: "Deepen Knee Bend",
            IssueType.BODY_LEAN: "Maintain Body Balance",
            IssueType.LOW_RELEASE: "Raise Release Point",
            IssueType.NO_FOLLOW_THROUGH: "Add Follow Through",
            IssueType.RUSHED_SHOT: "Slow Down Shot",
            IssueType.NO_LEG_DRIVE: "Use Leg Power",
            IssueType.HAND_FAST_FOOT_SLOW: "Improve Hand-Foot Coordination",
        }
        return titles.get(issue_type, "Improve Shooting Form")
    
    # 反馈文案方法 - Based on BEEF Method and professional standards
    def _get_elbow_feedback(self, score: float) -> str:
        if score >= 90:
            return "✓ 肘部伸展优秀（>170°），符合BEEF标准。完全伸展的手臂提供更好的稳定性和准确度"
        elif score >= 70:
            return "△ 肘部伸展基本达标（160-170°），建议出手时更完全地伸直手臂以提高稳定性"
        else:
            return "✗ 肘部伸展不足（<160°）。BEEF方法要求出手时手臂接近完全伸直（175°左右）"
    
    def _get_elbow_feedback_en(self, score: float) -> str:
        if score >= 90:
            return "✓ Excellent elbow extension (>170°), meets BEEF standard. Full arm extension provides better stability and accuracy"
        elif score >= 70:
            return "△ Elbow extension acceptable (160-170°), recommend fuller extension at release for improved stability"
        else:
            return "✗ Insufficient elbow extension (<160°). BEEF method requires near-full arm extension at release (~175°)"
    
    def _get_knee_feedback(self, score: float) -> str:
        if score >= 90:
            return "✓ 膝盖弯曲适度（通常100-130°），符合BEEF平衡原则。关键是保持**稳定可控的动作**。科学研究证实优秀射手的特征是更受控的膝盖运动，而非固定角度"
        elif score >= 70:
            return "△ 膝盖弯曲基本合理，但可以优化。建议找到你感觉**舒适且能控制的深度**（一般在100-130°范围），避免过深或过浅。重点是动作的稳定性和可控性"
        else:
            return "✗ 膝盖弯曲不当（过浅或过深）。BEEF方法要求双脚与肩同宽，膝盖适度弯曲以保持平衡。科学研究强调：**动作的控制性**比具体角度更重要。建议尝试100-130°范围，找到适合你的深度"
    
    def _get_knee_feedback_en(self, score: float) -> str:
        if score >= 90:
            return "✓ Appropriate knee bend (typically 100-130°), meets BEEF balance principle. Key is maintaining **stable, controlled motion**. Scientific research confirms elite shooters' characteristic is more controlled knee movement, not a fixed angle"
        elif score >= 70:
            return "△ Knee bend is reasonable but can be optimized. Recommend finding **your comfortable and controlled depth** (generally 100-130° range), avoiding too deep or too shallow. Focus on motion stability and control"
        else:
            return "✗ Improper knee bend (too shallow or too deep). BEEF method requires feet shoulder-width apart, knees moderately bent for balance. Scientific research emphasizes: **motion control** matters more than specific angle. Try 100-130° range to find your optimal depth"
    
    def _get_balance_feedback(self, score: float) -> str:
        if score >= 90:
            return "✓ 躯干接近垂直（<5°倾斜），优秀的平衡控制。研究表明这是≥70%命中率射手的典型特征"
        elif score >= 70:
            return "△ 躯干基本垂直（5-10°倾斜），可接受范围。尽量保持更垂直的姿态以提高稳定性"
        else:
            return "✗ 躯干倾斜过大（>10°）。生物力学研究显示：优秀射手在出手时躯干倾斜显著更小"
    
    def _get_balance_feedback_en(self, score: float) -> str:
        if score >= 90:
            return "✓ Trunk nearly vertical (<5° lean), excellent balance control. Research shows this is typical of ≥70% accuracy shooters"
        elif score >= 70:
            return "△ Trunk fairly vertical (5-10° lean), acceptable range. Try to maintain more vertical posture for improved stability"
        else:
            return "✗ Excessive trunk lean (>10°). Biomechanical research shows: Proficient shooters have significantly less trunk lean at release"
    
    def _get_release_feedback(self, score: float) -> str:
        if score >= 90:
            return "✓ 出手点高（肩部角度>90°），符合专业标准。研究确认更高的出手点与更高命中率相关"
        elif score >= 70:
            return "△ 出手点适中（75-90°），建议将球举到投篮眼上方（眉毛位置）以提高出手点"
        else:
            return "✗ 出手点偏低（<75°）。球应举到投篮眼正上方再出手，肩部角度应>90°"
    
    def _get_release_feedback_en(self, score: float) -> str:
        if score >= 90:
            return "✓ High release point (shoulder angle >90°), meets professional standard. Research confirms higher release correlates with better accuracy"
        elif score >= 70:
            return "△ Moderate release point (75-90°), recommend raising ball above shooting eye (eyebrow level) for higher release"
        else:
            return "✗ Low release point (<75°). Ball should be raised directly above shooting eye before release, shoulder angle should be >90°"
    
    def _get_follow_feedback(self, score: float) -> str:
        if score >= 90:
            return "✓ 跟随动作完整，手腕下压充分。BEEF方法的第四要素，确保球的稳定旋转"
        elif score >= 70:
            return "△ 有跟随动作但不够完整。出手后保持手臂伸展，手腕自然下压1-2秒"
        else:
            return "✗ 跟随动作不足。BEEF方法要求：手臂完全伸展，手腕下压（如'掏饼干罐'），手指指向篮筐"
    
    def _get_follow_feedback_en(self, score: float) -> str:
        if score >= 90:
            return "✓ Complete follow-through with good wrist snap. The 4th element of BEEF method, ensures stable ball spin"
        elif score >= 70:
            return "△ Has follow-through but not complete. Keep arm extended after release, wrist naturally snapped down for 1-2 seconds"
        else:
            return "✗ Insufficient follow-through. BEEF method requires: Full arm extension, wrist snap (like 'reaching into cookie jar'), fingers pointing at rim"
    
    def _get_fluidity_feedback(self, score: float) -> str:
        if score >= 90:
            return "✓ 动作流畅连贯，完整的投篮节奏。研究表明流畅的序列比机械重复更重要"
        elif score >= 70:
            return "△ 动作基本流畅，建议建立更清晰的节奏：准备→上举→出手→跟随"
        else:
            return "✗ 动作节奏不够流畅。建立完整序列：1)准备 2)举球 3)高点出手 4)跟随。不要急于出手"
    
    def _get_fluidity_feedback_en(self, score: float) -> str:
        if score >= 90:
            return "✓ Smooth and fluid motion, complete shooting rhythm. Research shows fluid sequence is more important than mechanical repetition"
        elif score >= 70:
            return "△ Motion is fairly fluid, recommend establishing clearer rhythm: Set→Lift→Release→Follow"
        else:
            return "✗ Motion rhythm not fluid enough. Establish complete sequence: 1)Set 2)Lift 3)Release at apex 4)Follow. Don't rush the shot"
    
    def _get_coordination_feedback(self, score: float) -> str:
        if score >= 90:
            return "✓ 手脚协调优秀，腿部发力和手部举球同步良好。力量传递顺畅，符合由下至上的发力链原则"
        elif score >= 70:
            return "△ 手脚协调基本合理，但有轻微的不同步。建议感受腿部向上蹬地的力量，让手臂跟随腿部发力"
        else:
            return "✗ 存在明显的手快脚慢问题：腿还在下蹲时手就开始上举。这会导致上下身脱节，影响力量传递。应该先腿部发力，手部跟随"
    
    def _get_coordination_feedback_en(self, score: float) -> str:
        if score >= 90:
            return "✓ Excellent hand-foot coordination, leg drive and hand lift are well synchronized. Smooth power transfer follows bottom-up kinetic chain principle"
        elif score >= 70:
            return "△ Hand-foot coordination is reasonable but slightly out of sync. Feel the upward push from legs, let arms follow leg drive"
        else:
            return "✗ Clear hand-fast-foot-slow issue: hands lift while legs are still dipping. This causes disconnection, affecting power transfer. Legs should drive first, hands follow"
