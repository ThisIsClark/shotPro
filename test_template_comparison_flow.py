"""
测试模板对比数据流
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path
import json

# 检查一个实际的结果文件
results_dir = Path('/Users/liuyu/Code/shotImprovement/results')

if results_dir.exists():
    # 找到最新的任务目录
    task_dirs = [d for d in results_dir.iterdir() if d.is_dir()]
    if task_dirs:
        latest_task = max(task_dirs, key=lambda p: p.stat().st_mtime)
        print(f"最新任务目录: {latest_task}")
        
        # 检查是否有结果文件
        result_file = latest_task / "result.json"
        if result_file.exists():
            print(f"\n找到结果文件: {result_file}")
            with open(result_file, 'r', encoding='utf-8') as f:
                result = json.load(f)
            
            print(f"\n结果数据键: {list(result.keys())}")
            
            # 检查是否有 template_comparison
            if 'template_comparison' in result:
                print(f"\n✓ 找到 template_comparison 数据")
                tc = result['template_comparison']
                print(f"  - template_id: {tc.get('template_id')}")
                print(f"  - template_name: {tc.get('template_name')}")
                print(f"  - comparisons 数量: {len(tc.get('comparisons', []))}")
                
                # 检查每个对比条目
                for i, comp in enumerate(tc.get('comparisons', [])):
                    print(f"\n  对比 [{i}]:")
                    print(f"    - phase: {comp.get('phase')}")
                    user_frame = comp.get('user_frame', {})
                    template_frame = comp.get('template_frame', {})
                    print(f"    - user_image_url: {user_frame.get('image_url')}")
                    print(f"    - template_image_url: {template_frame.get('image_url')}")
                    
                    # 检查图片文件是否存在
                    if user_frame.get('image_url'):
                        user_img_path = latest_task / user_frame['image_url'].lstrip('/')
                        print(f"    - user_image_exists: {user_img_path.exists()}")
                    
                    if template_frame.get('image_url'):
                        # 模板图片路径处理
                        template_img_url = template_frame['image_url']
                        if template_img_url.startswith('/template_images/'):
                            template_img_path = results_dir.parent / template_img_url.lstrip('/')
                        elif template_img_url.startswith('templates/'):
                            template_img_path = results_dir.parent / template_img_url
                        else:
                            template_img_path = None
                        
                        print(f"    - template_image_path: {template_img_path}")
                        if template_img_path:
                            print(f"    - template_image_exists: {template_img_path.exists()}")
            else:
                print(f"\n✗ 未找到 template_comparison 数据")
                print(f"  可能原因：")
                print(f"  1. 分析时没有选择模板")
                print(f"  2. 模板对比数据生成失败")
                print(f"  3. 数据保存时丢失")
        else:
            print(f"\n未找到结果文件: {result_file}")
    else:
        print("\n没有找到任务目录")
else:
    print("\nresults 目录不存在")

# 检查模板目录
templates_dir = Path('/Users/liuyu/Code/shotImprovement/templates')
if templates_dir.exists():
    print(f"\n\n检查模板目录:")
    template_dirs = [d for d in templates_dir.iterdir() if d.is_dir() and d.name.startswith('template_')]
    print(f"找到 {len(template_dirs)} 个模板")
    
    for template_dir in template_dirs:
        metadata_file = template_dir / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            print(f"\n模板: {metadata.get('name')} ({template_dir.name})")
            print(f"  关键帧数量: {len(metadata.get('key_frames', []))}")
            
            # 检查关键帧图片
            for kf in metadata.get('key_frames', []):
                phase = kf.get('phase')
                img_path = template_dir / f"{phase}.jpg"
                print(f"  - {phase}.jpg 存在: {img_path.exists()}")
