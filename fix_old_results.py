"""
检查和修复旧的分析结果，添加template_comparison数据
"""

import sys
sys.path.append('/Users/liuyu/Code/shotImprovement')

from pathlib import Path
import json
import shutil
from datetime import datetime

results_dir = Path('/Users/liuyu/Code/shotImprovement/results')

if results_dir.exists():
    # 找到所有任务目录
    task_dirs = [d for d in results_dir.iterdir() if d.is_dir()]
    
    print(f"找到 {len(task_dirs)} 个任务目录")
    
    for task_dir in sorted(task_dirs, key=lambda p: p.stat().st_mtime, reverse=True)[:5]:  # 只检查最新的5个
        result_file = task_dir / "result.json"
        
        if not result_file.exists():
            print(f"\n任务 {task_dir.name}: 没有result.json")
            continue
        
        # 读取结果
        with open(result_file, 'r', encoding='utf-8') as f:
            result = json.load(f)
        
        print(f"\n任务 {task_dir.name}:")
        print(f"  - 有template_comparison: {'template_comparison' in result}")
        
        # 检查是否有key_frames但没有template_comparison
        has_key_frames = 'key_frames' in result
        has_template_comparison = 'template_comparison' in result
        
        if has_key_frames and not has_template_comparison:
            print(f"  - 有key_frames但缺少template_comparison")
            
            # 检查是否有template_id
            if 'template_id' in result:
                print(f"  - 有template_id: {result['template_id']}")
                
                # 尝试加载模板
                template_dir = Path('/Users/liuyu/Code/shotImprovement/templates') / result['template_id']
                metadata_file = template_dir / "metadata.json"
                
                if metadata_file.exists():
                    print(f"  - 模板文件存在: {metadata_file}")
                    
                    # 读取模板数据
                    with open(metadata_file, 'r', encoding='utf-8') as f:
                        template_data = json.load(f)
                    
                    # 生成对比数据
                    template_key_frames = template_data.get('key_frames', [])
                    user_key_frames = result.get('key_frames', [])
                    
                    # 创建阶段映射
                    template_dict = {tkf['phase']: tkf for tkf in template_key_frames}
                    
                    comparisons = []
                    for user_kf in user_key_frames:
                        phase = user_kf.get('phase', '')
                        template_kf = template_dict.get(phase)
                        
                        comp = {
                            "phase": phase,
                            "user_frame": user_kf
                        }
                        
                        if template_kf:
                            comp["template_frame"] = {
                                "image_url": template_kf.get('image_path', ''),
                                "angles": template_kf.get('angles')
                            }
                            
                            # 计算角度差异
                            user_angles = user_kf.get('angles', {})
                            template_angles = template_kf.get('angles', {})
                            if user_angles and template_angles:
                                angle_diffs = {}
                                for key in user_angles:
                                    if key in template_angles:
                                        user_angle = user_angles[key]
                                        template_angle = template_angles[key]
                                        if user_angle is not None and template_angle is not None:
                                            angle_diffs[key] = abs(user_angle - template_angle)
                                comp["angle_differences"] = angle_diffs
                        
                        comparisons.append(comp)
                    
                    # 添加template_comparison到result
                    result['template_comparison'] = {
                        "template_id": result['template_id'],
                        "template_name": template_data.get('name', ''),
                        "comparisons": comparisons
                    }
                    
                    # 备份原文件
                    backup_file = result_file.with_suffix('.json.bak')
                    shutil.copy(result_file, backup_file)
                    
                    # 保存修复后的结果
                    with open(result_file, 'w', encoding='utf-8') as f:
                        json.dump(result, f, ensure_ascii=False, indent=2)
                    
                    print(f"  ✓ 已修复并保存")
                    print(f"  - 添加了 {len(comparisons)} 个对比")
                else:
                    print(f"  - 模板文件不存在: {metadata_file}")
            else:
                print(f"  - 没有template_id")
        elif has_template_comparison:
            print(f"  - 已有template_comparison数据")
    
    print("\n检查完成！")
