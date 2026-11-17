# V5 实拍版脚本 - Me vs Curry（基于真实素材）

**使用素材：**
- 你的投篮视频：`/Users/clark/Code/shotImprovement/modelVideo/myshotform.mp4`
- 库里投篮视频：`/Users/clark/Downloads/文章素材/投篮/curry.mp4`
- 5 张阶段对比图：`/Users/clark/Documents/文章素材/投篮/投篮对比/`
  - Deep Squat
  - Dip Point
  - Elbow Tuck
  - Hand Rise
  - Max Hold Point

**总时长：** 25–35 秒\
**画幅：** 9:16 竖屏\
**语言：** 英文字幕 + on-screen text\
**形式：** 实拍视频 + 关键帧对比图 + 2–3 秒录屏点缀\
**目标：** 建立"这球进了但和库里差距可量化"的渴望，引导用户体验模板对比

---

## SB7 逻辑对应

| SB7 要素 | 本视频如何表达 |
|---------|---------------|
| **Hero（渴望）** | 想要库里那种无解的投篮 |
| **Problem（问题）** | 这球进了，但感觉不对，和库里差在哪？ |
| **Guide（引导者）** | formrefine 把差距变成具体角度数字 |
| **Plan（计划）** | 上传视频 → 选库里模板 → 看每一阶段的 gap |
| **CTA（行动召唤）** | formrefine.ai |
| **Avoid Failure（避免失败）** | 不再靠猜，知道具体差在哪 |
| **Success（成功）** | Shoot like Curry. Take over your league. |

---

## 分镜脚本

| 时间 | 画面 | 字幕 / On-screen text | 说明 |
|------|------|----------------------|------|
| 0:00–0:03 | `myshotform.mp4` 进球瞬间 | This went in. | 建立熟悉感：你也能进球 |
| 0:03–0:05 | 球进网后定格 2 秒（你自然站立的画面）；库里画面从画面中心淡入叠上（半透明 ~50% + 高斯模糊） | （留白） | 转场：进了但感觉不对 → 脑中浮现库里 |
| 0:05–0:08 | 库里画面变清晰、放大成主画面 | Now picture Curry's. | 从想象落到现实 |
| 0:08–0:11 | 库里清晰画面定格 | Want that shot? The kind nobody can guard? | Hook：渴望 |
| 0:11–0:15 | **Max Hold Point** 对比图（左右 split screen，裁切/放大到充满竖屏） | See the exact gap. | 核心视觉钩子，用最具冲击力的单帧 |
| 0:15–0:19 | 同一画面，肘部角度数字弹出 | Your elbow: 100° / Curry: 58° | 具体数据，来自 Max Hold 图底部表格 |
| 0:19–0:24 | 5 张阶段对比图快速闪过（Deep Squat → Dip Point → Elbow Tuck → Hand Rise → Max Hold） | The gap is real. And measurable. | 证明不是只比一帧，而是每个阶段都量化 |
| 0:24–0:27 | 2–3 秒录屏：选 Curry 模板 → 对比结果出现 | Pick a star. See your gap. | 证明这是真功能 |
| 0:27–0:32 | 结尾品牌卡 | Shoot like Curry. Take over your league. formrefine.ai | CTA |

---

## 视觉细节

### 1. 开场 3 秒视频怎么变 5 秒

你的 `myshotform.mp4` 大约 3 秒，需要让最后一帧多停留 2 秒给库里浮现做转场：

1. 把视频放进主轨
2. 拖到**球进网后、你自然站立的那一秒**
3. 点「定格」，生成一个静帧片段
4. 把静帧缩到 **2 秒**
5. 最终结构：`[投篮 3 秒] + [定格 2 秒] = 5 秒`

> 如果你的原视频球进网后本来就有 1–2 秒你站着的画面，也可以不用定格，直接保留原视频。定格是保底方案。

### 2. 库里浮现转场（本片记忆点）

- 用 `curry.mp4` 叠在主轨上方，库里层**居中**
- 0:03 起点：opacity 0%，高斯模糊强
- 0:05：opacity 50%，模糊中等
- 0:05–0:08：opacity 100%，模糊归零，scale 1.0→1.2 占满屏
- 加 whoosh + reverb 音效
- 这 2 秒不加字幕

### 3. Max Hold Point 对比图怎么用

这张图是**横屏截图**，不能直接放进 9:16 竖屏（会很小、两边黑边）。处理方式：

- **方法 A（推荐）**：把整张对比图作为背景，上下加模糊/黑色遮罩，中间只突出 split screen 区域
- **方法 B**：放大到只看 split screen 区域（Your Shot + Curry），让两个投篮动作充满画面
- **方法 C**：左右分屏单独裁剪"Your Shot"和"Curry"两张图，重新拼成适合竖屏的上下或左右布局

建议用 **方法 B**：把 Max Hold 图放大，让左右两个投篮人物占满竖屏画面，底部角度表格仍可见但占小比例。

### 4. 5 张对比图快速闪过

0:19–0:24 共 5 秒，5 张图每张显示约 0.8–1 秒：

1. Deep Squat（0:19）
2. Dip Point（0:20）
3. Elbow Tuck（0:21）
4. Hand Rise（0:22）
5. Max Hold（0:23）

每张图之间用快速叠化或硬切，营造"数据扑面"的节奏感。每张图同样要放大到能看清 split screen 动作。

### 5. 角度数字弹出

- 颜色：你的数字黄色 `#feca57`，库里数字蓝色 `#48dbfb`
- 动画：放大弹入，错开 0.3 秒
- 用 Max Hold 图里的真实数据：`Your elbow: 100° / Curry: 58°`
- 也可以换成 `Shoulder: 114° / Curry: 77°`，看你更想突出哪个差距

### 6. 录屏点缀

- 只保留"下拉选 Curry 模板 → 对比结果出现"那 2 秒
- 不要上传、等待、分析过程

---

## 字幕脚本（按画面事件）

| 画面事件 | 英文字幕 |
|---------|---------|
| 你的 raw shot | This went in. |
| 库里浮现（转场） | （留白） |
| 库里画面变清晰 | Now picture Curry's. |
| Hook | Want that shot? The kind nobody can guard? |
| Max Hold split screen | See the exact gap. |
| 角度数字弹出 | Your elbow: 100° / Curry: 58° |
| 5 张对比图闪过 | The gap is real. And measurable. |
| 短录屏 | Pick a star. See your gap. |
| 结尾卡 | Shoot like Curry. Take over your league. formrefine.ai |

---

## 发布文案

### TikTok
```
This went in. But Curry's shot is a different world.

formrefine.ai showed me the exact gap — frame by frame.

#basketball #shootingform #curry #basketballtraining #formrefine
```

### Instagram Reels
```
This shot went in. But it didn't feel like Curry's.

formrefine.ai put my Max Hold next to Curry's and showed me the elbow gap: 100° vs 58°.

It wasn't "you're bad." It was "here's exactly where to fix."

🔗 Link in bio

#basketball #hoops #shootingform #curry #basketballtraining #formrefine
```

### YouTube Shorts
- **Title:** `I compared my shot to Steph Curry. The gap was bigger than I thought.`
- **Description 第一行：** `Compare your shot → formrefine.ai`

---

## 封面建议

用 **Max Hold Point 对比图** 做封面：
- 把左右 split screen 裁剪放大
- 两个投篮动作占满画面
- 中间大字：**Me vs Curry**
- 小字点缀：**Elbow 100° vs 58°**

这是这个视频里最抓眼的画面。

---

## CapCut 制作要点（简化版）

1. **新建工程** → 9:16 → 导入 `myshotform.mp4` 放主轨
2. **定格补时长**：球进网后定格 2 秒，让总长变成 5 秒
3. **库里浮现**：画中画导入 `curry.mp4`，居中，打关键帧：opacity 0→50%→100%，模糊强→中→0，scale 1.0→1.2
4. **定格 hook**：库里最帅那一帧定格，缓慢 zoom 1.0→1.1
5. **split screen**：导入 Max Hold 对比图，放大到左右两个动作充满画面
6. **角度数字**：黄色/蓝色，放大弹入，用真实数值
7. **5 图闪过**：0.8–1 秒/张，硬切或叠化
8. **录屏**：2 秒高光
9. **outro 卡**：formrefine.ai 统一结尾

---

## 可选的更强版本（如果你愿意重拍一个镜头）

如果你愿意补拍一个镜头，可以让情绪更到位：

- 让投篮者（小孩）投完球后**不庆祝**，而是皱眉/轻轻摇头/眼神放空 2 秒
- 这样库里浮现就不是"画面定格"而是"真实情绪转场"，比定格更有感染力

如果懒得补拍，用定格方案完全够用。

---

## 繁體 CapCut 操作對照（按本腳本操作）

你的 CapCut 是繁體介面，以下是文檔裡所有操作術語的繁體對照，以及直接用繁體術語寫一遍關鍵步驟，你剪輯時對著做就行。

### 術語對照表

| 文檔（簡體） | 你的 CapCut（繁體） |
|-------------|-------------------|
| 定格 | 定格 |
| 画中画 | 畫中畫 |
| 新增画中画 | 新增畫中畫 |
| 主轨 | 主軌道 |
| 不透明度 | 不透明度 |
| 关键帧（菱形图标） | 關鍵影格（菱形圖示） |
| 特效 -> 画面特效 -> 基础 -> 模糊 | 特效 -> 畫面特效 -> 基礎 -> 模糊 |
| 作用对象 | 作用對象 |
| 光效 -> 光晕 | 光效 -> 光暈 |
| 音频 -> 音效 | 音訊 -> 音效 |
| 变速 | 變速 |
| 文字 -> 新建文本 | 文字 -> 新增文字 |
| 动画 -> 入场 -> 放大弹入 | 動畫 -> 入場 -> 放大彈入 |
| 贴纸 | 貼紙 |
| 比例 | 比例 |
| 背景 | 背景 |
| 分割 | 分割 |
| 导出 | 匯出 |
| 音乐 | 音樂 |

### 分鏡繁體操作步驟

**0:00–0:03 球進框**

1. 開啟 CapCut ->「新增專案」-> 匯入 `myshotform.mp4` 放主軌道
2. 把時間軸拖到起跳前，點「分割」，刪掉前面
3. 拖到球進網後約 1 秒，點「分割」，刪掉後面，保留約 3 秒
4. 保留原聲（球進網唰聲，不要靜音）
5.「文字」->「新增文字」-> 輸入 `This went in.`，樣式選白色無襯線，放畫面下 1/3

**0:03–0:05 定格補時長（讓影片從 3 秒變 5 秒）**

1. 拖時間軸到球進網後、你自然站立的那一幀
2. 點主軌道影片 -> 底部選單滑到「定格」，點一下
3. CapCut 會插入一個靜幀片段，預設約 3 秒
4. 點選那個定格片段，拖右邊緣縮到 **2 秒**
5. 最終：`[投籃 3 秒] + [定格 2 秒] = 5 秒`

**0:03–0:05 感覺不對浮現 Curry（本片記憶點）**

1. 0:03 起就是定格那 2 秒畫面
2.「畫中畫」->「新增畫中畫」-> 匯入 `curry.mp4`，疊在主畫面上方，**置中**放置
3. 點選 Curry 層，點底部「菱形」關鍵影格圖示：
   - 在 0:03 起點打關鍵影格，「不透明度」設 **0%**
   - 拖到 0:05，「不透明度」設 **50%**
4. 給 Curry 層加模糊：「特效」->「畫面特效」->「基礎」->「模糊」，加好後點「作用對象」選 Curry 層，強度約 30–40
5. 加柔光：「特效」->「畫面特效」->「光效」->「光暈」，作用對象選 Curry 層
6. 音效：「音訊」->「音效」-> 搜 `whoosh`，拖到 0:03 起點；再疊一個 `reverb` 空靈感
7. 這 2 秒**不加字幕**

**0:05–0:08 Curry 變清晰放大**

1. 延續上一段 Curry 層，繼續打關鍵影格：
   - 不透明度：0:05 處 50% -> 0:08 處 **100%**
   - 模糊強度：0:05 處 30 -> 0:08 處 **0**（選模糊特效層打關鍵影格調強度）
   - 縮放 scale：0:05 處 1.0 -> 0:08 處 **1.2**
2. 加文字 `Now picture Curry's.`，在變清晰過程中出現

**0:08–0:11 Curry 定格 Hook**

1. 拖到 Curry 最帥的投籃姿勢那一幀，點「定格」，刪掉定格前後多餘
2. 給靜幀加緩慢 zoom：起點關鍵影格 scale 1.0，結尾 1.1
3. 文字 `Want that shot? The kind nobody can guard?`

**0:11–0:15 Split Screen（Max Hold Point 對比圖）**

1. 主軌放一張黑底（純色）4 秒
2.「畫中畫」匯入 Max Hold 對比圖，雙指放大到左右兩個投籃動作充滿畫面
3. 文字 `See the exact gap.`，放在畫面上方 1/3

**0:15–0:19 角度數字彈出**

1.「文字」->「新增文字」：左下輸入 `100°`，顏色黃 `#feca57`；右下輸入 `58°`，顏色藍 `#48dbfb`
2. 點選文字 ->「動畫」->「入場」選「放大彈入」，時長 0.5 秒。你的數字先出，Curry 數字錯開 0.3 秒後出
3. 頂部加一行 `Your elbow: 100° / Curry: 58°`

**0:19–0:24 5 張對比圖快速閃過**

1. 依序匯入 5 張對比圖，每張約 0.8–1 秒
2. 每張都雙指放大到 split screen 區域充滿畫面
3. 圖與圖之間用硬切或快速疊化
4. 文字 `The gap is real. And measurable.`

**0:24–0:27 錄屏**

1. 匯入錄屏，「分割」只留「點 Curry 模板 -> 對比結果出現」那 2 秒
2.「變速」-> **1.5x**
3. 文字 `Pick a star. See your gap.`

**0:27–0:32 Outro 卡**

1. 匯入 outro 卡，5 秒
2. 文字 `Shoot like Curry. Take over your league. formrefine.ai`

### 全局收尾（繁體）

- **配樂**：「音訊」->「音樂」搜 `lofi hiphop instrumental`，音量調到 **-8dB**
- **音效統一**：轉場浮現處固定用 whoosh + reverb
- **節奏檢查**：每 2–4 秒一個畫面變化，別讓任何畫面停超過 4 秒
- **匯出**：1080P、30fps、9:16
