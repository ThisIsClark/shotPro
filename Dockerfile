# 使用官方 Python 3.12 轻量级镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 安装系统依赖 (MediaPipe 和 OpenCV 可能需要)
# 虽然使用了 headless 版本，但某些底层库可能仍需依赖 glib
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
# 使用 --no-cache-dir 减小镜像体积
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口 (Hugging Face Spaces 默认端口为 7860)
EXPOSE 7860

# 启动命令
# 使用 Shell 格式以支持 $PORT 环境变量扩展
# Hugging Face Spaces 要求监听 7860 端口
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}
