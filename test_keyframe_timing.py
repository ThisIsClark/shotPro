"""Deterministic event-localization regressions; no model download required."""
import unittest
import json
from pathlib import Path
from app.core.pose_detector import Landmark

from app.core.angle_calculator import ShootingAngles
from app.core.phase_detector import FrameData, PhaseDetector, ShootingPhase as P
from app.core.rules_engine import RulesEngine


def interpolate(t, points):
    for (a, x), (b, y) in zip(points, points[1:]):
        if a <= t <= b:
            return x + (y - x) * (t - a) / (b - a)
    return points[-1][1]


def shot(fps=30, source_fps=None, offset=0.0):
    frames = []
    for i in range(round(2.4 * fps) + 1):
        t = i / fps
        y = interpolate(t, [(0,.65),(.3,.65),(.5,.75),(.65,.75),
                            (1.25,.2),(1.6,.2),(2,.6),(2.4,.6)])
        elbow = interpolate(t, [(0,95),(.65,95),(.85,65),(1.22,170),(2.4,170)])
        knee = interpolate(t, [(0,150),(.65,100),(1.2,175),(2.4,175)])
        shoulder = interpolate(t, [(0,30),(.65,30),(1.1,100),(2.4,100)])
        angles = ShootingAngles(elbow_angle=elbow, knee_angle=knee,
                                shoulder_angle=shoulder, trunk_angle=5)
        frames.append(FrameData(frame_number=round((t + offset) * (source_fps or fps)),
                                timestamp=t + offset, angles=angles, raw_angles=angles,
                                wrist_y=y, raw_wrist_y=y))
    return frames


def detect(frames):
    detector = PhaseDetector()
    detector.frame_history = frames
    return detector.get_key_frames()


class KeyframeTimingTests(unittest.TestCase):
    def test_known_events_and_temporal_order(self):
        keys = detect(shot())
        self.assertAlmostEqual(keys[P.SYNC_FRAME_1].timestamp, .65, delta=.06)
        self.assertAlmostEqual(keys[P.RELEASE_FRAME].timestamp, 1.185, delta=.06)
        self.assertAlmostEqual(keys[P.WRIST_PEAK_FRAME].timestamp, 1.25, delta=.06)
        self.assertLess(keys[P.MAX_HOLD_FRAME].timestamp, keys[P.RELEASE_FRAME].timestamp)
        self.assertGreater(keys[P.FOLLOW_THROUGH_FRAME].timestamp, keys[P.WRIST_PEAK_FRAME].timestamp)
        self.assertAlmostEqual(keys[P.KNEE_MIN_FRAME].timestamp, .65, delta=.06)

    def test_source_frame_numbers_do_not_change_events(self):
        baseline = detect(shot(30, 30))
        for fps, source in [(30,120), (60,60), (24,24)]:
            keys = detect(shot(fps,source))
            for phase in baseline:
                self.assertIsNotNone(keys[phase], phase)
                self.assertAlmostEqual(keys[phase].timestamp, baseline[phase].timestamp, delta=.09)

    def test_single_tracking_spike_does_not_move_peak(self):
        frames = shot()
        frames[7].raw_wrist_y = .01
        keys = detect(frames)
        self.assertAlmostEqual(keys[P.WRIST_PEAK_FRAME].timestamp, 1.25, delta=.06)

    def test_two_shots_do_not_mix_events(self):
        frames = shot() + shot(offset=3)
        for key in detect(frames).values():
            if key:
                self.assertLess(key.timestamp, 2.4)

    def test_missing_elbow_does_not_invent_release(self):
        frames = shot()
        for frame in frames:
            frame.angles.elbow_angle = None
        keys = detect(frames)
        self.assertIsNone(keys[P.RELEASE_FRAME])
        issues = RulesEngine().evaluate_coordination(keys,frames)
        self.assertTrue(all(issue.skipped for issue in issues))

    def test_static_video_and_short_input(self):
        self.assertTrue(all(f is None for f in detect(shot()[:2]).values()))
        frames = shot()
        for frame in frames:
            frame.raw_wrist_y = .6
        self.assertTrue(all(f is None for f in detect(frames).values()))

    def test_slow_motion_keeps_original_dip(self):
        frames = shot(fps=150)
        for frame in frames:
            frame.timestamp *= 5
        # 5 倍慢动作中，举球超过 2 秒，起点仍应在原来的低位平台。
        keys = detect(frames)
        self.assertAlmostEqual(keys[P.SYNC_FRAME_1].timestamp, .65 * 5, delta=.18)

    def test_clip_starts_at_dip(self):
        frames = shot()[20:]  # 截掉下沉过程，从最低处刚开始举球时起拍。
        start = frames[0].timestamp
        for i, frame in enumerate(frames):
            frame.timestamp -= start
            frame.frame_number = i
        self.assertEqual(detect(frames)[P.SYNC_FRAME_1].frame_number, 0)

    def test_clip_starts_on_low_platform(self):
        frames = shot()[15:]
        start = frames[0].timestamp
        for i, frame in enumerate(frames):
            frame.timestamp -= start
            frame.frame_number = i
        # 平台从首帧延续到约 .15s，应取末端而不是机械选择首帧。
        self.assertAlmostEqual(detect(frames)[P.SYNC_FRAME_1].timestamp, .15, delta=.04)

    def test_later_shot_uses_its_own_dip(self):
        first = shot()
        for frame in first:
            frame.angles.elbow_angle = 95  # 第一次抬手未伸臂，不构成完整投篮。
        second = shot(offset=2.4)[1:]
        for frame in second:
            frame.raw_wrist_y -= .10  # 第二次的低点比第一次高，不能取全局最低点。
        key = detect(first + second)[P.SYNC_FRAME_1]
        self.assertAlmostEqual(key.timestamp, 3.05, delta=.06)

    def test_tracking_gap_is_not_bridged(self):
        frames = [f for f in shot() if not .75 < f.timestamp < 1.1]
        keys = detect(frames)
        self.assertIsNone(keys[P.SYNC_FRAME_1])
        self.assertIsNone(keys[P.SYNC_FRAME_2])
        self.assertIsNone(keys[P.KNEE_MIN_FRAME])
        self.assertIsNotNone(keys[P.RELEASE_FRAME])
        self.assertIsNotNone(keys[P.WRIST_PEAK_FRAME])
        self.assertGreater(keys[P.RELEASE_FRAME].timestamp, 1.1)
        self.assertTrue(all(i.skipped for i in RulesEngine().evaluate_coordination(keys, frames)))

    def test_reddit1009_recorded_pose_regression(self):
        detector = PhaseDetector()
        rows = json.loads((Path(__file__).parent / 'tests/fixtures/reddit1009_pose.json').read_text())
        for row in rows:
            detector.detect_phase(row['frame'], row['time'],
                                  ShootingAngles(**row['angles']) if row['angles'] else None,
                                  Landmark(x=0, y=row['wrist_y'], z=0, visibility=1),
                                  row['confidence'])
        keys = detector.get_key_frames()
        self.assertIsNone(keys[P.SYNC_FRAME_1])
        self.assertIsNone(keys[P.KNEE_MIN_FRAME])
        self.assertEqual(keys[P.RELEASE_FRAME].frame_number, 37)
        self.assertIn(keys[P.WRIST_PEAK_FRAME].frame_number, (41, 42))
        self.assertIn(keys[P.ELBOW_MIN_FRAME].frame_number, (31, 32))
        issues = RulesEngine().evaluate_coordination(keys, detector.frame_history)
        self.assertTrue(all(i.skipped and not i.detected for i in issues))

    def test_partial_static_extended_arm_is_not_a_shot(self):
        frames = shot()[33:]
        for frame in frames:
            frame.angles.elbow_angle = 175
        self.assertTrue(all(v is None for v in detect(frames).values()))

    def test_partial_extremum_at_boundary_is_not_reported(self):
        keys = detect(shot()[33:])
        self.assertIsNotNone(keys[P.RELEASE_FRAME])
        self.assertIsNone(keys[P.SYNC_FRAME_1])
        self.assertIsNone(keys[P.ELBOW_MIN_FRAME])


if __name__ == '__main__':
    unittest.main()
