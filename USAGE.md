# 使用指南

## 快速开始

### 1. 安装依赖

```bash
# 安装 Python 依赖
pip3 install -r requirements.txt --user

# 测试依赖是否安装成功
python3 test_import.py
```

### 2. 启动服务

**方式一：使用启动脚本**
```bash
./start.sh
```

**方式二：直接运行**
```bash
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. 访问应用

启动后打开浏览器访问：

- **前端界面**: http://localhost:8000/app
- **API 文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

## 使用步骤

### Web 界面使用

1. 打开 http://localhost:8000/app
2. 点击或拖拽上传投篮视频（支持 MP4, MOV, AVI, WebM）
3. 选择投篮手（左手或右手）
4. 点击"开始分析"
5. 等待分析完成（进度条会显示实时进度）
6. 查看分析结果：
   - 总分和评级
   - 各项评分详情
   - 问题和改进建议
   - 关键帧图片
   - 标注视频

### API 使用

#### 上传视频

```bash
curl -X POST "http://localhost:8000/api/v1/videos/upload?shooting_hand=right" \
  -F "file=@your_video.mp4"
```

响应:
```json
{
  "task_id": "abc-123-def",
  "message": "视频上传成功，开始分析",
  "filename": "your_video.mp4"
}
```

#### 查询分析状态

```bash
curl "http://localhost:8000/api/v1/videos/tasks/abc-123-def/status"
```

响应:
```json
{
  "task_id": "abc-123-def",
  "status": "processing",
  "progress": 50,
  "message": "处理帧 150/300"
}
```

#### 获取分析结果

```bash
curl "http://localhost:8000/api/v1/videos/tasks/abc-123-def/result"
```

## 视频拍摄建议

为获得最佳分析效果：

1. **拍摄角度**: 从投篮手一侧拍摄（侧面45度最佳）
2. **画面范围**: 确保从头到脚完整入镜
3. **光线条件**: 在光线充足的环境拍摄
4. **画面稳定**: 使用三脚架或保持相机稳定
5. **单人画面**: 避免多人同时出现
6. **视频时长**: 建议 3-10 秒（包含完整投篮动作）
7. **背景简洁**: 避免复杂背景干扰识别

## 分析结果说明

### 评分维度

1. **肘部伸展 (20%)**: 出手时手臂伸展程度
2. **腿部发力 (15%)**: 准备阶段膝盖弯曲和腿部蓄力
3. **身体平衡 (15%)**: 躯干稳定性
4. **出手点 (20%)**: 出手位置和角度
5. **跟随动作 (15%)**: 出手后的手腕跟随
6. **动作连贯 (15%)**: 整体动作流畅性

### 评级标准

- **优秀 (90-100)**: 动作标准，几乎无需改进
- **良好 (75-89)**: 基本标准，有小幅改进空间
- **一般 (60-74)**: 存在一些问题，需要针对性改进
- **需改进 (<60)**: 多处问题，建议系统性练习

### 常见问题

- **肘部外展**: 出手时肘部向外展开
- **手臂未完全伸展**: 出手时手臂未伸直
- **膝盖弯曲不足**: 准备阶段下蹲不够
- **身体倾斜**: 出手时身体过度前倾或后仰
- **出手点过低**: 举球高度不够
- **缺少跟随动作**: 出手后没有手腕下压
- **动作不连贯**: 各阶段衔接不流畅

## 目录结构

```
shotImprovement/
├── uploads/          # 上传的视频文件
├── results/          # 分析结果
│   └── <task_id>/
│       ├── keyframe_preparation.jpg
│       ├── keyframe_lifting.jpg
│       ├── keyframe_release.jpg
│       ├── keyframe_follow_through.jpg
│       └── annotated.mp4
├── static/           # 静态文件
└── templates/        # 前端模板
```

## 故障排查

### 依赖安装失败

```bash
# 升级 pip
python3 -m pip install --upgrade pip

# 重新安装
pip3 install -r requirements.txt --user
```

### 端口已被占用

```bash
# 使用其他端口
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

### MediaPipe 检测失败

- 确保视频清晰，人物完整入镜
- 光线充足
- 避免复杂背景
- 尝试调整拍摄角度

### 视频处理慢

- 减少视频时长（建议 < 10 秒）
- 降低视频分辨率
- 确保系统有足够的内存

## 性能优化

### 生产环境部署

```bash
# 使用多个 worker
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# 或使用 gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

### 配置调整

编辑 `app/config.py`:

```python
# 视频限制
max_video_size_mb: int = 50
max_video_duration_seconds: int = 10

# 分析设置
target_fps: int = 30
min_detection_confidence: float = 0.5
min_tracking_confidence: float = 0.5
```

## 开发

### 运行测试

```bash
# TODO: 添加单元测试
pytest tests/
```

### 代码格式化

```bash
# 使用 black
black app/

# 使用 isort
isort app/
```

## 技术支持

如有问题，请查看：

1. API 文档: http://localhost:8000/docs
2. 设计文档: `docs/DESIGN.md`
3. README: `README.md`
