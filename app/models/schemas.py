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
    image_url: str
    angles: Optional[JointAngles] = None


class DimensionScore(BaseModel):
    """单项评分"""
    name: str
    name_en: str
    score: float
    weight: float
    weighted_score: float
    feedback: str
    feedback_en: str = ""


class TemplateComparison(BaseModel):
    """模板对比数据"""
    template_id: str
    template_name: str
    comparisons: list[dict]  # 对比数据数组


class AnalysisResult(BaseModel):
    """分析结果"""
    task_id: str
    video_filename: str
    overall_score: float
    rating: Rating
    dimension_scores: list[DimensionScore]
    phases: list[PhaseMetrics]
    issues: list[Issue]
    suggestions: list[Suggestion]
    key_frames: list[KeyFrame]
    annotated_video_url: Optional[str] = None
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
