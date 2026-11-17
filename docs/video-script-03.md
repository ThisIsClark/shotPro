# 第 3 条视频脚本 - Just Hooping（最新 SB7 重写版）

**总时长：** 15 秒 | **画幅：** 9:16 竖屏 | **语言：** 英文（视频内文字）| **工具：** CapCut（手机）

---

## 这条视频的核心

**概念：一条视频讲完整个最新 SB7 故事，用 V3 的"找回那一次"基调--从"那次感觉对了"起，到"找回那一次"终。**

这次重写对齐 `docs/landing-redesign.md` 的最新 SB7 顺序，和原版 V3 有三处根本区别：

- **Failure 提前到第二拍**：代价段紧接 Hero，不压在倒数第二。短视频里"不修的代价"比"问题陈述"更抓完播，先用"1000 次重复不是练习、是定型"钩住，再引向导。
- **新增 Proof 段**：原版 V3 没有"证据"独立段，直接 Plan -> Failure -> Success。最新 SB7 把曲线 + 角度差数字独立成 Proof（`The gap is real. And it's measurable.`），让"看不见的差距"被量化看见--这是 formrefine 的核心卖点，原版漏了。
- **Hero 融合 Character+Problem（feels right 双向）**：最新 brand.md 的 Hero 是双向命名--feels right（你拥有过那一次感觉对的）+ feels off（从那以后感觉不对）。V3 的暖->冷翻转正好做这一拍：`That one shot.` 暖色（feels right，黄金一投）-> 硬切 `But it feels off.` 冷色（feels off，又丢了）。比单向 feels off 更深--失去过比从没拥有过更痛。

**情绪弧线：** 纯粹享受（开）-> 痛点翻转 -> 越练越远的警告 -> AI 点破 -> 三步 -> 曲线量化证据 -> 修好后回归享受（收）。**首尾都是"享受篮球"，中间是脱节、代价与修复--V3 的灵魂不变，只是把代价提前、把证据补上。**

---

## 最新 SB7 七段映射

| 最新 SB7 段 | 时间 | 画面 | 文字 | 落地页对应 |
|--------|------|------|------|------------|
| 1. Hero 命名问题 | 0–2.5s | 暖色"那一次"投篮 -> 硬切冷色卡顿 | `That one shot.` / `But it feels off.` | brand.md Hero 双向 + landing.title |
| 2. Failure 代价 | 2.5–4.5s | 黑屏 + 计数器 1->100->1000 红字 | `1,000 reps with the same flaw isn't practice.` / `It's permanent.` | landing.failureTitle |
| 3. Guide 权威 | 4.5–6.5s | 投篮缩进 formrefine -> 关键帧+角度弹出 | `We see what your eyes can't.` | landing.guideAuthority |
| 4. Plan 三步 | 6.5–8s | 录->分析->修 三闪 | `Film. See. Fix.` | landing.planStep |
| 5. Proof 证据 | 8–10s | 角度曲线 + 23° 圈选 | `The gap is real.` / `And measurable.` | landing.curvesTitle |
| 6. Success 愿景 | 10–12.5s | 修复后流畅+连中（暖色） | `When the power flows, the shot goes.` -> `Just hooping.` | landing.successTitle + V3 peak |
| 7. CTA + Outro | 12.5–15s | 品牌卡 | tagline + formrefine.ai | brand.md 结尾卡 |

> **首尾呼应不变：** 0s 和 10s 都是"感觉对的投篮"（feels right），但 10s 那次是"修好后找回的那一次"--同一个动作，不同心境。Hero 点出"那一次感觉对了，又丢了"，Success 回到"找回了那一次"。

> **和原版 V3 的两处结构差：** ① Failure 从第 5 拍移到第 2 拍；② 新增 Proof 段（第 5 拍），原版这里直接是 Failure。

---

## 颜色映射（沿用产品 + 前两条）

| 谁/什么 | 颜色 | 色值 |
|--------|------|------|
| 你（user） | 黄 | `#feca57` |
| AI 诊断数据 | 蓝 | `#48dbfb` |
| 警告/代价 | 红 | `#ff6b6b` |
| 享受/成功 | 暖光（无强调色，自然色调） | - |

---

## 素材清单

### A. 投篮实拍（复用 v1 已拍素材，本条不重新拍）

v1 视频已产出的 Before/After 两段，直接就是本条要的两种状态：

- [ ] **享受版 = v1 After** -- 改进后更顺那段。0–1.5s Hero 开头用 + 10–12.5s Success 回归用（首尾同源）。
- [ ] **犹豫版 = v1 Before** -- "看着对、感觉不对"那段。1.5–2.5s Hero 翻转拍用（冷色卡顿）。
- [ ] **连中段 = v1 After 重复快剪** -- 没有独立连中素材，用 After 那段出手片段重复剪 3-4 次（每个 0.3s）模拟连中，配 swish×4。观众读作"连中"。

> **复用映射：** 犹豫版 = v1 Before（冷色、卡顿、感觉不对），享受版 = v1 After（暖色、流畅、改进后）。两段在 v1 里已经是同一个人、同一场景的对比，V3 直接拿来用，省掉重新拍摄。首尾呼应自动成立--开头用 After 暖色慢动作（享受），结尾用同一段 After 暖色正常速 + 重复快剪（修好后的享受），同一段两种处理区分心境。

### B. 从 formrefine.ai 截图（先跑一次分析）

- [ ] **关键帧 + 角度标注截图** -- Release 帧特写，带角度数字。4.5–6.5s Guide 段用。
- [ ] **角度曲线截图** -- **Proof 段核心证据**。曲线区截图：你的实线 + 球星虚线叠加（如有模板对比）或单条曲线带 release 帧标记。8–10s 用。
- [ ] **角度差数字** -- 从产品取差距最大的角度差值（如 release 差 23°）。Proof 段 9.5s 砸数字用。

> Proof 段是这次重写的新增核心--它把 Guide 段的"我看得见"量化成"差了多少度"。**没有曲线截图，这条视频的卖点就缺了一拍。** 一定要先跑一次分析拿到曲线。

### C. 品牌素材

- [ ] **formrefine.ai wordmark** -- 透明 PNG 或 CapCut 文字层。4.5–6.5s 水印 + 12.5–15s 结尾卡。
- [ ] **结尾卡 2.5s 片段** -- 复用第 1 条渲染好的 outro（tagline + wordmark），直接拼接。

### D. 音频

- [ ] **背景音乐** -- 两段情绪：开头/结尾用舒缓暖意（搜 "lofi basketball" / "warm"），中间 Failure/Proof 段用 hype 节奏（搜 "basketball" / "beat"）。或一条曲子做起伏。
- [ ] **转场音效** -- whoosh + tick + riser + chime（沿用前两条）。
- [ ] **计数器音效** -- 2.5–4.5s Failure 段用 ticking/计数声（搜 "clock tick" / "counter"），递增紧张感。
- [ ] **进球音** -- 10–12.5s Success 连中段的"唰"网声（搜 "swish" / "net"）。

---

## 完整分镜 + CapCut 操作步骤

### 0–2.5s | Hero - 命名问题（暖->冷翻转，feels right -> feels off 双向）

**起手式：先点亮"那一次感觉对的"，再翻转到"从那以后感觉不对"。这一拍同时承担 Character（你是谁）和 Problem（你丢了什么）。**

1. 新建项目，9:16
2. 主轨放 **"享受版"投篮**，0–1.5s
3. **变速** -> 0.5x（慢动作，突出"那次感觉对了"的体感）
4. **滤镜** -> 暖色类（"Warm" / "Sunset"），强度 ~50%
5. 文字层 `That one shot.` -- 白色，大号，居中下方；**淡入** 0.3s（0s 起）
   > 点出"那一次"--每个打球人都记得某次出手"感觉对了、球还没离手就知道会进"。这是 feels right 的钩子。
6. 1.2s 加一声轻 **swish** 网声（暗示球进了，那次感觉对了）
7. **1.5s 硬切**到 **"犹豫版"投篮**（不用转场，硬切制造落差）-- 这是翻转点
8. "犹豫版"**变速**正常速，出手瞬间（~2.0s）加 **0.3s freeze frame**（定格，表现"卡住"）
9. **滤镜**切**冷色类**（"Frost" / "Cool"），强度 ~60%（和前 1.5s 暖色对比）
10. 1.6s 文字层换成 `But it feels off.` -- 白色，中号，画面下方；"off" 一词用 **黄色 `#feca57`** 高亮
   > 翻转：从"那一次感觉对了"到"从那以后感觉不对"。feels right（你拥有过）-> feels off（你又丢了），双向对照比单向 feels off 更深--失去过比从没拥有过更痛。
11. 翻转瞬间（1.5s）加一声低沉 **thud** 或 **whoosh down**（下行音，挫败感）

> `That one shot.` -> `But it feels off.` 对齐 `docs/brand.md` 最新 Hero 双向命名：feels right（黄金一投，你拥有过又丢了）+ feels off（被卡住的日常）。`feels off` 取自落地页 Hero h1（`Your shot feels off.`）。V3 的暖->冷翻转让这一拍同时完成 Character（你记得那一次）和 Problem（但从那以后感觉不对）。

### 2.5–4.5s | Failure - 不修的代价（计数器 + 红字警告，提前到第二拍）

**这是最新 SB7 的核心动作：代价前置。不找对问题，越努力越远。**

1. 主轨 **黑屏**（纯黑背景），2.5–4.5s
2. **计数器动画**（关键帧或逐字）：
   - 2.5s：`1` -- 白色小字居中
   - 3.0s：`100` -- 白色中字
   - 3.5s：`1,000` -- 白色大字
   - 4.0s：`10,000` -- **红色 `#ff6b6b`** 超大字
   > 计数器代表"重复次数"，递增到红色时触发警告。
3. 计数器递增时配 **ticking 声**（越来越快，3.5s 后变急促）
4. 文字层（3.0s 起，**淡入**）：
   - 3.0s：`1,000 reps with the same flaw` -- 白色，中号，计数器上方
   - 3.7s：`isn't practice. It's permanent.` -- **红色 `#ff6b6b`**，中号加粗，紧接上一行
5. 4.0s 计数器变红时加一声 **低频 impact / boom**（警示音）

> 文案直接取自落地页 Failure 段（`1,000 reps with the same flaw isn't practice. It's permanent.`）。原版 V3 把这拍放在 7.5s，现在提前到 2.5s--让观众先感受到"不修的代价"，再引出向导，钩子更狠。

### 4.5–6.5s | Guide - AI 点破关键（权威登场）

**向导登场：投篮缩进 formrefine，AI 找到你眼睛看不见的缺陷。**

1. 4.5s 处，黑屏淡出 / 硬切到 **"犹豫版"投篮**做**画中画缩小**：scale 100% -> 30%，往中心收，**交叉溶解**到 **formrefine 关键帧截图**
2. 4.5s **whoosh**（片段被吸走）+ 5.0s **tick**（落进工具）+ 5.3s **riser**（分析中）
3. 主轨 = **Release 关键帧 + 角度标注**，5.0–6.5s
4. **入场** -> **上滑**
5. 文字层：
   - 5.2s `We see what` -- 蓝色 `#48dbfb`，中号，画面上方
   - 5.7s `your eyes can't.` -- 白色，中号，紧接上一行下方
   - 6.2s 角度数字弹出（如 `23° at release`）-- 黄色 `#feca57` 大字，**放大弹出**
6. **常驻水印** `formrefine.ai` 右上角，透明度 70%，4.5–6.5s
7. 6.3s **chime**（结果出现）

> 文案取自落地页 Guide 权威侧（`We see what your eyes can't. Frame by frame. Degree by degree.`）。共情侧（"你也经历过那一次"）已经在 Hero 段的 feels right 里完成了，这里只打权威--视频里权威比共情更上镜。

### 6.5–8s | Plan - 三步快闪

**计划段要快，1.5s 三步，每步 0.5s。**

1. 三段快剪，每段 0.5s：
   - 6.5–7.0s：**录** -- 手机拍摄投篮的画面 + 文字 `Film.`
   - 7.0–7.5s：**分析** -- 关键帧截图快闪 + 文字 `See.`
   - 7.5–8.0s：**修** -- "享受版"投篮一闪 + 文字 `Fix.`
2. 文字 `Film. / See. / Fix.` -- 白色大字，每段居中，**逐字弹出**
3. 每步切换加一声 **tick**
4. 配乐此处节奏加快（hype 段开始）

> 三步动词取自落地页 Plan（`Film one shot -> See what your eyes miss -> Fix the gap`）。原版 V3 用 `Record. Find. Fix.`，这次对齐落地页改成 `Film. See. Fix.`。

### 8–10s | Proof - 证据拍（新增核心段）

**这是重写新增的段：把"看不见的差距"量化成曲线和度数。呼应 tagline `you can't see`。**

1. 主轨 = **角度曲线截图**，8–10s
2. **入场** -> **淡入** 0.3s
3. 文字层逐行（每行单独文字轨道，**淡入**，间隔 0.4s）：
   - 8.2s：`The gap is real.` -- 白色，中号，画面上方
   - 8.7s：`And it's measurable.` -- 白色，中号，紧接上一行
4. 9.2s 用 **关键帧** 给差异最大的曲线段做高亮：加圈选贴纸（**贴纸** -> 搜 "circle" 或形状->椭圆->描边无填充->黄色 `#feca57`），圈在 release 帧曲线峰值处
5. 9.5s 文字 `23° at release.` -- 黄色 `#feca57` 大字，压在圈选位置，**放大弹出**
   > `23°` 是占位示例，用你实际 release 帧的角度差替换。选差距最大的那个关节。
6. 9.8s 全图恢复亮度，文字淡出，让位给 Success

> 文案取自落地页 Proof 段（`The gap is real. And it's measurable.`）。**原版 V3 跳过了这一拍**，直接 Plan -> Failure -> Success--结果"看不见的差距"只是嘴上说了，没让观众看见。这拍补上后，Guide 的"我看得见"才有了证据闭环。

### 10–12.5s | Success - 回归本能享受（首尾呼应 + 落地页愿景句）

**情绪反转：修好后的享受，回到开头"那一次"的状态，但带自信。首尾呼应--Hero 点出"那一次感觉对的"，Success 回到"找回了那一次"。**

1. 10s **硬切**到 **"享受版"投篮**（和 0s 同一段或同类素材）+ **连中快剪**
   - 10.0–11.0s：流畅出手（暖色，正常速）
   - 11.0–12.0s：连中 3-4 个进球快剪（每个 0.3s），配 **swish swish swish** 网声
2. **滤镜** -> 暖色（和开头一致，呼应）
3. 文字层（接力出现）：
   - 10.1s `When the power flows,` -- 白色，大号，居中
   - 10.5s `the shot goes.` -- 白色，大号，替换/紧接上一行
   - 11.6s `Just hooping.` -- **黄色 `#feca57`**，超大号加粗，**放大弹出**（情绪顶点）
   > 前两句是落地页 Success 愿景（`When the power flows, the shot goes.`），最后一句是 V3 的灵魂落点（`Just hooping.`）--愿景说完，落到体感。`Just hooping.` 同时是 Hero"那一次感觉对了"的回归：你终于找回了那次感觉，不用想，just hoop。
4. 12.0s 起 **淡出** 0.5s，让位给 outro
5. 配乐此处回归舒缓（和开头呼应），swish 声略高于 BGM

### 12.5–15s | CTA + Outro（复用品牌卡）

**直接复用第 1 条渲染好的 2.5s outro 片段拼接。** 完整 SOP 见 `docs/brand.md`。

- 12.5–13.7s Screen 1：tagline `Feel the difference you can't see.`
- 13.7–15.0s Screen 2：wordmark `formrefine.ai` + 下划线动画
- chime 落在 wordmark 出现，BGM 14.5s 淡出

> 这条正文压到 12.5s，outro 用标准 2.5s（12.5–15s），和第 1 条结尾卡时间完全对齐，拼接最干净。

### 配乐

1. **音频** -> **音乐** -> 选一条有情绪起伏的（或两条拼接：开头/结尾暖意 lofi + 中间 hype beat）
2. 音量 30–40%
3. 0s 和 15s 各加 0.5s **淡入/淡出**
4. 转场音效（whoosh/tick/riser/chime）放在 4.5–5s 拍上，音量略高于 BGM
5. 计数器 ticking（2.5–4.5s）音量适中，递增
6. 连中 swish 声（11.0–12.0s）略高于 BGM

### 导出

右上角 **导出** -> **1080p** -> 保存到相册。

---

## 发布文案（对照 `docs/publishing.md`）

### TikTok caption（前 80 字符关键）

```
1,000 reps with the same flaw isn't practice. It's permanent 🏀 formrefine.ai #basketball #shootingform #formrefine
```

或更短：
```
1,000 reps. Same flaw. That's not practice 🏀 #basketball #shootingform formrefine.ai
```

> 别重复视频 0s 的 `That one shot.`，caption 用 Failure 段的代价句做钩子--这是这次重写把 Failure 提前后的最强钩子位。

### Instagram Reels caption

```
1,000 reps with the same flaw isn't practice - it's permanent 🏀
formrefine.ai - 2 free analyses
See the gap. Fix it. Just hoop.
Link in bio 🔗 #basketball #shootingform #basketballtraining
```

### YouTube Shorts title + description

**Title：**
```
1,000 reps with the same flaw isn't practice. It's permanent. (AI form analysis)
```

**Description：**
```
Free shot analysis (2 free analyses) -> https://formrefine.ai

You know that one shot. The one that felt right. But your shot feels off now. 1,000 reps with the same flaw isn't practice - it's permanent. formrefine.ai sees what your eyes can't, measures the gap, and shows you the one fix. When the power flows, the shot goes. Just hoop.

#basketball #shootingform #basketballtraining #shorts
```

---

## 为什么这条和前两条不冲突

| | 第 1 条（V1 已拍）| 第 2 条（V3 本条）|
|--|--------|--------|
| 基调 | 诊断（对抗感）| **找回那一次（自我实现）** |
| SB7 顺序 | Problem + Guide 部分 | **最新落地页顺序：Hero->Failure->Guide->Plan->Proof->Success** |
| 钩子 | "Your shot feels off." | **暖->冷翻转 + "It's permanent."**（Failure 提前）|
| 证据 | ⚠️ 发力脱节卡 | **角度曲线 + 23°（独立 Proof 段）** |
| 情绪 | 疼 + 释然 | **享受->代价->警告->证据->享受** |
| 收束 | "Same power. Better timing." | **"When the power flows... Just hooping."** |
| 触发分享 | "我也有这问题" | **"我也想投成这样、享受篮球"** |

**两条是两种说服路径。** 这条是 V3 的完整视频化，且对齐了最新落地页 SB7--用户从视频进来，看到落地页是同一套叙事（同样的 `feels off` / `It's permanent` / `We see what your eyes can't` / `Film. See. Fix.` / `The gap is real` / `When the power flows`），转化路径一致。

---

## V3 叙事一致性检查（对齐最新落地页）

这条视频的每段文案都对应最新落地页 SB7：

| 视频 | 落地页对应段 + key |
|------|------------|
| `That one shot.` / `But it feels off.` | Hero 双向 - `brand.md` feels right/off + `landing.title` |
| `1,000 reps with the same flaw isn't practice. It's permanent.` | Failure - `landing.failureTitle` / `landing.failureDesc` |
| `We see what your eyes can't.` | Guide - `landing.guideAuthority` |
| `Film. See. Fix.` | Plan - `landing.planStep1-3` |
| `The gap is real. And it's measurable.` + `23° at release` | Proof - `landing.curvesTitle` / `landing.curvesSubtitle` |
| `When the power flows, the shot goes.` + `Just hooping.` | Success - `landing.successTitle` |
| outro tagline | 品牌卡 - `brand.md` |

**视频和落地页是同一个最新 SB7 故事的不同载体。** 这是这次重写的核心目的--让 V3 旗舰视频和最新落地页完全咬合。

---

## 拍摄难点 & 简化建议

1. **首尾呼应已解决**：复用 v1 Before/After，两段本就是同一个人的对比，无需重拍。开头用 v1 After 暖色慢动作（享受），结尾用同一段 After 暖色正常速 + 重复快剪模拟连中（修好后的享受）。唯一要做的区分是调色和变速，不是再拍素材。

2. **计数器动画**：CapCut 做递增数字较麻烦。简化：直接四个文字层（1 / 100 / 1,000 / 10,000）按时序**淡入淡出**替换，不做平滑递增，效果接近且省时。

3. **Proof 段曲线截图**：如果产品曲线区截图太复杂，简化：直接截一张带角度差数字的关键帧对比图（你 vs 球星并排 + `23°`），文字 `The gap is real.` 压上，省掉圈选动画。**但别整段砍掉**--Proof 是这次重写的新增核心，砍了就和原版 V3 没区别。

4. **两段配乐**：如果一条曲子难做情绪起伏，简化用一条 hype beat 全程，开头/结尾靠 swish 声和调色传达"享受"，不靠音乐暖意。

5. **时间紧张**：七段塞 12.5s 很紧。如果某段拍不下来，**最先砍 Plan 段**（6.5–8s 压到 1s，`Film. See. Fix.` 一闪而过）--因为 Plan 在短视频里最不扛情绪，Failure/Proof/Success 才是这条的核心。**别砍 Failure 或 Proof**，这俩是相对原版 V3 的升级点。
