"""
修复现有模板的image_path
"""

import sys
sys.path.append('/Users/liuyu/Code/shotImprovement')

from pathlib import Path
import json

templates_dir = Path('/Users/liuyu/Code/shotImprovement/templates')

if templates_dir.exists():
    template_dirs = [d for d in templates_dir.iterdir() if d.is_dir() and d.name.startswith('template_')]
    
    for template_dir in template_dirs:
        metadata_file = template_dir / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            print(f"\n处理模板: {metadata.get('name')} ({template_dir.name})")
            
            # 检查是否需要修复
            needs_fix = False
            for kf in metadata.get('key_frames', []):
                image_path = kf.get('image_path', '')
                if image_path.startswith('template_images/'):
                    needs_fix = True
                    old_path = image_path
                    new_path = image_path.replace('template_images/', 'templates/')
                    print(f"  修复: {old_path} -> {new_path}")
                    kf['image_path'] = new_path
            
            if needs_fix:
                # 备份原文件
                backup_file = metadata_file.with_suffix('.json.bak')
                import shutil
                shutil.copy(metadata_file, backup_file)
                print(f"  备份: {backup_file}")
                
                # 保存修复后的文件
                with open(metadata_file, 'w', encoding='utf-8') as f:
                    json.dump(metadata, f, ensure_ascii=False, indent=2)
                print(f"  ✓ 已修复并保存")
            else:
                print(f"  ✓ 无需修复")
    
    print("\n所有模板处理完成！")
else:
    print("templates 目录不存在")
