# 🏀 Basketball Shooting Form Analyzer

投篮姿势分析系统 - 上传投篮视频，获取专业的姿势分析和改进建议。

## 功能特点

- 📹 **视频上传**：支持 MP4, MOV, AVI, WebM 格式
- 🦴 **姿态检测**：使用 MediaPipe 进行人体关键点检测
- 📐 **角度分析**：计算肘部、肩部、膝盖等关键角度
- 📊 **阶段划分**：自动识别准备、上升、出手、跟随四个阶段
- ⚡ **规则评估**：基于专业投篮标准进行多维度评分
- 🎯 **问题检测**：识别常见投篮问题并给出建议
- 🎬 **可视化输出**：生成带骨骼标注的视频和关键帧图片

## 技术栈

- **后端框架**: FastAPI
- **视频处理**: OpenCV
- **姿态检测**: MediaPipe Pose
- **前端**: 原生 HTML/CSS/JavaScript

## 快速开始

### 1. 安装依赖

```bash
# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 运行服务

```bash
# 开发模式
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. 访问应用

- **前端界面**: http://localhost:8000/app
- **API 文档**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API 接口

### 上传视频

```bash
POST /api/v1/videos/upload
Content-Type: multipart/form-data

# 参数
- file: 视频文件
- shooting_hand: 投篮手 ("left" 或 "right")

# 响应
{
    "task_id": "uuid",
    "message": "视频上传成功，开始分析",
    "filename": "video.mp4"
}
```

### 查询状态

```bash
GET /api/v1/videos/tasks/{task_id}/status

# 响应
{
    "task_id": "uuid",
    "status": "processing",
    "progress": 50,
    "message": "处理帧 150/300"
}
```

### 获取结果

```bash
GET /api/v1/videos/tasks/{task_id}/result

# 响应
{
    "task_id": "uuid",
    "overall_score": 78.5,
    "rating": "good",
    "dimension_scores": [...],
    "issues": [...],
    "suggestions": [...],
    "key_frames": [...],
    "annotated_video_url": "/results/uuid/annotated.mp4"
}
```

## 项目结构

```
basketball-shooting-analysis/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 应用入口
│   ├── config.py               # 配置管理
│   ├── api/
│   │   └── routes/
│   │       ├── upload.py       # 上传接口
│   │       └── health.py       # 健康检查
│   ├── core/
│   │   ├── pose_detector.py    # MediaPipe 姿态检测
│   │   ├── angle_calculator.py # 角度计算
│   │   ├── phase_detector.py   # 阶段检测
│   │   ├── rules_engine.py     # 规则引擎
│   │   └── video_processor.py  # 视频处理
│   ├── models/
│   │   └── schemas.py          # Pydantic 模型
│   └── services/
│       └── analysis_service.py # 分析服务
├── templates/
│   └── index.html              # 前端页面
├── uploads/                    # 上传文件目录
├── results/                    # 分析结果目录
├── docs/
│   └── DESIGN.md              # 设计文档
├── requirements.txt
└── README.md
```

## 评估维度

| 维度 | 权重 | 说明 |
|------|------|------|
| 肘部伸展 | 20% | 出手时手臂伸展程度 |
| 腿部发力 | 15% | 准备阶段膝盖弯曲和腿部蓄力 |
| 身体平衡 | 15% | 躯干稳定性 |
| 出手点 | 20% | 出手位置和角度 |
| 跟随动作 | 15% | 出手后的手腕跟随 |
| 动作连贯 | 15% | 整体动作流畅性 |

## 评级标准

- **优秀 (Excellent)**: 90-100 分
- **良好 (Good)**: 75-89 分
- **一般 (Fair)**: 60-74 分
- **需改进 (Needs Improvement)**: 60 分以下

## 拍摄建议

为获得最佳分析效果，请注意：

1. **侧面拍摄**：从投篮手一侧拍摄，确保能看清手臂和腿部动作
2. **全身入镜**：确保从头到脚都在画面中
3. **光线充足**：在光线良好的环境拍摄
4. **稳定画面**：使用三脚架或保持手机稳定
5. **单人画面**：画面中只有一个人
6. **时长控制**：视频时长建议在 10 秒以内

## 常见问题检测

- 肘部外展
- 手臂未完全伸展
- 膝盖弯曲不足
- 身体倾斜过大
- 出手点过低
- 缺少跟随动作
- 动作不连贯

## License

MIT License
