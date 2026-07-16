"""Pydantic schemas for request/response models"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ShootingPhase(str, Enum):
    """投篮阶段"""
    PREPARATION = "preparation"  # 准备阶段
    LIFTING = "lifting"          # 上升阶段
    RELEASE = "release"          # 出手阶段
    FOLLOW_THROUGH = "follow_through"  # 跟随阶段
    # 关键帧（4帧版本 - 发力连贯性检测）
    SYNC_FRAME_1 = "sync_frame_1"      # 手脚同步检测帧1：沉球点（手腕最低点后上升）
    SYNC_FRAME_2 = "sync_frame_2"      # 手脚同步检测帧2：手上升后（沉球点后N帧）
    MAX_HOLD_FRAME = "max_hold_frame"  # 发力脱节检测帧1：最高持球点（手腕高+肘角未伸展）
    RELEASE_FRAME = "release_frame"    # 发力脱节检测帧2：出手点（手腕最高+肘角伸展）
    # 关键帧（8帧版本 - 细化动作节点，与 phase_detector.ShootingPhase 对齐）
    KNEE_MIN_FRAME = "knee_min_frame"            # 最低蹲点：膝盖弯曲角度最小的帧
    ELBOW_MIN_FRAME = "elbow_min_frame"          # 最紧折叠点：手肘角度最小的帧
    WRIST_PEAK_FRAME = "wrist_peak_frame"        # 手腕最高点：手腕物理位置最高的帧
    FOLLOW_THROUGH_FRAME = "follow_through_frame"  # 跟随定型点：出手后手腕稳定的帧


class IssueSeverity(str, Enum):
    """问题严重程度"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class IssueType(str, Enum):
    """问题类型"""
    ELBOW_FLARE = "elbow_flare"           # 肘部外展
    WRIST_FLIP = "wrist_flip"             # 手腕甩动
    NO_FOLLOW_THROUGH = "no_follow_through"  # 缺少跟随
    BODY_LEAN = "body_lean"               # 身体倾斜
    LOW_RELEASE = "low_release"           # 出手点过低
    KNEE_COLLAPSE = "knee_collapse"       # 膝盖内扣
    INSUFFICIENT_KNEE_BEND = "insufficient_knee_bend"  # 膝盖弯曲不足
    ARM_NOT_EXTENDED = "arm_not_extended"  # 手臂未完全伸展
    RUSHED_SHOT = "rushed_shot"           # 仓促出手
    NO_LEG_DRIVE = "no_leg_drive"         # 缺少腿部发力
    HAND_FAST_FOOT_SLOW = "hand_fast_foot_slow"  # 手快脚慢
    TEMPLATE_DIFFERENCE = "template_difference"  # 模板差异建议
    # 新增后台分析问题类型（发力连贯性）
    KNEE_BENDING_AFTER_DIP = "knee_bending_after_dip"  # 沉球后膝盖继续弯曲（手快脚慢）
    INSUFFICIENT_KNEE_EXTENSION = "insufficient_knee_extension"  # 出手时膝盖未伸直
    POWER_DISCONNECTION = "power_disconnection"  # 发力脱节


class Rating(str, Enum):
    """评级"""
    EXCELLENT = "excellent"  # 优秀 90-100
    GOOD = "good"            # 良好 75-89
    FAIR = "fair"            # 一般 60-74
    NEEDS_IMPROVEMENT = "needs_improvement"  # 需改进 <60


class Point2D(BaseModel):
    """2D坐标点"""
    x: float
    y: float


class Point3D(BaseModel):
    """3D坐标点"""
    x: float
    y: float
    z: float
    visibility: float = 1.0


class JointAngles(BaseModel):
    """关节角度"""
    elbow_angle: float = Field(..., description="肘部角度 (肩-肘-腕)")
    shoulder_angle: float = Field(..., description="肩部角度 (髋-肩-肘)")
    knee_angle: float = Field(..., description="膝盖角度 (髋-膝-踝)")
    trunk_angle: float = Field(..., description="躯干倾斜角度")
    wrist_angle: Optional[float] = Field(None, description="手腕角度 (肘-腕-食指)")


class FrameAnalysis(BaseModel):
    """单帧分析结果"""
    frame_number: int
    timestamp: float  # 秒
    landmarks: Optional[dict] = None  # 关键点坐标
    angles: Optional[JointAngles] = None
    phase: Optional[ShootingPhase] = None
    confidence: float = 0.0


class PhaseMetrics(BaseModel):
    """阶段指标"""
    name: ShootingPhase
    frame_range: tuple[int, int]
    time_range: tuple[float, float]
    avg_knee_angle: Optional[float] = None
    avg_elbow_angle: Optional[float] = None
    max_wrist_height: Optional[float] = None
    score: float = 0.0
    issues: list[str] = []


class Issue(BaseModel):
    """检测到的问题"""
    type: IssueType
    severity: IssueSeverity
    description: str
    description_en: str
    frame: Optional[int] = None
    suggestion: str


class Suggestion(BaseModel):
    """改进建议"""
    priority: int
    title: str
    description: str
    related_issue: Optional[IssueType] = None


class KeyFrame(BaseModel):
    """关键帧"""
    phase: ShootingPhase
    frame_number: int
    timestamp: float
    image_url: Optional[str] = None  # 图片URL（可能在生成后填充）
    angles: Optional[JointAngles] = None


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


class CoordinationIssue(BaseModel):
    """发力连贯性问题检测结果"""
    issue_type: CoordinationIssueType
    detected: bool
    severity: CoordinationSeverity
    frame_1: Optional[KeyFrame] = None  # 检测用的第一帧
    frame_2: Optional[KeyFrame] = None  # 检测用的第二帧
    knee_angle_1: Optional[float] = None  # 第一帧膝盖角度
    knee_angle_2: Optional[float] = None  # 第二帧膝盖角度
    description: str
    description_en: str
    suggestion: str
    suggestion_en: str


class TemplateComparison(BaseModel):
    """模板对比数据"""
    template_id: str
    template_name: str
    comparisons: list[dict]  # 对比数据数组


class AnalysisResult(BaseModel):
    """分析结果 - 发力连贯性检测"""
    task_id: str
    video_filename: str
    coordination_issues: list[CoordinationIssue]  # 发力连贯性检测结果
    key_frames: list[KeyFrame]  # 所有检测用的关键帧
    annotated_video_url: Optional[str] = None
    skeleton_video_url: Optional[str] = None  # 骨骼运动视频URL
    total_frames: int
    fps: float
    duration: float
    template_comparison: Optional[TemplateComparison] = None  # 模板对比（可选）


class UploadResponse(BaseModel):
    """上传响应"""
    task_id: str
    message: str
    filename: str


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str
    status: TaskStatus
    progress: int = 0  # 0-100
    message: str = ""
    result: Optional[AnalysisResult] = None
    error: Optional[str] = None
