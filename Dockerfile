# 使用官方 Python 3.12 轻量级镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 安装系统依赖 (MediaPipe 和 OpenCV 需要)
# MediaPipe 需要 OpenGL ES 和 EGL 库
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1 \
    libgomp1 \
    libegl1 \
    libgles2 \
    libglvnd0 \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
# 使用 --no-cache-dir 减小镜像体积
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口（Railway 通过 PORT 环境变量自动分配）
EXPOSE 8000

# 启动命令
# Railway 会注入 PORT 环境变量，本地默认 8000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
