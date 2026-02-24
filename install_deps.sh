#!/bin/bash

echo "🔧 开始安装依赖..."
echo ""

# 第一步：安装基础依赖
echo "📦 步骤 1/3: 安装基础依赖..."
pip3 install --user --no-cache-dir \
    fastapi==0.109.0 \
    uvicorn[standard]==0.27.0 \
    python-multipart==0.0.9 \
    aiofiles==23.2.1 \
    pydantic==2.5.0 \
    pydantic-settings==2.1.0 \
    python-dotenv==1.0.0

if [ $? -ne 0 ]; then
    echo "❌ 基础依赖安装失败"
    exit 1
fi

echo "✅ 基础依赖安装完成"
echo ""

# 第二步：安装视频处理依赖
echo "📦 步骤 2/3: 安装 OpenCV 和 NumPy..."
pip3 install --user --no-cache-dir \
    numpy==1.24.3 \
    opencv-python-headless==4.9.0.80

if [ $? -ne 0 ]; then
    echo "❌ OpenCV 安装失败"
    exit 1
fi

echo "✅ OpenCV 安装完成"
echo ""

# 第三步：安装 MediaPipe（跳过 opencv-contrib-python 依赖）
echo "📦 步骤 3/3: 安装 MediaPipe..."

# 先安装 MediaPipe 的其他依赖
pip3 install --user --no-cache-dir \
    attrs>=19.1.0 \
    "protobuf<4,>=3.11" \
    absl-py \
    "flatbuffers>=2.0" \
    matplotlib

# 安装 MediaPipe，跳过依赖检查
pip3 install --user --no-cache-dir --no-deps mediapipe==0.10.9

if [ $? -ne 0 ]; then
    echo "❌ MediaPipe 安装失败"
    exit 1
fi

echo "✅ MediaPipe 安装完成"
echo ""

# 验证安装
echo "🔍 验证安装..."
python3 test_import.py

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 所有依赖安装成功！"
    echo ""
    echo "下一步："
    echo "  运行: ./start.sh"
    echo "  或者: python3 -m uvicorn app.main:app --reload"
else
    echo ""
    echo "⚠️  部分依赖可能有问题，但可以尝试启动服务"
fi
