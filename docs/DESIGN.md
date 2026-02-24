# 投篮姿势分析系统设计文档

## 1. 项目概述

### 1.1 项目名称
Basketball Shooting Form Analyzer (篮球投篮姿势分析器)

### 1.2 项目目标
构建一个 Web 应用，让用户上传侧面投篮视频，系统自动分析投篮姿势，识别问题并给出改进建议。

### 1.3 核心功能
- 用户上传侧面投篮视频
- 使用 MediaPipe 进行人体关键点检测
- 分析投篮各阶段的关键角度和姿势
- 生成带有骨骼标注的可视化视频/图片
- 根据标准投篮姿势规则评估并给出建议

---

## 2. 技术架构

### 2.1 技术栈选型

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| 后端框架 | FastAPI | 高性能异步框架，自带 OpenAPI 文档 |
| 视频处理 | OpenCV | 视频帧提取、图像处理 |
| 姿态检测 | MediaPipe Pose | Google 的人体姿态估计方案，33个关键点 |
| 任务队列 | Celery + Redis | 异步处理视频分析任务 |
| 数据库 | PostgreSQL | 存储用户数据、分析结果 |
| 文件存储 | 本地/S3 | 存储上传的视频和生成的结果 |
| 前端 | Vue.js / React (可选) | 用户界面 |

### 2.2 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client (Browser)                         │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                      FastAPI Application                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Upload API  │  │ Analysis API│  │ Result API              │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
        ┌───────────────────┐       ┌───────────────────┐
        │   Redis (Queue)   │       │   PostgreSQL      │
        └─────────┬─────────┘       └───────────────────┘
                  │
                  ▼
        ┌───────────────────┐
        │  Celery Workers   │
        │  ┌─────────────┐  │
        │  │ OpenCV      │  │
        │  │ MediaPipe   │  │
        │  │ Analyzer    │  │
        │  └─────────────┘  │
        └───────────────────┘
                  │
                  ▼
        ┌───────────────────┐
        │  File Storage     │
        │  (Videos/Results) │
        └───────────────────┘
```

---

## 3. MediaPipe 关键点说明

### 3.1 投篮分析相关的关键点

MediaPipe Pose 提供 33 个人体关键点，投篮分析主要使用以下关键点：

```
投篮手侧 (以右手为例):
┌────────────────────────────────────────┐
│  11 - 左肩    12 - 右肩               │
│  13 - 左肘    14 - 右肘               │
│  15 - 左腕    16 - 右腕               │
│  23 - 左髋    24 - 右髋               │
│  25 - 左膝    26 - 右膝               │
│  27 - 左踝    28 - 右踝               │
│  19 - 左食指  20 - 右食指 (出手方向)   │
└────────────────────────────────────────┘
```

### 3.2 关键角度定义

| 角度名称 | 计算方式 | 标准范围 | 说明 |
|----------|----------|----------|------|
| 肘部角度 | 肩-肘-腕 | 准备: 70°-90°, 出手: 150°-180° | 出手时手臂应接近完全伸直 |
| 肩部角度 | 髋-肩-肘 | 45°-90° | 手臂抬起的角度 |
| 膝盖角度 | 髋-膝-踝 | 下蹲: 90°-120°, 起跳: 150°-180° | 腿部发力程度 |
| 躯干倾斜 | 垂直线与肩-髋连线 | 0°-15° | 身体应基本保持直立 |
| 手腕角度 | 肘-腕-食指 | 出手后: 向下弯曲 | 跟随动作 |

---

## 4. 投篮阶段划分

### 4.1 阶段定义

```
时间线: ────────────────────────────────────────────────>

阶段:   [  准备阶段  ] [ 上升阶段 ] [ 出手阶段 ] [ 跟随阶段 ]
        
        持球准备      开始上举    最高点出手   出手后保持
        屈膝蓄力      手臂上抬    手臂伸直     手腕下压
```

### 4.2 阶段检测逻辑

| 阶段 | 检测条件 |
|------|----------|
| 准备阶段 | 膝盖角度 < 120°，肘部角度 < 100° |
| 上升阶段 | 腕部 Y 坐标持续上升 |
| 出手阶段 | 肘部角度接近 180°，腕部达到最高点 |
| 跟随阶段 | 腕部 Y 坐标开始下降，手腕弯曲 |

---

## 5. 分析规则引擎

### 5.1 评估维度

```python
class ShootingFormRules:
    """投篮姿势评估规则"""
    
    rules = {
        # 肘部规则
        "elbow_alignment": {
            "description": "肘部是否内收",
            "check": "肘部应在肩部正下方，不应外展",
            "weight": 0.2
        },
        
        # 出手角度规则
        "release_angle": {
            "description": "出手时手臂伸展程度",
            "check": "出手时肘部角度应接近180°",
            "weight": 0.2
        },
        
        # 腿部发力规则
        "leg_power": {
            "description": "腿部蓄力和发力",
            "check": "准备阶段膝盖应有足够弯曲",
            "weight": 0.15
        },
        
        # 身体平衡规则
        "body_balance": {
            "description": "躯干稳定性",
            "check": "出手时身体不应过度前倾或后仰",
            "weight": 0.15
        },
        
        # 跟随动作规则
        "follow_through": {
            "description": "出手后的跟随动作",
            "check": "手腕应自然下压，保持跟随",
            "weight": 0.15
        },
        
        # 动作连贯性
        "fluidity": {
            "description": "整体动作连贯性",
            "check": "从下蹲到出手应一气呵成",
            "weight": 0.15
        }
    }
```

### 5.2 评分机制

```
总分 = Σ (单项得分 × 权重) × 100

评级:
- 90-100: 优秀 (Excellent)
- 75-89:  良好 (Good)
- 60-74:  一般 (Fair)
- < 60:   需改进 (Needs Improvement)
```

---

## 6. API 设计

### 6.1 接口列表

```yaml
POST /api/v1/videos/upload
  描述: 上传投篮视频
  请求: multipart/form-data (video file)
  响应: { task_id, status, message }

GET /api/v1/tasks/{task_id}/status
  描述: 查询分析任务状态
  响应: { task_id, status, progress, message }

GET /api/v1/tasks/{task_id}/result
  描述: 获取分析结果
  响应: { 
    task_id,
    overall_score,
    rating,
    phases: [...],
    issues: [...],
    suggestions: [...],
    annotated_video_url,
    key_frames: [...]
  }

GET /api/v1/analysis/{analysis_id}
  描述: 获取历史分析记录
  响应: { analysis details }
```

### 6.2 响应数据结构

```json
{
  "task_id": "uuid",
  "overall_score": 78.5,
  "rating": "Good",
  "phases": [
    {
      "name": "准备阶段",
      "frame_range": [0, 30],
      "metrics": {
        "knee_angle": 95,
        "elbow_angle": 85
      },
      "score": 80,
      "issues": []
    }
  ],
  "issues": [
    {
      "type": "elbow_flare",
      "severity": "medium",
      "description": "出手时肘部略微外展",
      "frame": 45
    }
  ],
  "suggestions": [
    {
      "priority": 1,
      "title": "保持肘部内收",
      "description": "出手时保持肘部在肩部正下方...",
      "reference_video": "url_to_tutorial"
    }
  ],
  "annotated_video_url": "/results/xxx/annotated.mp4",
  "key_frames": [
    {
      "phase": "release",
      "frame_number": 45,
      "image_url": "/results/xxx/frame_45.jpg",
      "annotations": {...}
    }
  ]
}
```

---

## 7. 项目目录结构

```
basketball-shooting-analysis/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 应用入口
│   ├── config.py               # 配置管理
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── upload.py       # 上传接口
│   │   │   ├── analysis.py     # 分析接口
│   │   │   └── health.py       # 健康检查
│   │   └── dependencies.py     # 依赖注入
│   ├── core/
│   │   ├── __init__.py
│   │   ├── pose_detector.py    # MediaPipe 姿态检测
│   │   ├── angle_calculator.py # 角度计算
│   │   ├── phase_detector.py   # 阶段检测
│   │   ├── rules_engine.py     # 规则引擎
│   │   └── video_processor.py  # 视频处理
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py         # 数据库模型
│   │   └── schemas.py          # Pydantic 模型
│   ├── services/
│   │   ├── __init__.py
│   │   ├── analysis_service.py # 分析服务
│   │   └── storage_service.py  # 存储服务
│   └── workers/
│       ├── __init__.py
│       └── celery_app.py       # Celery 配置和任务
├── tests/
│   ├── __init__.py
│   ├── test_pose_detector.py
│   ├── test_angle_calculator.py
│   └── test_api.py
├── uploads/                    # 上传文件目录
├── results/                    # 分析结果目录
├── docs/
│   └── DESIGN.md              # 本设计文档
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

## 8. 核心算法流程

### 8.1 视频分析流程

```
输入视频
    │
    ▼
┌─────────────────────┐
│ 1. 视频预处理       │  - 提取帧 (建议 30fps)
│                     │  - 调整分辨率
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 2. 姿态检测         │  - MediaPipe Pose
│                     │  - 获取 33 个关键点
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 3. 角度计算         │  - 计算各关节角度
│                     │  - 平滑处理 (移动平均)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 4. 阶段划分         │  - 识别投篮各阶段
│                     │  - 标记关键帧
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 5. 规则评估         │  - 应用评估规则
│                     │  - 计算各项得分
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ 6. 生成结果         │  - 标注视频/图片
│                     │  - 生成建议报告
└─────────────────────┘
```

### 8.2 角度计算算法

```python
import numpy as np

def calculate_angle(point1, point2, point3):
    """
    计算三个点形成的角度
    point2 是顶点
    
    返回角度 (0-180度)
    """
    vector1 = np.array(point1) - np.array(point2)
    vector2 = np.array(point3) - np.array(point2)
    
    cos_angle = np.dot(vector1, vector2) / (
        np.linalg.norm(vector1) * np.linalg.norm(vector2)
    )
    angle = np.arccos(np.clip(cos_angle, -1.0, 1.0))
    
    return np.degrees(angle)
```

---

## 9. 常见问题检测

### 9.1 问题类型定义

| 问题代码 | 问题名称 | 检测方法 | 影响 |
|----------|----------|----------|------|
| `ELBOW_FLARE` | 肘部外展 | 肘部 X 坐标偏离肩部 | 影响出手稳定性 |
| `WRIST_FLIP` | 手腕甩动 | 手腕角度变化过大 | 影响出手一致性 |
| `NO_FOLLOW` | 缺少跟随 | 出手后手腕角度保持不变 | 影响球的旋转 |
| `BODY_LEAN` | 身体倾斜 | 躯干角度超过阈值 | 影响平衡和准度 |
| `LOW_RELEASE` | 出手点过低 | 出手时手腕高度不够 | 容易被盖帽 |
| `KNEE_COLLAPSE` | 膝盖内扣 | 膝盖 X 坐标内移 | 影响下肢发力 |
| `THUMB_PUSH` | 拇指推球 | (需要更精细检测) | 影响球的旋转 |

---

## 10. 部署方案

### 10.1 开发环境

```bash
# 本地开发
docker-compose up -d redis postgres
uvicorn app.main:app --reload
celery -A app.workers.celery_app worker --loglevel=info
```

### 10.2 生产环境

```yaml
# docker-compose.prod.yml
services:
  api:
    build: .
    replicas: 2
    
  worker:
    build: .
    command: celery worker
    replicas: 3  # 视频处理较耗资源
    
  redis:
    image: redis:alpine
    
  postgres:
    image: postgres:15
```

---

## 11. 性能考虑

### 11.1 视频处理优化

- 限制上传视频大小 (建议 < 50MB)
- 限制视频时长 (建议 < 10秒)
- 降采样处理 (不需要分析每一帧)
- 使用 GPU 加速 (如有条件)

### 11.2 并发处理

- 使用 Celery 异步处理视频分析
- 设置合理的 Worker 数量
- 任务超时设置 (建议 5 分钟)

---

## 12. 后续扩展

### 12.1 功能扩展
- [ ] 支持正面视频分析
- [ ] 支持多人同时分析
- [ ] 对比标准球员动作
- [ ] 历史数据追踪进步
- [ ] 移动端适配

### 12.2 技术扩展
- [ ] 使用深度学习模型提高准确度
- [ ] 3D 姿态重建
- [ ] 实时分析 (WebRTC)

---

## 13. 开发计划

### Phase 1: 核心功能 (MVP)
1. 搭建 FastAPI 项目框架
2. 实现视频上传接口
3. 集成 MediaPipe 姿态检测
4. 实现角度计算模块
5. 实现基础规则引擎
6. 生成标注图片/视频
7. 简单的结果展示页面

### Phase 2: 完善功能
1. 添加 Celery 异步处理
2. 数据库存储分析历史
3. 丰富评估规则
4. 优化前端界面

### Phase 3: 优化增强
1. 性能优化
2. 添加用户系统
3. 部署上线

---

## 14. 风险与挑战

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 视频质量差 | 关键点检测不准 | 提供拍摄指南，增加置信度过滤 |
| 侧面角度不标准 | 分析结果偏差 | 提示用户调整角度，多角度融合 |
| MediaPipe 遮挡问题 | 关键点丢失 | 使用插值填补，标记不可靠区域 |
| 不同投篮风格 | 规则不通用 | 提供多种标准模板，支持自定义 |

---

## 15. 参考资源

- [MediaPipe Pose 文档](https://developers.google.com/mediapipe/solutions/vision/pose_landmarker)
- [OpenCV Python 文档](https://docs.opencv.org/)
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- 篮球投篮技术分析相关论文

---

**文档版本**: v1.0  
**最后更新**: 2024年  
**作者**: AI Assistant  

---

请 review 此设计文档，如有任何问题或需要调整的地方请告诉我，确认无误后我们开始编码实现。
