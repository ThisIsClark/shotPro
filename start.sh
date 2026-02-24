#!/bin/bash

# 启动脚本
echo "🏀 启动投篮姿势分析系统..."

#!/bin/bash
cd /Users/liuyu/Code/shotImprovement
source venv/bin/activate
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000