"""
测试模板加载功能
直接验证模板能否正确加载
"""
from pathlib import Path
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.models.template import TemplateManager

# 初始化 TemplateManager
templates_dir = Path(__file__).parent / "templates"
manager = TemplateManager(templates_dir)

# 测试加载 DevinBooker 模板
template_id = "template_3e7fbf098d26"
print(f"\n{'='*60}")
print(f"测试加载模板: {template_id}")
print(f"{'='*60}\n")

template = manager.get_template(template_id)

if template:
    print(f"✅ 模板加载成功!")
    print(f"  - ID: {template.id}")
    print(f"  - 名称: {template.name}")
    print(f"  - 描述: {template.description}")
    print(f"  - 创建时间: {template.created_at}")
    print(f"  - 关键帧数量: {len(template.key_frames)}")
    print(f"\n关键帧详情:")
    for i, kf in enumerate(template.key_frames, 1):
        print(f"  {i}. {kf.phase}")
        print(f"     - 帧号: {kf.frame_number}")
        print(f"     - 时间: {kf.timestamp}s")
        print(f"     - 图片路径: {kf.image_path}")
        print(f"     - 角度数据: {len(kf.angles) if kf.angles else 0} 个")
else:
    print("❌ 模板加载失败!")

# 测试列出所有模板
print(f"\n{'='*60}")
print(f"所有模板列表:")
print(f"{'='*60}\n")

templates = manager.list_templates()
for t in templates:
    print(f"  - {t['name']} (ID: {t['id']})")
    print(f"    关键帧数量: {t['key_frame_count']}")
    print()
