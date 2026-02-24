#!/usr/bin/env python3
"""测试核心依赖"""

import sys

print("=" * 50)
print("测试核心依赖")
print("=" * 50)

# 测试FastAPI
try:
    import fastapi
    print("✅ FastAPI      - 已安装")
except ImportError as e:
    print(f"❌ FastAPI      - 未安装: {e}")
    sys.exit(1)

# 测试Uvicorn
try:
    import uvicorn
    print("✅ Uvicorn      - 已安装")
except ImportError as e:
    print(f"❌ Uvicorn      - 未安装: {e}")
    sys.exit(1)

# 测试NumPy
try:
    import numpy as np
    print(f"✅ NumPy        - 已安装 (v{np.__version__})")
except ImportError as e:
    print(f"❌ NumPy        - 未安装: {e}")
    sys.exit(1)

# 测试OpenCV
try:
    import cv2
    print(f"✅ OpenCV       - 已安装 (v{cv2.__version__})")
except ImportError as e:
    print(f"❌ OpenCV       - 未安装: {e}")
    sys.exit(1)

# 测试MediaPipe
try:
    import mediapipe as mp
    print(f"✅ MediaPipe    - 已安装 (v{mp.__version__})")
except ImportError as e:
    print(f"❌ MediaPipe    - 未安装: {e}")
    sys.exit(1)

# 测试Pydantic
try:
    import pydantic
    print(f"✅ Pydantic     - 已安装 (v{pydantic.__version__})")
except ImportError as e:
    print(f"❌ Pydantic     - 未安装: {e}")
    sys.exit(1)

print("=" * 50)
print("\n✅ 所有核心依赖已安装！")
print("\n现在可以启动服务：")
print("  python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
print("\n访问:")
print("  前端: http://localhost:8000/app")
print("  API文档: http://localhost:8000/docs")
print()
