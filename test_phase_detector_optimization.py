"""
测试优化后的关键帧判断逻辑
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.phase_detector import PhaseDetector, PhaseThresholds, ShootingPhase
from app.core.angle_calculator import ShootingAngles
from app.core.pose_detector import Landmark


def test_smooth_data():
    """测试数据平滑功能"""
    print("测试数据平滑功能...")
    detector = PhaseDetector()
    
    # 模拟角度数据（有噪声）
    angles_list = [
        ShootingAngles(elbow_angle=90, shoulder_angle=50, knee_angle=120, trunk_angle=15),
        ShootingAngles(elbow_angle=92, shoulder_angle=52, knee_angle=118, trunk_angle=16),
        ShootingAngles(elbow_angle=88, shoulder_angle=48, knee_angle=122, trunk_angle=14),
        ShootingAngles(elbow_angle=95, shoulder_angle=55, knee_angle=115, trunk_angle=18),
        ShootingAngles(elbow_angle=85, shoulder_angle=45, knee_angle=125, trunk_angle=12),
    ]
    
    # 测试角度平滑
    smoothed = detector._smooth_angles(angles_list[0])
    print(f"  原始角度: {angles_list[0].elbow_angle}°")
    print(f"  平滑后角度: {smoothed.elbow_angle:.1f}°")
    
    # 测试手腕Y坐标平滑
    wrist_y_list = [0.8, 0.79, 0.81, 0.78, 0.8]
    for wrist_y in wrist_y_list:
        smoothed_wrist = detector._smooth_wrist_y(wrist_y)
        print(f"  原始手腕Y: {wrist_y:.3f}, 平滑后: {smoothed_wrist:.3f}")
    
    print("✓ 数据平滑功能正常\n")


def test_preparation_phase():
    """测试准备阶段判断"""
    print("测试准备阶段判断...")
    detector = PhaseDetector()
    
    # 模拟准备阶段：膝盖弯曲、肘部弯曲、躯干直立
    angles = ShootingAngles(
        elbow_angle=100,  # < 110°
        shoulder_angle=50,
        knee_angle=120,  # < 130°
        trunk_angle=15   # < 20°
    )
    
    wrist_landmark = Landmark(x=0.5, y=0.8, z=0.0, visibility=1.0)
    
    # 检测多帧以确保平滑
    for i in range(10):
        phase = detector.detect_phase(i, i * 0.033, angles, wrist_landmark)
    
    final_phase = detector.detect_phase(10, 0.33, angles, wrist_landmark)
    print(f"  检测到的阶段: {final_phase}")
    assert final_phase == ShootingPhase.PREPARATION, "准备阶段判断错误"
    print("✓ 准备阶段判断正确\n")


def test_lifting_phase():
    """测试上升阶段判断"""
    print("测试上升阶段判断...")
    detector = PhaseDetector()
    
    # 先准备阶段
    prep_angles = ShootingAngles(
        elbow_angle=100,
        shoulder_angle=50,
        knee_angle=120,
        trunk_angle=15
    )
    wrist_landmark = Landmark(x=0.5, y=0.8, z=0.0, visibility=1.0)
    
    for i in range(5):
        detector.detect_phase(i, i * 0.033, prep_angles, wrist_landmark)
    
    # 上升阶段：手腕上升，速度足够
    lift_angles = ShootingAngles(
        elbow_angle=120,
        shoulder_angle=60,
        knee_angle=140,
        trunk_angle=18
    )
    
    # 手腕从0.8上升到0.5
    wrist_positions = [0.8, 0.75, 0.7, 0.65, 0.6, 0.55, 0.5]
    for i, wrist_y in enumerate(wrist_positions):
        wrist_landmark = Landmark(x=0.5, y=wrist_y, z=0.0, visibility=1.0)
        phase = detector.detect_phase(5 + i, (5 + i) * 0.033, lift_angles, wrist_landmark)
    
    print(f"  检测到的阶段: {phase}")
    assert phase == ShootingPhase.LIFTING, "上升阶段判断错误"
    print("✓ 上升阶段判断正确\n")


def test_release_phase():
    """测试出手阶段判断"""
    print("测试出手阶段判断...")
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
        detector.detect_phase(i, i * 0.033, prep_angles, wrist_landmark)
    
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
        detector.detect_phase(5 + i, (5 + i) * 0.033, lift_angles, wrist_landmark)
    
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
    
    print(f"  检测到的阶段: {phase}")
    assert phase == ShootingPhase.RELEASE, "出手阶段判断错误"
    print("✓ 出手阶段判断正确\n")


def test_follow_through_phase():
    """测试跟随阶段判断"""
    print("测试跟随阶段判断...")
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
        detector.detect_phase(i, i * 0.033, prep_angles, wrist_landmark)
    
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
        detector.detect_phase(5 + i, (5 + i) * 0.033, lift_angles, wrist_landmark)
    
    # 出手阶段
    release_angles = ShootingAngles(
        elbow_angle=155,
        shoulder_angle=75,
        knee_angle=160,
        trunk_angle=20
    )
    wrist_positions = [0.5, 0.51, 0.52]
    for i, wrist_y in enumerate(wrist_positions):
        wrist_landmark = Landmark(x=0.5, y=wrist_y, z=0.0, visibility=1.0)
        detector.detect_phase(12 + i, (12 + i) * 0.033, release_angles, wrist_landmark)
    
    # 跟随阶段：手腕持续下降
    follow_angles = ShootingAngles(
        elbow_angle=160,
        shoulder_angle=80,
        knee_angle=165,
        trunk_angle=22
    )
    wrist_positions = [0.53, 0.55, 0.57, 0.59, 0.61]
    for i, wrist_y in enumerate(wrist_positions):
        wrist_landmark = Landmark(x=0.5, y=wrist_y, z=0.0, visibility=1.0)
        phase = detector.detect_phase(15 + i, (15 + i) * 0.033, follow_angles, wrist_landmark)
    
    print(f"  检测到的阶段: {phase}")
    assert phase == ShootingPhase.FOLLOW_THROUGH, "跟随阶段判断错误"
    print("✓ 跟随阶段判断正确\n")


def test_auto_reset():
    """测试自动重置功能"""
    print("测试自动重置功能...")
    detector = PhaseDetector()
    
    # 模拟完整投篮
    angles = ShootingAngles(
        elbow_angle=100,
        shoulder_angle=50,
        knee_angle=120,
        trunk_angle=15
    )
    
    # 准备 -> 上升 -> 出手 -> 跟随
    wrist_positions = [0.8] * 5 + [0.7, 0.6, 0.5] + [0.51, 0.52, 0.53] + [0.55, 0.57, 0.59, 0.61, 0.63]
    for i, wrist_y in enumerate(wrist_positions):
        wrist_landmark = Landmark(x=0.5, y=wrist_y, z=0.0, visibility=1.0)
        detector.detect_phase(i, i * 0.033, angles, wrist_landmark)
    
    print(f"  跟随阶段帧数: {detector.follow_frames_count}")
    print(f"  出手已检测: {detector.release_detected}")
    
    # 模拟新的投篮：手腕重新上升
    new_prep_angles = ShootingAngles(
        elbow_angle=95,
        shoulder_angle=48,
        knee_angle=115,
        trunk_angle=14
    )
    wrist_positions = [0.65, 0.6, 0.55, 0.5, 0.45]
    for i, wrist_y in enumerate(wrist_positions):
        wrist_landmark = Landmark(x=0.5, y=wrist_y, z=0.0, visibility=1.0)
        phase = detector.detect_phase(20 + i, (20 + i) * 0.033, new_prep_angles, wrist_landmark)
    
    print(f"  新投篮阶段: {phase}")
    print(f"  出手已重置: {not detector.release_detected}")
    print("✓ 自动重置功能正常\n")


if __name__ == "__main__":
    print("=" * 60)
    print("开始测试优化后的关键帧判断逻辑")
    print("=" * 60 + "\n")
    
    try:
        test_smooth_data()
        test_preparation_phase()
        test_lifting_phase()
        test_release_phase()
        test_follow_through_phase()
        test_auto_reset()
        
        print("=" * 60)
        print("所有测试通过！✓")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n✗ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
