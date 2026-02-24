#!/usr/bin/env python3
"""
测试依赖是否安装成功
"""

import sys

def test_imports():
    """测试所有必要的包是否可以导入"""
    packages = [
        ('fastapi', 'FastAPI'),
        ('uvicorn', 'Uvicorn'),
        ('cv2', 'OpenCV'),
        ('mediapipe', 'MediaPipe'),
        ('numpy', 'NumPy'),
        ('pydantic', 'Pydantic'),
    ]
    
    success = True
    print("=" * 50)
    print("测试依赖包安装状态")
    print("=" * 50)
    
    for module_name, display_name in packages:
        try:
            __import__(module_name)
            print(f"✅ {display_name:15s} - 已安装")
        except ImportError as e:
            print(f"❌ {display_name:15s} - 未安装 ({e})")
            success = False
    
    print("=" * 50)
    
    if success:
        print("\n✅ 所有依赖已安装，可以启动服务！")
        print("\n运行命令:")
        print("  python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
        print("\n或使用启动脚本:")
        print("  ./start.sh")
        return 0
    else:
        print("\n❌ 部分依赖未安装，请运行:")
        print("  pip3 install -r requirements.txt --user")
        return 1

if __name__ == "__main__":
    sys.exit(test_imports())
