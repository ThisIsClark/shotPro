"""
调试出手阶段判断
"""

import sys
sys.path.append('/Users/liuyu/Code/shotImprovement')

from app.core.phase_detector import PhaseDetector, PhaseThresholds, ShootingPhase
from app.core.angle_calculator import ShootingAngles
from app.core.pose_detector import Landmark


def debug_release_phase():
    """调试出手阶段判断"""
    print("调试出手阶段判断...")
    detector = PhaseDetector()
    
    # 模拟完整投篮过程
    # 准备阶段
    prep_angles = ShootingAngles(
        elbow_angle=100,
        shoulder_angle=50,
        knee_angle=120,
        trunk_angle=15
    )
    wrist_landmark = Landmark(x=0.5, y=0.8, z=0.0, visibility=1.0)
    for i in range(5):
        phase = detector.detect_phase(i, i * 0.033, prep_angles, wrist_landmark)
        print(f"帧 {i}: {phase}, wrist_y={wrist_landmark.y:.3f}, wrist_rising={detector.wrist_rising}, release_detected={detector.release_detected}")
    
    # 上升阶段
    lift_angles = ShootingAngles(
        elbow_angle=120,
        shoulder_angle=60,
        knee_angle=140,
        trunk_angle=18
    )
    wrist_positions = [0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.5]
    for i, wrist_y in enumerate(wrist_positions):
        wrist_landmark = Landmark(x=0.5, y=wrist_y, z=0.0, visibility=1.0)
        phase = detector.detect_phase(5 + i, (5 + i) * 0.033, lift_angles, wrist_landmark)
        print(f"帧 {5+i}: {phase}, wrist_y={wrist_y:.3f}, wrist_rising={detector.wrist_rising}, release_detected={detector.release_detected}")
    
    # 出手阶段：肘部伸展，手腕达到最高点
    release_angles = ShootingAngles(
        elbow_angle=155,  # >= 150°
        shoulder_angle=75,  # >= 70°
        knee_angle=160,
        trunk_angle=20
    )
    
    # 手腕开始下降（需要足够的变化）
    wrist_positions = [0.5, 0.52, 0.54, 0.56, 0.58]
    for i, wrist_y in enumerate(wrist_positions):
        wrist_landmark = Landmark(x=0.5, y=wrist_y, z=0.0, visibility=1.0)
        phase = detector.detect_phase(12 + i, (12 + i) * 0.033, release_angles, wrist_landmark)
        print(f"帧 {12+i}: {phase}, wrist_y={wrist_y:.3f}, wrist_rising={detector.wrist_rising}, release_detected={detector.release_detected}")
    
    print(f"\n最终阶段: {phase}")


if __name__ == "__main__":
    debug_release_phase()
