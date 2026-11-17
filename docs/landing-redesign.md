# formrefine.ai 落地页重设计 — 基于 SB7 框架

**设计原则：** 顾客是英雄，品牌是向导。落地页的每一屏都在推进同一个故事：英雄遇到问题 → 向导出现 → 给出计划 → 召唤行动。

---

## 现状诊断

当前落地页的问题（对照 SB7）：

| SB7 元素 | 现状 | 问题 |
|----------|------|------|
| Character | "两分随便投，一到三分线外就 Air Ball？" | ❌ 描述的是新手，不是卡在瓶颈的认真练球者 |
| Problem | "AI 分析你的手腿协调性" | ❌ 这是产品功能，不是用户的问题 |
| Guide | 缺 | ❌ 没有共情，直接跳到功能 |
| Plan | 缺 | ❌ 用户不知道流程是什么 |
| CTA | "上传视频，免费检测一次" | ⚠️ 有 CTA 但偏功能描述，不是故事推进 |
| Failure | 缺 | ❌ 没有说"不修会怎样" |
| Success | "力链贯通 = 远投轻松" | ⚠️ 有但埋在 feature 卡片里，不够突出 |

**核心问题：** 当前落地页是"功能清单"思维——列了产品能做什么，但没有讲故事。用户看到的是"AI 分析协调性"，不是"我懂你的挫败，我能帮你"。

---

## 新落地页结构（SB7 顺序）

```
┌─────────────────────────────────────────┐
│ 1. HERO — 命名问题（内部 + 哲学）        │  ← "It feels off."
│    + 直接 CTA                            │
├─────────────────────────────────────────┤
│ 2. FAILURE — 不修的代价                  │  ← "1000 reps with the same flaw..."
├─────────────────────────────────────────┤
│ 3. GUIDE — 共情 + 权威                   │  ← "We see what your eyes can't."
├─────────────────────────────────────────┤
│ 4. PLAN — 三步计划                       │  ← Film → See → Fix
├─────────────────────────────────────────┤
│ 5. PROOF — 产品证据（曲线 demo + 检测示例）│  ← 可视化"看不见的差距"
├─────────────────────────────────────────┤
│ 6. SUCCESS — 成功愿景                    │  ← "When the power flows..."
│    + 直接 CTA                            │
├─────────────────────────────────────────┤
│ 7. GUIDE SECTION — 拍摄指南              │  ← 降低行动门槛（过渡 CTA）
├─────────────────────────────────────────┤
│ 8. PRICING                              │  ← 转化
└─────────────────────────────────────────┘
```

**和当前页面的关键区别：**
- Hero 从"功能描述"改为"命名问题"
- 新增 Failure 段（当前完全没有）
- 新增 Guide 段（共情 + 权威，当前直接跳功能）
- 新增 Plan 段（三步，当前没有显性计划）
- Proof 段保留但重新定位为"证据"而非"功能展示"
- Success 段从 feature 卡片里提取出来，独立成段

---

## 逐屏文案设计

### 1. HERO — 命名问题

**SB7 角色：** 让英雄说"对，这就是我"。

**当前：**
```
h1: 两分随便投，一到三分线外就 Air Ball？不是力量不够，是发力不够连贯。
p:  AI 分析你的手腿协调性，检测手脚同步问题 & 发力脱节，给出精准改进建议
```

**改为：**

```
h1: Your shot feels off.
p:  You've put in the reps. You know something's wrong. You just can't see it.
CTA: See your gap →
Benefits: 2 free · Free to try · 30 seconds
```

**中文版：**
```
h1: 投篮感觉不对。
p:  你练了那么多。你知道哪里有问题。你只是看不见。
CTA: 看到你的差距 →
Benefits: 2 次免费 · 免费试用 · 30 秒出结果
```

**为什么这样改：**
- "feels off" 直接命名内部问题——所有打过球的人都有这个体感
- "You've put in the reps" 是共情——肯定用户的努力，不是"你不行"
- "You just can't see it" 是哲学层——不是你的错，是眼睛的局限
- CTA "See your gap" 是过渡 CTA——不是"上传视频"（功能），而是"看到差距"（结果）
- Benefits 从"检测你最不知道的问题"改为"2 free · Free to try · 30 seconds"——降低行动门槛的三个事实

### 2. FAILURE — 不修的代价

**SB7 角色：** 温和的紧迫感。不恐吓，但让用户意识到"不行动有成本"。

**新增段，当前页面没有。**

```
h2: 1,000 reps with the same flaw isn't practice.
p:  It's permanent. Every shot without fixing the gap cements the wrong pattern deeper. You can't fix what you can't see.
```

**中文版：**
```
h2: 带着同一个缺陷练 1000 次，不是练习。
p:  是定型。每一次没修的出手，都在加深错误的肌肉记忆。你看不见，就修不了。
```

**设计：** 深色背景，大字，简洁。可以加一个计数器动画（1... 100... 1000...）增强冲击感。不需要图片，文字本身就是证据。

### 3. GUIDE — 共情 + 权威

**SB7 角色：** 让用户信任你。先共情（我懂你），再权威（我能帮你）。

**新增段，当前页面没有。**

```
共情侧：
  "You've felt it. The shot that looks fine but doesn't feel right.
   The power that should be there but isn't.
   We've been there too."

权威侧：
  "We see what your eyes can't.
   Frame by frame. Degree by degree.
   Every joint, every phase, every timing gap — measured and mapped."
```

**中文版：**
```
共情侧：
  "你感受过。那个看着对但感觉不对的出手。
   那个应该有力量但就是没有的瞬间。
   我们也经历过。"

权威侧：
  "我们看到你眼睛看不到的。
   逐帧。逐度。
   每个关节、每个阶段、每个时序差距——测量、映射。"
```

**设计：** 两栏布局。左栏共情（暖色调，用户视角），右栏权威（冷色调，技术视角）。中间一条竖线分隔。或者上下排列，先共情后权威。

### 4. PLAN — 三步计划

**SB7 角色：** 降低决策焦虑。让用户觉得"这很简单，我能做"。

**新增段，当前页面没有。**

```
h2: 3 steps to a better shot.

Step 1: 🎬 Film one shot
        One video, side angle, any phone.

Step 2: 👁️ See what your eyes miss
        Every joint angle mapped. Every timing gap measured.
        Compared to pro templates if you want.

        ┌─────────────────────────────────────────────┐
        │  [你的 Release 帧]  ←→  [球星 Release 帧]   │  ← 关键帧并排对比
        │       23° apart                              │  ← 角度差数字
        ├─────────────────────────────────────────────┤
        │  ╱╲    ╱╲                                   │
        │ ╱  ╲  ╱  ╲   ─ ─ ─ ─ ─ ─ ─                 │  ← 角度曲线叠加
        │╱    ╲╱    ╲  (your ── template - -)          │     (你的实线 + 球星虚线)
        └─────────────────────────────────────────────┘

Step 3: 🔧 Fix the gap
        Know exactly what to change. Then make more.
```

**中文版：**
```
h2: 三步，更好的投篮。

Step 1: 🎬 拍一个投篮
        一段视频，侧面角度，任何手机。

Step 2: 👁️ 看到眼睛看不到的
        每个关节角度映射。每个时序差距测量。
        可选球星模板对比。

        ┌─────────────────────────────────────────────┐
        │  [你的出手帧]  ←→  [球星出手帧]             │  ← 关键帧并排对比
        │       差 23°                                │  ← 角度差数字
        ├─────────────────────────────────────────────┤
        │  ╱╲    ╱╲                                   │
        │ ╱  ╲  ╱  ╲   ─ ─ ─ ─ ─ ─ ─                 │  ← 角度曲线叠加
        │╱    ╲╱    ╲  (你 ── 球星 - -)               │
        └─────────────────────────────────────────────┘

Step 3: 🔧 修掉差距
        精确知道该改什么。然后投进更多。
```

**设计：** 三步横向排列，每步一个图标 + 标题 + 一行描述。Step 2 下方嵌入**真实对比效果图**——1-2 个差距最大的关键帧并排 + 1 张角度曲线叠加图。每步之间用箭头或线条连接，强调"路径感"。

**对比效果图的实现：**

- **默认状态（未分析时）：** 显示一组预设的 demo 对比图（用产品截图或静态 demo 图片），标注 "Example result"
- **分析后状态：** 替换为用户真实分析结果——从 `template_comparison.comparisons` 中取差距最大的 1-2 个关键帧并排图 + `curve_comparison` 的角度曲线图
- **数据来源：** 分析完成后，前端 JS 从 `currentTaskId` 的结果中提取对比数据，动态渲染到 Plan Step 2 的预览区域
- **关键帧选择：** 取 `angle_diffs` 中差异最大的阶段（通常是 release_frame），展示该阶段的并排对比
- **曲线图：** 复用产品内已有的 d3 曲线组件，缩小版渲染在预览区域

**HTML 结构：**

```html
<div class="plan-step-preview" id="planStep2Preview">
    <!-- 默认 demo 状态 -->
    <div class="preview-demo" id="previewDemo">
        <div class="preview-keyframes">
            <div class="preview-kf-pair">
                <img src="/static/demo_release_user.jpg" alt="Your form">
                <span class="preview-vs">vs</span>
                <img src="/static/demo_release_template.jpg" alt="Pro form">
            </div>
            <div class="preview-angle-diff">23° apart at release</div>
        </div>
        <div class="preview-curve">
            <svg id="previewCurveSvg"></svg>
        </div>
        <div class="preview-label">Example result</div>
    </div>
    <!-- 真实结果状态（分析后 JS 动态填充） -->
    <div class="preview-real" id="previewReal" style="display: none;">
        <div class="preview-keyframes" id="previewRealKeyframes">
            <!-- JS 动态填充 -->
        </div>
        <div class="preview-curve" id="previewRealCurve">
            <svg id="previewRealCurveSvg"></svg>
        </div>
    </div>
</div>
```

### 5. PROOF — 产品证据

**SB7 角色：** 证明向导的权威。不是"功能展示"，是"证据"。

**保留当前页面的 curves demo + 检测示例，但重新定位文案。**

**当前 curves demo：**
```
h2: Your shot, quantified.
p:  See the angles your eyes can't. Every frame of your shooting motion becomes a curve...
```

**改为：**
```
h2: The gap is real. And it's measurable.
p:  Your eyes see a shot. We see 6 joint angles across 8 keyframes — the timing, the breaks, the invisible gaps that decide whether the ball goes in.
```

**中文版：**
```
h2: 差距是真实的。而且可测量。
p:  你的眼睛看到一个投篮。我们看到 8 个关键帧的 6 个关节角度——时序、断点、决定进球与否的看不见的差距。
```

**当前检测示例段：** 保留，但标题从"发力连贯性检测示例"改为更故事化的：

```
h2: What we found in one shot
```

### 6. SUCCESS — 成功愿景

**SB7 角色：** 描绘成功后的世界。不是"产品能做什么"，是"你修掉差距后会怎样"。

**当前：** 成功愿景埋在 feature 卡片"力链贯通 = 远投轻松"里，不够突出。

**改为独立段：**

```
h2: When the power flows, the shot goes.
p:  Not luck. Not more reps. Just one gap found and fixed.
    That's the difference between "feels off" and "swish."
CTA: Find your gap →
```

**中文版：**
```
h2: 发力通了，球就进了。
p:  不是运气。不是更多练习。只是一个差距被找到、被修掉。
    这就是"感觉不对"和"空心入网"的区别。
CTA: 找到你的差距 →
```

**设计：** 可以用一张"球进框"的图或动画作为背景。或者用 17 连中的数据作为证据（"17 in a row after one fix"）。CTA 重复出现——SB7 强调 CTA 要出现多次。

### 7. GUIDE SECTION — 拍摄指南

**SB7 角色：** 过渡 CTA 的配套。降低"Film one shot"的执行门槛。

**保留当前页面的拍摄指南段，基本不变。** 这是 Plan 第一步的详细说明，帮助用户跨过"我不知道怎么拍"的障碍。

### 8. PRICING

**保留当前定价段。** SB7 里定价是 CTA 的延伸，不是独立故事段。

---

## i18n 文案对照表

### 英文版（en-US）

| Key | 当前 | 改为 |
|-----|------|------|
| `landing.title` | "Easy from 2-point range, but air balls from 3? It's not strength — it's coordination." | "Your shot feels off." |
| `landing.subtitle` | "AI analyzes your hand-leg coordination..." | "You've put in the reps. You know something's wrong. You just can't see it." |
| `landing.cta` | "Upload Video, 3 Free Trials" | "See Your Gap" |
| `landing.benefit1` | "Results in 30 seconds" | "2 free" |
| `landing.benefit2` | "2 free trials" | "Free to try" |
| `landing.benefit3` | "Detect the problem you didn't know you had" | "30 seconds" |
| `landing.failureTitle` | (new) | "1,000 reps with the same flaw isn't practice." |
| `landing.failureDesc` | (new) | "It's permanent. Every shot without fixing the gap cements the wrong pattern deeper. You can't fix what you can't see." |
| `landing.guideEmpathy` | (new) | "You've felt it. The shot that looks fine but doesn't feel right. The power that should be there but isn't." |
| `landing.guideAuthority` | (new) | "We see what your eyes can't. Frame by frame. Degree by degree. Every joint, every phase, every timing gap — measured and mapped." |
| `landing.planTitle` | (new) | "3 steps to a better shot" |
| `landing.planStep1Title` | (new) | "Film one shot" |
| `landing.planStep1Desc` | (new) | "One video, side angle, any phone" |
| `landing.planStep2Title` | (new) | "See what your eyes miss" |
| `landing.planStep2Desc` | (new) | "Every joint angle mapped. Every timing gap measured. Compared to pro templates if you want." |
| `landing.planStep3Title` | (new) | "Fix the gap" |
| `landing.planStep3Desc` | (new) | "Know exactly what to change. Then make more." |
| `landing.curvesTitle` | "Your shot, quantified." | "The gap is real. And it's measurable." |
| `landing.curvesSubtitle` | "See the angles your eyes can't..." | "Your eyes see a shot. We see 6 joint angles across 8 keyframes — the timing, the breaks, the invisible gaps that decide whether the ball goes in." |
| `landing.demoTitle` | "Power Coherence Detection Example" | "What we found in one shot" |
| `landing.featuresTitle` | "Your problem might be here" | (保留，或改为 "The gaps we find") |
| `landing.successTitle` | (new) | "When the power flows, the shot goes." |
| `landing.successDesc` | (new) | "Not luck. Not more reps. Just one gap found and fixed. That's the difference between 'feels off' and 'swish.'" |
| `landing.successCta` | (new) | "Find Your Gap" |
| `landing.knowledgeText` | "Shooting isn't just about arms..." | (保留，这是教育内容，和 SB7 不冲突) |
| `landing.knowledgeCta` | "Detect My Power Coherence" | "Find My Gap" |

### 中文版（zh-CN）

| Key | 当前 | 改为 |
|-----|------|------|
| `landing.title` | "两分随便投，一到三分线外就 Air Ball？不是力量不够，是发力不够连贯。" | "投篮感觉不对。" |
| `landing.subtitle` | "AI 分析你的手腿协调性..." | "你练了那么多。你知道哪里有问题。你只是看不见。" |
| `landing.cta` | "上传视频，免费分析 2 次" | "看到你的差距" |
| `landing.benefit1` | "30秒出结果" | "2 次免费" |
| `landing.benefit2` | "2 次免费试用" | "免费试用" |
| `landing.benefit3` | "检测你最不知道的问题" | "30 秒" |
| `landing.failureTitle` | (new) | "带着同一个缺陷练 1000 次，不是练习。" |
| `landing.failureDesc` | (new) | "是定型。每一次没修的出手，都在加深错误的肌肉记忆。你看不见，就修不了。" |
| `landing.guideEmpathy` | (new) | "你感受过。那个看着对但感觉不对的出手。那个应该有力量但就是没有的瞬间。" |
| `landing.guideAuthority` | (new) | "我们看到你眼睛看不到的。逐帧。逐度。每个关节、每个阶段、每个时序差距——测量、映射。" |
| `landing.planTitle` | (new) | "三步，更好的投篮" |
| `landing.planStep1Title` | (new) | "拍一个投篮" |
| `landing.planStep1Desc` | (new) | "一段视频，侧面角度，任何手机" |
| `landing.planStep2Title` | (new) | "看到眼睛看不到的" |
| `landing.planStep2Desc` | (new) | "每个关节角度映射。每个时序差距测量。可选球星模板对比。" |
| `landing.planStep3Title` | (new) | "修掉差距" |
| `landing.planStep3Desc` | (new) | "精确知道该改什么。然后投进更多。" |
| `landing.curvesTitle` | "Your shot, quantified." | "差距是真实的。而且可测量。" |
| `landing.curvesSubtitle` | "See the angles your eyes can't..." | "你的眼睛看到一个投篮。我们看到 8 个关键帧的 6 个关节角度——时序、断点、决定进球与否的看不见的差距。" |
| `landing.demoTitle` | "发力连贯性检测示例" | "一次投篮里我们发现了什么" |
| `landing.successTitle` | (new) | "发力通了，球就进了。" |
| `landing.successDesc` | (new) | "不是运气。不是更多练习。只是一个差距被找到、被修掉。这就是'感觉不对'和'空心入网'的区别。" |
| `landing.successCta` | (new) | "找到你的差距" |
| `landing.knowledgeCta` | "检测我的发力连贯性" | "找到我的差距" |

---

## 新增 HTML 段落结构

### Failure 段

```html
<section class="landing-failure">
    <h2 class="landing-failure-title" data-i18n="landing.failureTitle">
        1,000 reps with the same flaw isn't practice.
    </h2>
    <p class="landing-failure-desc" data-i18n="landing.failureDesc">
        It's permanent. Every shot without fixing the gap cements the wrong pattern deeper. You can't fix what you can't see.
    </p>
</section>
```

### Guide 段

```html
<section class="landing-guide-story">
    <div class="landing-guide-empathy">
        <h3 data-i18n="landing.guideEmpathyLabel">We get it</h3>
        <p data-i18n="landing.guideEmpathy">
            You've felt it. The shot that looks fine but doesn't feel right. The power that should be there but isn't.
        </p>
    </div>
    <div class="landing-guide-divider"></div>
    <div class="landing-guide-authority">
        <h3 data-i18n="landing.guideAuthorityLabel">We can help</h3>
        <p data-i18n="landing.guideAuthority">
            We see what your eyes can't. Frame by frame. Degree by degree. Every joint, every phase, every timing gap — measured and mapped.
        </p>
    </div>
</section>
```

### Plan 段

```html
<section class="landing-plan">
    <h2 class="landing-plan-title" data-i18n="landing.planTitle">3 steps to a better shot</h2>
    <div class="landing-plan-steps">
        <div class="plan-step">
            <div class="plan-step-number">1</div>
            <div class="plan-step-icon">🎬</div>
            <h3 data-i18n="landing.planStep1Title">Film one shot</h3>
            <p data-i18n="landing.planStep1Desc">One video, side angle, any phone</p>
        </div>
        <div class="plan-step-arrow">→</div>
        <div class="plan-step plan-step-highlight">
            <div class="plan-step-number">2</div>
            <div class="plan-step-icon">👁️</div>
            <h3 data-i18n="landing.planStep2Title">See what your eyes miss</h3>
            <p data-i18n="landing.planStep2Desc">Every joint angle mapped. Every timing gap measured.</p>
        </div>
        <div class="plan-step-arrow">→</div>
        <div class="plan-step">
            <div class="plan-step-number">3</div>
            <div class="plan-step-icon">🔧</div>
            <h3 data-i18n="landing.planStep3Title">Fix the gap</h3>
            <p data-i18n="landing.planStep3Desc">Know exactly what to change. Then make more.</p>
        </div>
    </div>
    <!-- Step 2 对比效果图预览 -->
    <div class="plan-step-preview" id="planStep2Preview">
        <div class="preview-demo" id="previewDemo">
            <div class="preview-keyframes">
                <div class="preview-kf-pair">
                    <img src="/static/demo_release_user.jpg" alt="Your form">
                    <span class="preview-vs">vs</span>
                    <img src="/static/demo_release_template.jpg" alt="Pro form">
                </div>
                <div class="preview-angle-diff">23° apart at release</div>
            </div>
            <div class="preview-curve">
                <svg id="previewCurveSvg"></svg>
            </div>
            <div class="preview-label">Example result</div>
        </div>
        <div class="preview-real" id="previewReal" style="display: none;">
            <div class="preview-keyframes" id="previewRealKeyframes"></div>
            <div class="preview-curve" id="previewRealCurve">
                <svg id="previewRealCurveSvg"></svg>
            </div>
        </div>
    </div>
</section>
```

### Success 段

```html
<section class="landing-success">
    <h2 class="landing-success-title" data-i18n="landing.successTitle">
        When the power flows, the shot goes.
    </h2>
    <p class="landing-success-desc" data-i18n="landing.successDesc">
        Not luck. Not more reps. Just one gap found and fixed. That's the difference between "feels off" and "swish."
    </p>
    <button class="landing-cta-btn" onclick="openAuthModal()">
        <span>→</span>
        <span data-i18n="landing.successCta">Find Your Gap</span>
    </button>
</section>
```

---

## CTA 重复策略

SB7 强调：CTA 要在页面中出现 **3-5 次**。当前页面只有 2 次（hero + demo 底部），改为：

| 位置 | CTA 文案 | 类型 |
|------|---------|------|
| Hero | "See Your Gap" | 直接 |
| Plan 段末 | "See Your Gap" | 直接 |
| Success 段 | "Find Your Gap" | 直接（换词避免重复感） |
| Knowledge 段末 | "Find My Gap" | 直接 |
| 拍摄指南段 | (保留当前的，作为 Plan Step 1 的延伸) | 过渡 |

---

## 不改的部分

- **拍摄指南段** — 保留，这是 Plan Step 1 的详细说明
- **Feature 卡片** — 保留，但标题从"你的问题可能在这里"改为"The gaps we find"（从"问题"改为"我们发现的差距"，向导视角）
- **Pricing 段** — 保留
- **Footer** — 保留
- **曲线 demo** — 保留，只改文案
- **检测示例** — 保留，只改标题

---

## 实施优先级

1. **P0（文案替换，零代码改动）**：Hero title/subtitle/CTA/benefits、curves demo 文案、demo 标题、knowledge CTA
2. **P1（新增 HTML 段）**：Failure 段、Guide 段、Plan 段、Success 段
3. **P2（CSS 样式）**：新增段的样式设计
4. **P3（动画/交互）**：Failure 段计数器动画、Plan 段步骤动画
