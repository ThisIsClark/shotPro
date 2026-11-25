import unittest
from types import SimpleNamespace

from app.core.shot_rhythm import classify_motion, detect_shot_rhythm
from app.core.phase_detector import ShootingPhase


class MotionCases(unittest.TestCase):
    def test_overlapping_lift_at_two_playback_speeds(self):
        for fps in (24, 48):
            rows = [(i/fps, 20+5*i, 75+4*i, i/18) for i in range(22)]
            result = classify_motion(rows)
            self.assertEqual(result['style'], 'one_motion')
            self.assertLess(result['evidence_start'], result['evidence_end'])

    def test_measurable_set_then_extension(self):
        arms = [10, 30, 55, 80, 96, 98, 98, 97, 99, 100, 111, 125, 142]
        elbows = [100, 98, 87, 79, 74, 75, 75, 76, 85, 98, 120, 145, 164]
        rows = [(i/30, a, e, a/115) for i, (a, e) in enumerate(zip(arms, elbows))]
        self.assertEqual(classify_motion(rows)['style'], 'two_motion')

    def test_gap_or_few_observations_do_not_imply_a_hold(self):
        rows = [(i/30, 15+5*i, 75+4*i, i/18) for i in range(22)]
        for incomplete in (rows[:4], rows[:8]+rows[16:], [(i/8,a,e,w) for i,(_,a,e,w) in enumerate(rows)]):
            self.assertEqual(classify_motion(incomplete)['reason'], 'insufficient_tracking')

    def test_hidden_shooting_elbow_makes_style_unclear(self):
        keys = {ShootingPhase.SYNC_FRAME_1: SimpleNamespace(frame_number=1,timestamp=1/30),
                ShootingPhase.RELEASE_FRAME: SimpleNamespace(frame_number=15,timestamp=15/30)}
        visible = SimpleNamespace(x=.3, y=.7, visibility=.95)
        hidden = SimpleNamespace(x=.35, y=.5, visibility=.1)
        for hand, side in [('left', 0), ('right', 1)]:
            landmarks = {j+side:visible for j in (23,11,13,15)}
            landmarks[13+side] = hidden
            poses = {i:SimpleNamespace(landmarks=landmarks) for i in range(1,16)}
            self.assertEqual(detect_shot_rhythm(keys, poses, hand, 30)['reason'], 'insufficient_tracking')
