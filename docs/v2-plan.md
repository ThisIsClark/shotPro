# formrefine.ai v2 Plan - 曲线分析 + 模板对比

**目标：** 管理员可上传 NBA 球星投篮视频做模板（含完整曲线数据），普通用户分析时可选预设模板做曲线叠加对比，且用户自己也能看 6 关节角度时序曲线。

**核心约束：** 不破坏现有功能。所有改动是加法。复用现有 `local_auth_service` JWT 鉴权 + 前端 d3。

---

## 现状关键发现（决定方案的基础）

| 项 | 现状 | 影响 |
|----|------|------|
| per-frame 时序数据 | `AnalysisService.analyze_video` 内部 `frame_data_list` 已计算每帧 6 关节角度 + phase + wrist_y，但**只在内存用，未持久化**（`analysis_service.py:220`） | M1 只需把它接出来存盘 |
| `ShootingAngles` | 已有 `to_dict()`，6 个字段（elbow/shoulder/trunk 必有，knee/wrist/hip Optional）（`angle_calculator.py:11`） | 数据模型现成 |
| 模板存储 | `templates/{id}/metadata.json` + 4 张 `{phase}.jpg`，只存 4 关键帧角度（`template.py`） | M2 要加 `angles.json` + `phases.json` |
| 模板创建端点 | `POST /api/v1/templates/create` 已存在（`templates.py:23`），**完全无鉴权** | M2 要加 admin 检查 |
| 管理员鉴权 | `local_auth_service.py`（bcrypt + JWT + role）+ `admin.html` 登录页 + `/api/v1/auth/local-login` 已就绪 | 直接复用，不新建 |
| 用户端对比 | `upload.py:157` `_generate_comparison` 已实现 4 点角度 diff | M3 新增曲线对比并存 |
| 前端图表 | `templates/index.html` 已用 d3 | M4 不引新库 |

---

## M1 - 时序数据持久化（地基）

**用户和模板共用的数据模型。先做这步，M2/M3/M4 都依赖它。**

### 后端改动

1. **`FullAnalysisResult` 加字段**（`analysis_service.py:60`）
   ```python
   frame_data: list[dict] = field(default_factory=list)  # per-frame 时序
   ```
   每帧结构：
   ```json
   {"frame_number": 0, "timestamp": 0.0, "phase": "preparation",
    "angles": {"elbow_angle": 90.0, "shoulder_angle": 30.0, ...},
    "wrist_y": 0.5, "confidence": 0.9}
   ```

2. **`analyze_video` 末尾序列化 `frame_data_list`**（`analysis_service.py:507` return 前）
   ```python
   frame_data = [
       {
           "frame_number": fd.frame_number,
           "timestamp": fd.timestamp,
           "phase": fd.phase.value,
           "angles": fd.angles.to_dict() if fd.angles else None,
           "wrist_y": fd.wrist_y,
           "confidence": fd.confidence
       }
       for fd in frame_data_list
   ]
   ```
   传入 `FullAnalysisResult(..., frame_data=frame_data)`。

3. **`to_dict()` 包含 `frame_data`**（`analysis_service.py:72`）
   主响应带 `frame_data`，但前端图表单独 fetch 文件避免主响应过大：
   - 持久化到 `results/{task_id}/frame_data.json`
   - `to_dict()` 里只放 `frame_data_url: /results/{task_id}/frame_data.json`，不放完整数组

4. **`AnalysisConfig` 加开关**（`analysis_service.py:25`）
   ```python
   generate_frame_data: bool = True
   ```
   模板创建场景下也开（M2 用）。

### 影响面
- 纯加法，`to_dict()` 多了字段，老前端忽略不影响
- 现有 `key_frames` / `coordination_issues` 不变
- 磁盘多写一个 `frame_data.json`（每帧 ~150 字节 × ~150 帧 ≈ 22KB，可忽略）

### 验收
- 用户分析后，`results/{task_id}/frame_data.json` 存在
- 文件含每帧 6 关节角度 + phase
- 老的功能（关键帧、协调性检测、PDF 导出）全部不破

---

## M2 - 管理员上传模板（含曲线数据）

### 鉴权：复用 local_auth_service JWT

1. **新增依赖函数** `app/api/deps.py`：
   ```python
   async def require_admin(token: str = Depends(jwt_bearer)) -> dict:
       payload = jwt_service.verify_token(token)
       if payload.get("role") != "admin":
           raise HTTPException(403, "Admin only")
       return payload
   ```
   （具体看现有 `deps.py` 写法对齐）

2. **`POST /api/v1/templates/create` 加 `Depends(require_admin)`**（`templates.py:23`）
   - 堵住当前的无鉴权漏洞
   - admin.html 已有登录页可拿 token

### 模板存储扩展

3. **`Template` 数据类加字段**（`template.py:23`）
   ```python
   has_curve_data: bool = False
   ```
   `to_dict()` / `from_dict()` 同步加，向后兼容（老模板缺字段默认 False）。

4. **创建模板时存曲线数据**（`templates.py` 的 `create_template` 内，分析完成后）
   ```python
   # angles.json - per-frame 6 关节时序
   angles_path = template_dir / "angles.json"
   with open(angles_path, 'w') as f:
       json.dump(result.frame_data, f)

   # phases.json - 阶段边界（对比时对齐用）
   phases = _extract_phase_boundaries(result.frame_data)  # 从 frame_data 推 4 阶段 start/end
   with open(template_dir / "phases.json", 'w') as f:
       json.dump(phases, f)

   template.has_curve_data = True
   ```
   `_extract_phase_boundaries`：扫 `frame_data` 的 `phase` 字段，记录每个阶段的首尾 frame_number。

5. **`TemplateManager.get_template` 加载曲线数据**（按需，不在 list 时加载避免内存爆）
   - 新增 `get_template_curves(template_id) -> dict` 单独读 `angles.json` + `phases.json`
   - `get_template` 主路径不读曲线（list 列表场景用不到）

### 影响面
- `templates/create` 端点行为变化：要 admin token。如果有其他地方调它（比如 admin.html 现有上传逻辑），确认带 token
- 老模板（无 `has_curve_data`）依然能用 4 点 diff 对比，曲线对比时降级提示"该模板无曲线数据"

### 验收
- 管理员登录后能上传 NBA 视频创建模板
- `templates/{id}/` 下有 `angles.json` + `phases.json` + `metadata.json` + 4 张 jpg
- 非管理员调 `create` 返回 403
- 现有 `list` / `get` 接口不破

---

## M3 - 模板对比 v2（曲线叠加 + 阶段对齐）

### 对比算法

**输入：** 用户 `frame_data`（M1 持久化）+ 模板 `angles.json` + `phases.json`

**阶段对齐（不用 DTW）：**
1. 用户和模板都有 4 阶段（preparation/lifting/release/follow_through）
2. 对每个阶段独立处理：取用户该阶段所有帧 + 模板该阶段所有帧
3. 各自重采样到统一长度（如 50 点，线性插值）
4. 计算每个关节的角度差曲线

**输出：**
```json
{
  "joints": [
    {
      "name": "elbow_angle",
      "user_curve": [/* 200 点，4 阶段各 50 */],
      "template_curve": [/* 200 点 */],
      "diff_curve": [/* 200 点 */],
      "max_diff_phase": "lifting",
      "max_diff_value": 12.5
    },
    /* shoulder/knee/trunk/wrist/hip */
  ],
  "phase_boundaries": {
    "preparation": {"user": [0, 40], "template": [0, 35]},
    /* ... */
  }
}
```

### 后端改动

6. **新增 `app/services/comparison_service.py`**
   - `compare_curves(user_frame_data: list, template_curves: dict) -> dict`
   - 含阶段对齐 + 重采样 + 差值计算逻辑
   - 纯函数，可单测

7. **`upload.py` 用户分析时调用**（`upload.py:157` 现有模板对比逻辑旁）
   ```python
   if template_id and template.has_curve_data:
       template_curves = template_manager.get_template_curves(template_id)
       curve_comparison = comparison_service.compare_curves(
           result.frame_data, template_curves
       )
       result_dict["template_comparison"]["curve_comparison"] = curve_comparison
   # 保留原 4 点 diff（result_dict["template_comparison"]["comparisons"]）兼容
   ```

### 影响面
- 用户分析响应多了 `curve_comparison` 字段（选了支持曲线的模板时）
- 老 4 点 diff 保留，老前端不破

### 验收
- 用户选带曲线的模板分析，响应含 `curve_comparison`
- 选老模板（无曲线），降级只返回 4 点 diff，不报错
- 曲线对齐正确（同阶段对比，不是按时间硬比）

---

## M4 - 用户端曲线图（前端 d3）

### 用户分析结果页

8. **新增曲线图组件**（`templates/index.html`，已有 d3）
   - 6 关节角度时序曲线（可切换显示哪些关节）
   - X 轴：帧 / 时间
   - 阶段背景色分区（4 阶段 4 种浅色）
   - 关键帧竖线标注 + 标签
   - 数据源：`/results/{task_id}/frame_data.json`

9. **模板对比视图**
   - 双线叠加图（用户实线 + 模板虚线）
   - 差值最大阶段高亮
   - 关键帧双标注

### 影响面
- 纯前端加视图，后端无改动
- 数据已有（M1 持久化的 frame_data.json）

### 验收
- 用户分析后能看到自己 6 关节曲线
- 选模板对比能看到双线叠加
- 移动端可读（9:16 适配，图表可横滑）

---

## 实施顺序与依赖

```
M1 (地基) ──┬─→ M2 (管理员模板)
            └─→ M3 (曲线对比) ──→ M4 (前端曲线)
                               ↑
                          M2 提供模板曲线数据
```

**建议节奏：**
1. **本周**：M1（数据模型，不依赖任何反馈，确定要做）+ 同步发第 1 条视频收数据
2. **下周**：M2（管理员上传）+ M3（对比逻辑）
3. **下下周**：M4（前端曲线，工作量大但不阻塞后端）

每个 M 独立可发布，不用等全部做完。

---

## 风险与决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 鉴权 | 复用 local_auth_service JWT | 基础设施已就绪，比环境变量密码安全，admin.html 可改造 |
| 曲线可见性 | 所有用户都能看 | 作为差异化卖点，不做付费门槛（早期要传播不要设墙） |
| 对齐算法 | 阶段对齐 + 重采样 | phase_detector 已切 4 段，几乎免费；DTW 过度工程 |
| 数据持久化 | 单独 `frame_data.json` 文件 | 避免主分析响应过大，前端按需 fetch |
| 模板元数据 | 只有 `name` | YAGNI，早期模板少，等涨到 20+ 再加 `shot_type` 等字段 |
| NBA 素材版权 | 早期小规模风险低，模板命名避免具体球员名 | 起量后再考虑授权或自录参考动作 |

---

## 验收总清单（v2 完成）

- [ ] M1：用户分析后 `results/{task_id}/frame_data.json` 存在，含每帧 6 关节角度
- [ ] M1：老功能（关键帧/协调性/PDF/导出）全不破
- [ ] M2：`/api/v1/templates/create` 需 admin token，非 admin 返回 403
- [ ] M2：管理员上传后模板目录有 `angles.json` + `phases.json`
- [ ] M2：老模板（无曲线数据）依然能被列出和用 4 点 diff 对比
- [ ] M3：用户选曲线模板分析，响应含 `curve_comparison`
- [ ] M3：曲线按阶段对齐（不是按时间硬比）
- [ ] M4：用户能看到自己 6 关节曲线图
- [ ] M4：模板对比能看双线叠加 + 差异高亮
- [ ] M4：移动端可读

---

## 不在本计划内（明确排除）

- 模板库批量导入 NBA 视频（先手动上传几个验证流程）
- 用户自定义模板保存（v3 再做，先把管理员侧跑通）
- 曲线数据存数据库（先文件系统，量大了再迁 Supabase）
- 付费/登录门槛（早期要传播）
- NBA 素材版权授权处理（早期小规模风险自担，起量后处理）
