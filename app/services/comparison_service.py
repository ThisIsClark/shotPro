"""
Comparison Service Module (M3)
曲线对比服务：用户投篮曲线 vs 模板曲线，按阶段对齐 + 重采样 + 差值计算。

不依赖 DTW，用 phase_detector 已切好的 4 阶段做对齐：
对每个阶段独立处理 -> 各自重采样到统一长度（如 50 点）-> 计算角度差曲线。
"""

from __future__ import annotations

import numpy as np
from typing import Optional

from ..core.angle_calculator import ShootingAngles


# 每个阶段重采样到的点数。拼接后一条曲线 = 4 阶段 × POINTS_PER_PHASE = 200 点
POINTS_PER_PHASE = 50

# 对比输出的关节列表（与前端 ANGLE_JOINTS 对齐）
COMPARISON_JOINTS = [
    "elbow_angle",
    "shoulder_angle",
    "knee_angle",
    "hip_angle",
    "trunk_angle",
    "wrist_angle",
]

# 阶段顺序（拼接曲线时按此顺序，与 phase_detector 流程一致）
PHASE_ORDER = ["preparation", "lifting", "release", "follow_through"]


def _resample(values: list[float], n: int) -> list[float]:
    """
    将一组角度值重采样到固定长度 n（线性插值）。

    用于把用户/模板某阶段的不同帧数拉到统一长度，便于逐点比较。
    输入可能含 None（关节未检测到），先转成 np.nan，重采样后再转回 None。
    """
    if not values:
        return [None] * n

    arr = np.array([v if v is not None else np.nan for v in values], dtype=float)

    if len(arr) == 1:
        return [float(arr[0]) if not np.isnan(arr[0]) else None] * n

    # 用 nan-aware 线性插值补齐中间的 None
    valid_idx = np.where(~np.isnan(arr))[0]
    if len(valid_idx) == 0:
        return [None] * n
    if len(valid_idx) < len(arr):
        arr = np.interp(
            np.arange(len(arr)),
            valid_idx,
            arr[valid_idx],
        )

    # 重采样到 n 点：原索引空间 -> 新索引空间
    old_idx = np.linspace(0, len(arr) - 1, len(arr))
    new_idx = np.linspace(0, len(arr) - 1, n)
    resampled = np.interp(new_idx, old_idx, arr)
    return [float(v) if not np.isnan(v) else None for v in resampled]


def _extract_phase_series(
    frame_data: list[dict], phase: str, joint_key: str
) -> list[Optional[float]]:
    """从 frame_data 中抽出某阶段某关节的角度序列（按时间顺序）。"""
    series = []
    for fd in frame_data:
        if fd.get("phase") != phase:
            continue
        angles = fd.get("angles") or {}
        series.append(angles.get(joint_key))
    return series


def _phase_boundaries(frame_data: list[dict]) -> dict[str, dict]:
    """从 frame_data 推各阶段首尾 timestamp（用于前端叠加时的阶段标注）。"""
    boundaries: dict[str, dict] = {}
    for fd in frame_data:
        phase = fd.get("phase")
        if not phase or phase == "unknown":
            continue
        if phase not in boundaries:
            boundaries[phase] = {
                "start_time": fd["timestamp"],
                "end_time": fd["timestamp"],
            }
        else:
            boundaries[phase]["end_time"] = fd["timestamp"]
    return boundaries


def compare_curves(
    user_frame_data: list[dict],
    template_curves: dict,
) -> Optional[dict]:
    """
    用户曲线 vs 模板曲线，按阶段对齐后逐点比较。

    Args:
        user_frame_data: 用户的 per-frame 时序数据（M1 持久化的 frame_data.json 格式），
            每帧含 phase + angles[frame_number, timestamp, ...]
        template_curves: 模板的曲线数据，形如
            {"angles": [...], "phases": {...}}（来自 TemplateManager.get_template_curves）

    Returns:
        {
            "joints": [
                {
                    "name": "elbow_angle",
                    "user_curve": [50×4=200 点],
                    "template_curve": [200 点],
                    "diff_curve": [200 点],
                    "max_diff_phase": "lifting",
                    "max_diff_value": 12.5,
                }, ...
            ],
            "phase_boundaries": {
                "preparation": {"user": [...], "template": [...]},
                ...
            }
        }
        或 None（输入数据不足，比如缺曲线数据或没有阶段）。
    """
    if not user_frame_data or not template_curves:
        return None

    template_frame_data = template_curves.get("angles")
    if not template_frame_data:
        return None

    # 拼接后的统一时间轴点数（4 阶段 × POINTS_PER_PHASE）
    n_total = POINTS_PER_PHASE * len(PHASE_ORDER)

    joints_out = []
    for joint_key in COMPARISON_JOINTS:
        user_resampled: list = []
        template_resampled: list = []
        phase_marks: list[dict] = []  # 每个阶段的 [start, end] 在拼接曲线里的索引

        for phase in PHASE_ORDER:
            user_series = _extract_phase_series(user_frame_data, phase, joint_key)
            template_series = _extract_phase_series(template_frame_data, phase, joint_key)

            # 阶段缺失：用全 None 占位，保持索引对齐
            if not user_series:
                user_resampled.extend([None] * POINTS_PER_PHASE)
            else:
                user_resampled.extend(_resample(user_series, POINTS_PER_PHASE))

            if not template_series:
                template_resampled.extend([None] * POINTS_PER_PHASE)
            else:
                template_resampled.extend(_resample(template_series, POINTS_PER_PHASE))

            start_idx = (PHASE_ORDER.index(phase)) * POINTS_PER_PHASE
            phase_marks.append({"phase": phase, "start": start_idx, "end": start_idx + POINTS_PER_PHASE - 1})

        # 差值曲线（逐点，None 当作不可比跳过）
        diff_curve = []
        for u, t in zip(user_resampled, template_resampled):
            if u is None or t is None:
                diff_curve.append(None)
            else:
                diff_curve.append(abs(u - t))

        # 找差异最大的阶段
        max_diff_phase = None
        max_diff_value = 0.0
        for mark in phase_marks:
            segment = [d for d in diff_curve[mark["start"]:mark["end"] + 1] if d is not None]
            if not segment:
                continue
            phase_avg = sum(segment) / len(segment)
            if phase_avg > max_diff_value:
                max_diff_value = phase_avg
                max_diff_phase = mark["phase"]

        joints_out.append({
            "name": joint_key,
            "user_curve": user_resampled,
            "template_curve": template_resampled,
            "diff_curve": diff_curve,
            "max_diff_phase": max_diff_phase,
            "max_diff_value": round(max_diff_value, 2) if max_diff_phase else 0.0,
        })

    # 阶段边界（时间，供前端标注）
    user_phases = _phase_boundaries(user_frame_data)
    template_phases = template_curves.get("phases") or _phase_boundaries(template_frame_data)

    return {
        "joints": joints_out,
        "phase_marks": phase_marks,
        "phase_boundaries": {
            "user": user_phases,
            "template": template_phases,
        },
        "points_per_phase": POINTS_PER_PHASE,
    }
