"""
MediaPipe Pose Detection Module
使用 MediaPipe Tasks API 进行人体姿态检测
"""

import cv2
import numpy as np
import mediapipe as mp
from dataclasses import dataclass
from typing import Optional
from enum import IntEnum
from pathlib import Path
import urllib.request


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
    z: float  # 度估计
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


# 模型文件路径
MODEL_PATH = Path(__file__).parent.parent.parent / "models" / "pose_landmarker.task"
# 使用固定版本，避免 latest 标签导致模型静默更新、检测结果不一致
DEFAULT_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/0_2024-03-19/pose_landmarker_heavy.task"


def download_model():
    """下载/加载 MediaPipe 模型文件"""
    from app.config import settings

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

    # 优先使用配置的固定模型 URL
    model_url = settings.pose_model_url or DEFAULT_MODEL_URL

    if not MODEL_PATH.exists():
        print(f"[MediaPipe] Downloading model from {model_url}")
        try:
            urllib.request.urlretrieve(model_url, str(MODEL_PATH))
            print(f"[MediaPipe] Model saved to {MODEL_PATH}")
        except Exception as e:
            print(f"[MediaPipe] Failed to download from {model_url}: {e}")
            # 回退到默认 URL
            if model_url != DEFAULT_MODEL_URL:
                print(f"[MediaPipe] Falling back to default URL")
                urllib.request.urlretrieve(DEFAULT_MODEL_URL, str(MODEL_PATH))
                print(f"[MediaPipe] Model saved to {MODEL_PATH}")
            else:
                raise

    # 打印模型文件信息，便于调试
    if MODEL_PATH.exists():
        import hashlib
        with open(MODEL_PATH, 'rb') as f:
            md5 = hashlib.md5(f.read()).hexdigest()
        print(f"[MediaPipe] Using model file: {MODEL_PATH} (MD5: {md5})")

    return MODEL_PATH


class PoseDetector:
    """姿态检测器 - 使用 MediaPipe Tasks API"""

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
            model_complexity: 模型复杂度 (0, 1, 2) - 在新 API 中使用不同模型文件
        """
        # 下载模型文件
        model_path = download_model()

        # 创建 PoseLandmarker
        # 使用 IMAGE 模式：每帧独立检测，不依赖时序跟踪
        # 之前用 VIDEO 模式但传入的时间戳不准确（每次+1ms），
        # 导致 MediaPipe 光流跟踪器预测偏移，骨骼与身体不对齐
        BaseOptions = mp.tasks.BaseOptions
        PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
        VisionRunningMode = mp.tasks.vision.RunningMode

        options = PoseLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=VisionRunningMode.IMAGE,
            min_pose_detection_confidence=min_detection_confidence,
            min_pose_presence_confidence=min_tracking_confidence,
            min_tracking_confidence=min_tracking_confidence,
            output_segmentation_masks=False
        )

        self.landmarker = mp.tasks.vision.PoseLandmarker.create_from_options(options)

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

    def detect(self, frame: np.ndarray, timestamp_ms: int = None) -> Optional[PoseResult]:
        """
        检测单帧图像中的人体姿态

        Args:
            frame: BGR 格式的图像
            timestamp_ms: 未使用（保留兼容性），IMAGE 模式不需要时间戳

        Returns:
            PoseResult 或 None (如果未检测到)
        """
        height, width = frame.shape[:2]

        # 转换为 RGB (MediaPipe 需要 RGB 输入)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # 创建 MediaPipe Image
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

        # IMAGE 模式：每帧独立检测，不需要时间戳
        results = self.landmarker.detect(mp_image)

        if not results.pose_landmarks or len(results.pose_landmarks) == 0:
            return None

        # 获取第一个检测到的人体
        pose_landmarks = results.pose_landmarks[0]

        # 提取关键点
        landmarks = {}
        total_visibility = 0.0

        for idx, landmark in enumerate(pose_landmarks):
            landmarks[idx] = Landmark(
                x=landmark.x,
                y=landmark.y,
                z=landmark.z,
                visibility=landmark.visibility if hasattr(landmark, 'visibility') else 1.0
            )
            total_visibility += landmarks[idx].visibility

        # 计算平均置信度
        avg_confidence = total_visibility / len(landmarks) if landmarks else 0.0

        return PoseResult(
            landmarks=landmarks,
            confidence=avg_confidence,
            image_width=width,
            image_height=height,
            raw_landmarks=pose_landmarks
        )

    def draw_landmarks(
        self,
        frame: np.ndarray,
        pose_result: PoseResult,
        draw_connections: bool = True,
        highlight_shooting_arm: bool = True,
        shooting_hand: str = "right",
        crop_info: Optional[dict] = None
    ) -> np.ndarray:
        """
        在图像上绘制关键点和骨骼连接（不绘制面部关键点）

        Args:
            frame: BGR 格式的图像
            pose_result: 姿态检测结果
            draw_connections: 是否绘制骨骼连接
            highlight_shooting_arm: 是否高亮投篮手臂（已废弃，现在统一大小）
            shooting_hand: 投篮手 ("left" 或 "right")
            crop_info: 裁剪信息字典，包含 crop_x1, crop_y1, orig_width, orig_height
                       如果提供，会将归一化坐标转换为裁剪后的相对坐标

        Returns:
            绘制后的图像
        """
        annotated = frame.copy()

        # 使用当前帧的实际尺寸（裁剪后的尺寸）
        height, width = frame.shape[:2]

        # 如果有裁剪信息，需要调整坐标计算方式
        if crop_info:
            orig_width = crop_info['orig_width']
            orig_height = crop_info['orig_height']
            crop_x1 = crop_info['crop_x1']
            crop_y1 = crop_info['crop_y1']

            def get_pixel_coords(landmark):
                """将归一化坐标转换为裁剪后图像的像素坐标"""
                orig_x = landmark.x * orig_width
                orig_y = landmark.y * orig_height
                # 转换为裁剪后的相对坐标
                cropped_x = orig_x - crop_x1
                cropped_y = orig_y - crop_y1
                return (int(cropped_x), int(cropped_y))
        else:
            def get_pixel_coords(landmark):
                """将归一化坐标转换为像素坐标"""
                return (int(landmark.x * width), int(landmark.y * height))

        # 自定义绘制关键点（排除面部关键点 0-10）
        # 只绘制身体关键点（11-32）
        body_landmarks = list(range(11, 33))

        # 统一的关键点大小（5像素，增大以更明显）
        point_radius = 5

        print(f"[draw_landmarks] frame尺寸: {width}x{height}, crop_info: {crop_info}")
        print(f"[draw_landmarks] pose_result.landmarks数量: {len(pose_result.landmarks) if pose_result.landmarks else 0}")

        drawn_count = 0
        for idx in body_landmarks:
            landmark = pose_result.landmarks.get(idx)
            if landmark:
                coords = get_pixel_coords(landmark)
                # 检查坐标是否在当前图像范围内
                if 0 <= coords[0] < width and 0 <= coords[1] < height:
                    # 统一使用黄色小点
                    cv2.circle(annotated, coords, point_radius, (0, 255, 255), -1)
                    drawn_count += 1

        print(f"[draw_landmarks] 绘制的骨骼点数量: {drawn_count}")

        # 绘制骨骼连接（只绘制身体连接）
        if draw_connections:
            # 身体连接索引对
            body_connections = [
                (11, 12), (11, 13), (13, 15), (15, 17), (15, 19), (15, 21), (17, 19),
                (12, 14), (14, 16), (16, 18), (16, 20), (16, 22), (18, 20),
                (11, 23), (12, 24), (23, 24), (23, 25), (24, 26),
                (25, 27), (26, 28), (27, 29), (28, 30), (29, 31), (30, 32)
            ]

            for start_idx, end_idx in body_connections:
                start_landmark = pose_result.landmarks.get(start_idx)
                end_landmark = pose_result.landmarks.get(end_idx)
                if start_landmark and end_landmark:
                    start_coords = get_pixel_coords(start_landmark)
                    end_coords = get_pixel_coords(end_landmark)
                    # 检查坐标是否在范围内
                    if (0 <= start_coords[0] < width and 0 <= start_coords[1] < height and
                        0 <= end_coords[0] < width and 0 <= end_coords[1] < height):
                        cv2.line(annotated, start_coords, end_coords, (128, 128, 128), 3)  # 线宽3像素

        return annotated

    def draw_angles(
        self,
        frame: np.ndarray,
        pose_result: PoseResult,
        angles: dict,
        shooting_hand: str = "right",
        visibility_threshold: float = 0.5,
        crop_info: Optional[dict] = None
    ) -> np.ndarray:
        """
        在图像上绘制角度信息（仅标注可见的关键点）

        Args:
            frame: BGR 格式的图像
            pose_result: 姿态检测结果
            angles: 角度字典
            shooting_hand: 投篮手
            visibility_threshold: 可见性阈值（0-1），低于此值不标注
            crop_info: 裁剪信息字典，包含 crop_x1, crop_y1, orig_width, orig_height

        Returns:
            绘制后的图像
        """
        annotated = frame.copy()

        # 使用当前帧的实际尺寸（裁剪后的尺寸）
        height, width = frame.shape[:2]

        # 如果有裁剪信息，需要调整坐标计算方式
        if crop_info:
            orig_width = crop_info['orig_width']
            orig_height = crop_info['orig_height']
            crop_x1 = crop_info['crop_x1']
            crop_y1 = crop_info['crop_y1']

            def get_pixel_coords(landmark):
                """将归一化坐标转换为裁剪后图像的像素坐标"""
                if landmark:
                    orig_x = landmark.x * orig_width
                    orig_y = landmark.y * orig_height
                    cropped_x = orig_x - crop_x1
                    cropped_y = orig_y - crop_y1
                    return (int(cropped_x), int(cropped_y))
                return None
        else:
            def get_pixel_coords(landmark):
                """将归一化坐标转换为像素坐标"""
                if landmark:
                    return (int(landmark.x * width), int(landmark.y * height))
                return None

        # 获取关键点位置
        if shooting_hand == "right":
            elbow_idx = PoseLandmark.RIGHT_ELBOW
            knee_idx = PoseLandmark.RIGHT_KNEE
            hip_idx = PoseLandmark.RIGHT_HIP
            ankle_idx = PoseLandmark.RIGHT_ANKLE
        else:
            elbow_idx = PoseLandmark.LEFT_ELBOW
            knee_idx = PoseLandmark.LEFT_KNEE
            hip_idx = PoseLandmark.LEFT_HIP
            ankle_idx = PoseLandmark.LEFT_ANKLE

        # 验证膝盖位置是否正确（膝盖应该在髋部和脚踝之间）
        def is_knee_position_valid(knee_coords, hip_coords, ankle_coords):
            """验证膝盖位置是否在髋部和脚踝之间"""
            if not knee_coords or not hip_coords or not ankle_coords:
                return False
            # 膝盖的Y坐标应该在髋部和脚踝之间（屏幕坐标系Y轴向下）
            return hip_coords[1] < knee_coords[1] < ankle_coords[1]

        # 在肘部位置显示肘部角度（检查可见性）
        elbow_landmark = pose_result.landmarks.get(elbow_idx)
        elbow_coords = get_pixel_coords(elbow_landmark)
        if elbow_coords and "elbow_angle" in angles and angles["elbow_angle"] is not None:
            # 检查坐标是否在范围内
            if 0 <= elbow_coords[0] < width and 0 <= elbow_coords[1] < height:
                # 检查可见性
                if elbow_landmark and elbow_landmark.visibility >= visibility_threshold:
                    text = f"Elbow: {angles['elbow_angle']:.1f}deg"
                    cv2.putText(
                        annotated, text,
                        (elbow_coords[0] + 10, elbow_coords[1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2
                    )

        # 在膝盖位置显示膝盖角度（检查可见性和位置正确性）
        knee_landmark = pose_result.landmarks.get(knee_idx)
        hip_landmark = pose_result.landmarks.get(hip_idx)
        ankle_landmark = pose_result.landmarks.get(ankle_idx)
        knee_coords = get_pixel_coords(knee_landmark)
        hip_coords = get_pixel_coords(hip_landmark)
        ankle_coords = get_pixel_coords(ankle_landmark)

        if knee_coords and "knee_angle" in angles and angles["knee_angle"] is not None:
            # 检查坐标是否在范围内
            if 0 <= knee_coords[0] < width and 0 <= knee_coords[1] < height:
                # 检查可见性和位置正确性
                is_valid = False
                if knee_landmark and knee_landmark.visibility >= visibility_threshold:
                    # 验证膝盖位置是否在髋部和脚踝之间
                    if is_knee_position_valid(knee_coords, hip_coords, ankle_coords):
                        is_valid = True

                if is_valid:
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
        self.landmarker.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()