# 🏀 Analysis Logic - How the System Works

## 📊 Core Analysis Pipeline

The system analyzes your shooting form through **4 main steps**:

```
Video Upload
    ↓
1. Pose Detection (MediaPipe)
    ↓
2. Angle Calculation
    ↓
3. Phase Detection
    ↓
4. Rules Engine Evaluation
    ↓
Results + Suggestions
```

---

## 🎯 What the System Measures

### 1. **Pose Detection** (Using MediaPipe)
- Detects **33 body landmarks** in each frame
- Tracks key points: shoulders, elbows, wrists, hips, knees, ankles
- Works on side-view shooting videos

### 2. **Angle Calculation**
The system calculates **5 critical angles**:

| Angle | Measurement Points | What It Shows |
|-------|-------------------|---------------|
| **Elbow** | Shoulder → Elbow → Wrist | Arm extension |
| **Shoulder** | Hip → Shoulder → Elbow | Release height |
| **Knee** | Hip → Knee → Ankle | Leg bend/power |
| **Trunk** | Vertical → Shoulder → Hip | Body lean |
| **Wrist** | Elbow → Wrist → Hand | Wrist snap |

### 3. **Phase Detection**
Identifies **4 shooting phases**:

1. **Preparation** - Ready stance, knees bent
2. **Lifting** - Ball going up
3. **Release** - Ball leaving hand
4. **Follow Through** - After release

---

## 📐 Evaluation Criteria

The system evaluates **6 dimensions** of shooting form:

### 1. Elbow Extension (20% weight)
**What it checks:**
- Arm fully extended at release?
- Elbow angle at release point

**Ideal values:**
- ✅ **Excellent**: 170°+ (almost straight)
- ⚠️ **Acceptable**: 150°-170°
- ❌ **Needs work**: < 150°

**Common issues detected:**
- "Arm not fully extended at release"
- Suggests: "Fully extend your arm at release, fingers pointing at the rim"

---

### 2. Leg Power (15% weight)
**What it checks:**
- Knee bend during preparation
- Using leg power for the shot

**Ideal values:**
- ✅ **Excellent**: 100° or less (deep bend)
- ⚠️ **Acceptable**: 100°-120°
- ❌ **Needs work**: > 120° (too upright)

**Common issues detected:**
- "Insufficient knee bend during preparation"
- Suggests: "Bend your knees more before shooting, use leg power to help your shot"

---

### 3. Body Balance (15% weight)
**What it checks:**
- Body upright at release?
- Trunk lean angle

**Ideal values:**
- ✅ **Excellent**: ≤ 5° (nearly vertical)
- ⚠️ **Acceptable**: 5°-15°
- ❌ **Needs work**: > 15° (leaning)

**Common issues detected:**
- "Excessive body lean at release"
- Suggests: "Keep your body upright at release, avoid leaning forward or backward"

---

### 4. Release Point (20% weight)
**What it checks:**
- Release height
- Shoulder angle at release

**Ideal values:**
- ✅ **Excellent**: 90°+ (high release)
- ⚠️ **Acceptable**: 70°-90°
- ❌ **Needs work**: < 70° (low release)

**Common issues detected:**
- "Low release point"
- Suggests: "Raise the ball above your forehead before releasing, higher release point"

---

### 5. Follow Through (15% weight)
**What it checks:**
- Wrist snap after release
- Hand position maintained

**Ideal values:**
- ✅ **Excellent**: Clear wrist flexion (≤ 140°)
- ⚠️ **Acceptable**: Some follow through detected
- ❌ **Needs work**: No follow through phase detected

**Common issues detected:**
- "No clear follow-through detected"
- Suggests: "Keep your wrist snapped down after release, fingers pointing at the rim"

---

### 6. Fluidity (15% weight)
**What it checks:**
- Smooth phase transitions
- Complete shooting motion
- Proper sequence

**Ideal values:**
- ✅ **Excellent**: All 4 phases in correct order
- ⚠️ **Acceptable**: 3+ phases detected
- ❌ **Needs work**: Missing phases or wrong order

**Common issues detected:**
- "Shot may be rushed, incomplete phases detected"
- Suggests: "Slow down, ensure clear preparation, lifting, and release phases"

---

## 🔢 How Scoring Works

### Score Calculation

Each dimension gets a score (0-100), then weighted:

```
Overall Score = (Elbow × 20%) + (Leg × 15%) + (Balance × 15%) + 
                (Release × 20%) + (Follow × 15%) + (Fluidity × 15%)
```

### Rating Levels

| Score | Rating | Meaning |
|-------|--------|---------|
| 90-100 | **Excellent** | Professional-level form |
| 75-89 | **Good** | Solid fundamentals |
| 60-74 | **Fair** | Room for improvement |
| 0-59 | **Needs Work** | Significant issues |

---

## 🎯 Threshold-Based Detection

### Example: Elbow Extension

```python
Ideal: 170° (perfect arm extension)
Minimum: 150° (acceptable)

If angle = 175°:
  ✅ Score = 100 (Excellent!)
  
If angle = 160°:
  ⚠️ Score = 85 (Good, linear interpolation between 150-170)
  
If angle = 140°:
  ❌ Score = 65 (Needs work)
  🚨 Issue detected: "Arm not fully extended"
  💡 Suggestion: "Fully extend your arm at release"
```

### Example: Knee Bend

```python
Ideal: 100° or less (deep squat)
Maximum: 120° (acceptable limit)

If angle = 95°:
  ✅ Score = 100 (Perfect leg power!)
  
If angle = 110°:
  ⚠️ Score = 85 (Good)
  
If angle = 135°:
  ❌ Score = 62
  🚨 Issue: "Insufficient knee bend"
  💡 Suggestion: "Bend your knees more, use leg power"
```

---

## 🔍 Issue Detection Logic

### Severity Levels

Issues are categorized by severity:

| Severity | When Detected | Visual |
|----------|---------------|--------|
| **HIGH** | Major form flaw (e.g., elbow < 130°) | 🔴 Red |
| **MEDIUM** | Noticeable issue (e.g., elbow 130-150°) | 🟡 Yellow |
| **LOW** | Minor improvement area | 🔵 Blue |

### Priority Ranking

Suggestions are shown by priority:
1. **HIGH severity** issues first
2. **MEDIUM severity** issues second
3. **LOW severity** issues last
4. Maximum of **5 suggestions** shown

---

## 📋 Example Analysis Flow

### Input Video
Side-view shooting video, 3-10 seconds

### Step 1: Pose Detection
- Detects person in each frame
- Extracts 33 body landmarks
- Tracks throughout video

### Step 2: Angle Calculation (per frame)
```
Frame 45:
  Elbow: 165°
  Knee: 105°
  Trunk: 8°
  Shoulder: 85°
  Wrist: 145°
```

### Step 3: Phase Detection
```
Frames 1-30:   Preparation (knee bending)
Frames 31-50:  Lifting (ball going up)
Frames 51-60:  Release (ball leaving hand)
Frames 61-75:  Follow Through (wrist snap)
```

### Step 4: Evaluation

**Elbow Extension (20%):**
- Average at release: 165°
- Score: 88/100 (Good)
- Feedback: "Arm extension is acceptable, could be fuller"

**Leg Power (15%):**
- Minimum knee angle: 105°
- Score: 95/100 (Excellent)
- Feedback: "Good leg power and knee bend"

**Body Balance (15%):**
- Average trunk lean: 8°
- Score: 92/100 (Excellent)
- Feedback: "Good body balance and stability"

**Release Point (20%):**
- Average shoulder angle: 85°
- Score: 82/100 (Good)
- Feedback: "Release point is acceptable, could be higher"

**Follow Through (15%):**
- Wrist snap detected: Yes
- Score: 90/100 (Excellent)
- Feedback: "Good follow through with wrist snap"

**Fluidity (15%):**
- All phases detected in order
- Score: 90/100 (Excellent)
- Feedback: "Smooth and fluid shooting motion"

### Final Results

```
Overall Score: 89.9 → 90
Rating: Excellent

Top Suggestion:
💡 "Fully extend your arm at release"
   (Related to elbow angle of 165°)
```

---

## 🎓 What Makes This Analysis Reliable

### 1. **Based on Basketball Fundamentals**
- Angle thresholds come from professional shooting form
- Mirrors coaching points from NBA trainers
- Standard biomechanics principles

### 2. **Objective Measurements**
- Not subjective - based on actual angles
- Consistent evaluation every time
- Removes human bias

### 3. **Context-Aware**
- Considers different shooting phases
- Understands preparation vs. release
- Looks at motion sequence

### 4. **Weighted Scoring**
- Critical elements (elbow, release) = 20% each
- Supporting elements (balance, legs) = 15% each
- Reflects real importance in shooting

---

## 🔧 Customizable Thresholds

The system uses these default values, but they can be adjusted:

```python
# Default Thresholds
elbow_ideal: 170°
elbow_minimum: 150°

knee_ideal: 100°
knee_maximum: 120°

trunk_ideal: 5°
trunk_maximum: 15°

shoulder_ideal: 90°
shoulder_minimum: 70°

wrist_follow_minimum: 140°
```

---

## 💡 Why You Get Specific Suggestions

### The Logic:

1. **Detect deviation** from ideal angles
2. **Classify severity** based on how far off
3. **Match to issue type** (predefined categories)
4. **Generate specific tip** for that issue
5. **Rank by severity** (fix worst issues first)

### Example Suggestion Mapping:

| Detected Issue | Suggestion Given |
|----------------|------------------|
| Elbow 140° (< 150°) | "Fully extend your arm at release, fingers pointing at the rim" |
| Knee 130° (> 120°) | "Bend your knees more before shooting, use leg power to help your shot" |
| Trunk 20° (> 15°) | "Keep your body upright at release, avoid leaning forward or backward" |
| Shoulder 65° (< 70°) | "Raise the ball above your forehead before releasing, higher release point" |
| No follow phase | "Keep your wrist snapped down after release, fingers pointing at the rim" |

---

## 🎯 Summary

The system analyzes your shooting form by:

1. ✅ **Detecting** your body pose using MediaPipe AI
2. ✅ **Measuring** 5 key angles throughout the motion
3. ✅ **Identifying** 4 distinct shooting phases
4. ✅ **Evaluating** 6 dimensions against ideal thresholds
5. ✅ **Calculating** weighted scores (0-100)
6. ✅ **Detecting** specific issues with severity levels
7. ✅ **Generating** prioritized, actionable suggestions

**It's like having a basketball coach that:**
- Never gets tired
- Measures every angle precisely
- Gives consistent feedback
- Focuses on what matters most

---

## 📊 Visual Representation

```
Your Video
    ↓
[MediaPipe AI Pose Detection]
    ↓
Body Landmarks (33 points)
    ↓
[Angle Calculator]
    ↓
5 Key Angles per Frame
    ↓
[Phase Detector]
    ↓
4 Shooting Phases Identified
    ↓
[Rules Engine - 6 Dimensions]
    ↓
┌─────────────────────────────┐
│ Elbow Extension     88/100  │ × 20% = 17.6
│ Leg Power           95/100  │ × 15% = 14.25
│ Body Balance        92/100  │ × 15% = 13.8
│ Release Point       82/100  │ × 20% = 16.4
│ Follow Through      90/100  │ × 15% = 13.5
│ Fluidity            90/100  │ × 15% = 13.5
└─────────────────────────────┘
    ↓
Overall Score: 89.05 → 90 (Excellent)
    ↓
Issues Detected + Suggestions
```

---

**The analysis is based on objective biomechanical measurements, not guesswork!** 🎯
