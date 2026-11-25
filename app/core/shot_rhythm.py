"""Estimate lift/extension timing in the selected shot, in the camera plane."""
from statistics import median
import numpy as np

from .phase_detector import ShootingPhase


def _angle(a, b):
    length = np.linalg.norm(a) * np.linalg.norm(b)
    if length < 1:
        return np.nan
    return np.degrees(np.arccos(np.clip(np.dot(a, b) / length, -1, 1)))


def classify_motion(samples):
    """Rows contain time, upper-arm elevation, elbow opening and relative wrist height."""
    unclear = {"style": "unclear", "reason": "insufficient_tracking"}
    if len(samples) < 7:
        return unclear
    t, arm, elbow, wrist = np.asarray(samples).T
    dt = np.diff(t)
    if (not np.isfinite(samples).all() or min(dt) <= 0 or median(dt) > 0.075
            or max(dt) > min(0.13, median(dt) * 2.5)):
        return unclear

    # A centered median removes isolated pose spikes without shifting onset in time.
    arm, elbow, wrist = [np.array([np.median(v[max(0, i-1):i+2]) for i in range(len(v))])
                         for v in (arm, elbow, wrist)]
    duration = t[-1] - t[0]
    lift = arm[-1] - arm[0]
    tuck = int(np.argmin(elbow))
    opening = elbow[-1] - elbow[tuck]
    if lift < 40 or opening < 35 or wrist[-1] - wrist[0] < 0.4 or tuck >= len(t)-3:
        return {"style": "unclear", "reason": "partial_motion"}

    # Look for a raised, still-flexed arm that settles for multiple observations
    # before the main extension. Height and elevation must agree on that interval.
    for i in range(len(t)-3):
        if arm[i] < arm[0] + lift * 0.55 or elbow[i] > elbow[tuck] + opening * 0.45:
            continue
        j = int(np.searchsorted(t, t[i] + max(0.06, duration * 0.14)))
        if j >= len(t)-1 or j < i+2:
            continue
        section = slice(i, j+1)
        if (np.ptp(arm[section]) <= lift * 0.075 and np.ptp(wrist[section]) <= 0.18
                and max(elbow[section]) < elbow[tuck] + opening * 0.5):
            return {"style": "two_motion", "reason": "set_then_extend",
                    "evidence_start": round(float(t[i]), 3), "evidence_end": round(float(t[j]), 3)}

    # Require positive evidence of simultaneous lift and extension over the
    # central portion of elbow opening. No detected hold alone proves nothing.
    low = tuck + np.flatnonzero(elbow[tuck:] >= elbow[tuck] + opening * 0.2)[0]
    high = low + np.flatnonzero(elbow[low:] >= elbow[tuck] + opening * 0.8)[0]
    if (high - low >= 2 and arm[high] - arm[low] >= lift * 0.15
            and wrist[high] - wrist[low] >= 0.10):
        return {"style": "one_motion", "reason": "overlapping_lift",
                "evidence_start": round(float(t[low]), 3), "evidence_end": round(float(t[high]), 3)}
    return {"style": "unclear", "reason": "mixed_timing"}


def detect_shot_rhythm(keys, poses, hand, fps):
    release = keys.get(ShootingPhase.RELEASE_FRAME)
    start = keys.get(ShootingPhase.SYNC_FRAME_1) or keys.get(ShootingPhase.ELBOW_MIN_FRAME)
    if not release or not start or fps <= 0:
        return {"style": "unclear", "reason": "partial_motion"}
    rows = []
    side = int(hand == "right")
    for frame, pose in poses.items():
        if not start.frame_number <= frame <= release.frame_number:
            continue
        joints = [pose.landmarks.get(i + side) for i in (23, 11, 13, 15)]
        if any(p is None or p.visibility < 0.5 for p in joints):
            continue
        hip, shoulder, elbow, wrist = np.array([(p.x * pose.image_width, p.y * pose.image_height)
                                                for p in joints])
        torso = hip - shoulder
        if np.linalg.norm(torso) < 1:
            continue
        rows.append((frame / fps, _angle(torso, elbow-shoulder), _angle(shoulder-elbow, wrist-elbow),
                     (shoulder[1]-wrist[1]) / np.linalg.norm(torso)))
    if not rows or rows[0][0]-start.timestamp > 0.075 or release.timestamp-rows[-1][0] > 0.075:
        return {"style": "unclear", "reason": "insufficient_tracking"}
    return classify_motion(rows)
