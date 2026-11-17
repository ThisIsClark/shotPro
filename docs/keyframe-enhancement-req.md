# 需求文档：关键帧增强 — 角度极值帧 + 曲线联动

## 1. 背景

当前系统已有 4 个关键帧（沉球点、手上升后、最高持球点、出手点），主要用于发力连贯性检测。这些关键帧是"检测逻辑驱动"的——它们的存在是为了对比两帧之间的膝盖角度差异。

但用户在查看曲线图时，缺少对**角度极值点**的直观认知。比如膝盖弯曲最深的那一刻、手肘折叠最紧的那一刻，这些是投篮动作中非常关键的姿态节点，也是教练最常强调的"checkpoints"。

## 2. 新增关键帧定义

在现有 4 帧基础上，新增以下关键帧：

| # | 关键帧 | 英文 key | 含义 | 检测逻辑 |
|---|--------|----------|------|----------|
| 1 | **最低蹲点** | `knee_min_frame` | 膝盖弯曲角度最小的帧 | 在 preparation + lifting 阶段范围内，找 `knee_angle` 最小值对应的帧。这是从下蹲到蹬伸的转折点，代表蓄力完成瞬间 |
| 2 | **最紧折叠点** | `elbow_min_frame` | 手肘角度最小的帧 | 在 lifting + release 阶段范围内，找 `elbow_angle` 最小值对应的帧。这是起球到出手的过渡点，代表手臂蓄力最紧的状态 |
| 3 | **手腕最高点** | `wrist_peak_frame` | 手腕物理位置最高的帧 | 全范围找 `wrist_y`（归一化坐标）最小值对应的帧。这是出手瞬间的精确帧，比现有 RELEASE_FRAME 更直观——RELEASE_FRAME 是"减速后恢复"的检测帧，而这是纯粹的物理最高点 |
| 4 | **出手后跟随点** | `follow_through_frame` | 出手后手腕开始明显下落后的稳定帧 | 在 wrist_peak_frame 之后，找手腕 Y 值从最低点回升后趋于稳定的帧（连续 3 帧变化 < 0.005）。代表跟随动作的定型姿态 |

### 为什么选这 4 个

- **最低蹲点**和**最紧折叠点**是你明确提出的，分别对应下肢和上肢的蓄力极值
- **手腕最高点**：现有 RELEASE_FRAME 的检测逻辑较复杂（找减速区），对用户来说"出手瞬间"最直观的定义就是球离手的那一刻=手腕最高点。这个帧和 RELEASE_FRAME 可能接近但未必相同，作为独立关键帧更有价值
- **出手后跟随点**：跟随动作是 BEEF 中的 F（Follow-through），但当前系统没有专门捕捉这个姿态。教练常说"出手后保持姿势 1-2 秒"，这个帧就是那个定型姿态

## 3. 数据结构变更

### 3.1 ShootingPhase 枚举扩展

在 `app/core/phase_detector.py` 的 `ShootingPhase` 中新增：

```python
# 角度极值关键帧
KNEE_MIN_FRAME = "knee_min_frame"          # 最低蹲点
ELBOW_MIN_FRAME = "elbow_min_frame"        # 最紧折叠点
WRIST_PEAK_FRAME = "wrist_peak_frame"      # 手腕最高点
FOLLOW_THROUGH_FRAME = "follow_through_frame"  # 出手后跟随点
```

### 3.2 get_key_frames() 扩展

`PhaseDetector.get_key_frames()` 返回的 dict 从 4 帧扩展为 8 帧。新增 4 帧的检测逻辑：

- `knee_min_frame`：在 `preparation` + `lifting` 阶段帧中，取 `knee_angle` 最小的帧
- `elbow_min_frame`：在 `lifting` + `release` 阶段帧中，取 `elbow_angle` 最小的帧
- `wrist_peak_frame`：全范围取 `wrist_y`（原始值）最小的帧（已有 `min_wrist_y_frame` 逻辑，直接复用）
- `follow_through_frame`：在 `wrist_peak_frame` 之后，找手腕 Y 值回升后连续 3 帧变化 < 0.005 的帧

### 3.3 KeyFrameInfo / FullAnalysisResult

`KeyFrameInfo` 的 `phase` 字段已支持任意 `ShootingPhase` 枚举值，无需修改结构。

`FullAnalysisResult.key_frames` 列表会从最多 4 项变为最多 8 项。

### 3.4 TemplateKeyFrame 扩展

`app/models/template.py` 的 `TemplateKeyFrame.phase` 字段是 `str` 类型，天然支持新值，无需修改结构。

模板的 `metadata.json` 中 `key_frames` 数组会包含更多条目。

## 4. 前端展示

### 4.1 曲线图联动（核心交互）

在角度时序曲线图上，用**竖线标记 + 标签**标注所有关键帧的位置：

- 现有 4 帧（沉球点等）用**白色半透明虚线**（已有）
- 新增 4 帧用**彩色实线 + 顶部标签**，颜色与对应关节曲线一致：
  - `knee_min_frame` → 红色实线（与 knee_angle 曲线同色 `#ff6b6b`），标签 "🦵 最低蹲"
  - `elbow_min_frame` → 青色实线（与 elbow_angle 曲线同色 `#48dbfb`），标签 "💪 最紧折"
  - `wrist_peak_frame` → 白色实线，标签 "🎯 最高点"
  - `follow_through_frame` → 灰色实线，标签 "🫳 跟随"

**点击竖线 → 弹出该帧的关键帧图片**（lightbox 或 inline 展示），实现曲线与画面的联动。

### 4.2 关键帧图片展示

在曲线图下方，新增一个**关键帧时间轴条**（horizontal timeline strip）：

```
[最低蹲] → [沉球点] → [最紧折] → [手上升后] → [最高点] → [最高持球] → [出手点] → [跟随点]
   🦵         📍         💪         📍          🎯         📍          📍         🫳
```

- 每个节点是一张缩略图 + 标签
- 按时间顺序排列
- 点击缩略图可放大查看
- 当前被选中的关键帧高亮，曲线图上对应竖线也高亮

### 4.3 发力连贯性检测区域

现有的手脚同步性和发力脱节卡片**保持不变**，它们仍然使用原来的 4 帧（sync_frame_1/2, max_hold_frame, release_frame）做对比展示。

新增的关键帧不参与发力连贯性检测逻辑，它们是独立的姿态参考点。

## 5. 模板系统变更

### 5.1 模板创建

`POST /api/v1/templates/create` 的分析流程会自动生成 8 个关键帧（因为 `PhaseDetector.get_key_frames()` 返回 8 帧），模板目录下会保存 8 张关键帧图片：

```
templates/{template_id}/
├── metadata.json          # key_frames 数组含 8 项
├── sync_frame_1.jpg
├── sync_frame_2.jpg
├── max_hold_frame.jpg
├── release_frame.jpg
├── knee_min_frame.jpg     # 新增
├── elbow_min_frame.jpg    # 新增
├── wrist_peak_frame.jpg   # 新增
├── follow_through_frame.jpg  # 新增
├── angles.json
└── phases.json
```

### 5.2 模板对比

关键帧图片对比（lightbox 中的左右对比）需要支持新的 4 帧。对比逻辑不变：同 phase 的用户帧 vs 模板帧并排展示。

曲线对比（comparison_service.py）不受影响——曲线对比基于 per-frame 时序数据，不依赖关键帧。

## 6. 实现范围

### 后端

| 文件 | 变更 |
|------|------|
| `app/core/phase_detector.py` | ShootingPhase 枚举 +4；get_key_frames() +4 帧检测逻辑 |
| `app/services/analysis_service.py` | 关键帧生成循环从 4 帧扩展为 8 帧；PHASE_NAMES +4 |
| `app/models/template.py` | 无结构变更（phase字段是 str，天然兼容 |
| `app/api/routes/templates.py` | 无变更（自动跟随 get_key_frames 扩展） |

### 前端

| 区域 | 变更 |
|------|------|
| 曲线图渲染 | 新增 4 条彩色竖线 + 标签；点击竖线弹出关键帧图片 |
| 关键帧时间轴 | 新增水平时间轴条组件，8 帧缩略图 + 标签 |
| Lightbox | 支持新 phase 的模板对比 |
| i18n | 新增 4 个关键帧的中英文名称 |

## 7. 不在范围内

- 不修改发力连贯性检测逻辑（rules_engine.py）
- 不修改曲线对比算法（comparison_service.py）
- 不修改 PDF 导出（后续可单独迭代）
- 不修改评分系统

## 8. 风险与注意事项

1. **帧重复**：`wrist_peak_frame` 和现有 `RELEASE_FRAME` 可能是同一帧或非常接近。前端展示时如果两帧间隔 < 2 帧，可合并显示标签避免重叠
2. **检测失败**：新增帧的检测可能失败（如膝盖不在画面内），需 graceful fallback——该帧标记为 None，前端不显示对应竖线
3. **模板兼容性**：旧模板只有 4 帧关键帧，前端需兼容 key_frames 数组长度不同的情况
4. **性能**：关键帧从 4 增到 8，图片生成多 4 张，但每张只是单帧提取+标注，耗时可忽略
