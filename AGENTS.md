# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

Basketball Shooting Form Analyzer - A FastAPI backend that analyzes basketball shooting form videos using MediaPipe Pose estimation.

## Build & Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
python test_core.py
python test_import.py
python test_phase_detector_optimization.py
python test_template_comparison_flow.py
python test_template_load.py
python test_landmark_fixes.py

# Run all tests (CI)
export PYTHONPATH=$PYTHONPATH:.
python test_core.py && python test_import.py

# Start development server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Access
# Frontend: http://localhost:8000/app
# API docs: http://localhost:8000/docs
```

## Architecture

### Core Modules (`app/core/`)

| Module | Purpose |
|--------|---------|
| `pose_detector.py` | MediaPipe Pose detection (33 landmarks). `PoseDetector.detect()` returns `PoseResult` |
| `angle_calculator.py` | Calculates shooting angles (elbow, shoulder, knee, trunk, wrist, hip) |
| `phase_detector.py` | Detects shooting phases: Preparation → Lifting → Release → Follow-through |
| `rules_engine.py` | BEEF-based evaluation (Balance, Eyes, Elbows, Follow-through) with NBA player references |
| `video_processor.py` | Video I/O, frame extraction, annotated video generation |

### Service Layer (`app/services/`)

- `analysis_service.py` - Orchestrates full analysis pipeline: detect → calculate → phase → evaluate → generate outputs

### API Routes (`app/api/routes/`)

- `upload.py` - Video upload, async analysis task, template comparison
- `templates.py` - Template management (save/load shooting form templates)
- `export.py` - Export PDF report, keyframes, comparison images, and share card
- `health.py` - Health check

### Export Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /export/{task_id}/pdf` | Export PDF report (supports zh-CN/en-US) |
| `GET /export/{task_id}/images/keyframes` | Export keyframe images as ZIP |
| `GET /export/{task_id}/images/comparisons` | Export side-by-side comparison images as ZIP |
| `GET /export/{task_id}/images/all` | Export all images (keyframes + comparisons) as ZIP |
| `GET /export/{task_id}/images/share-card` | Export single shareable long image for social media |

### Data Flow

```
Upload Video → Pose Detection (MediaPipe) → Angle Calculation → Phase Detection → Rules Evaluation → Results
                                         ↓
                          Key Frames + Annotated Video + PDF Report
```

### Shooting Phases

1. **Preparation** - Knee bend, elbow flexion, ready position
2. **Lifting** - Arm raising, wrist ascending
3. **Release** - Full elbow extension, highest wrist point
4. **Follow-through** - Wrist descending, form hold

### Key Classes

- `ShootingAngles` - Dataclass for angle data (elbow, shoulder, knee, trunk, wrist, hip)
- `PhaseSegment` - Detected phase with frame range and duration
- `EvaluationResult` - Overall score, rating, dimension scores, issues, suggestions
- `FullAnalysisResult` - Complete analysis output with key frames and annotated video path

## Configuration

- `app/config.py` - Pydantic Settings loaded from `.env`
- Key settings: `upload_dir`, `results_dir`, `templates_dir`, `target_fps=30`, `max_video_size_mb=50`

## Deployment

- Docker: `Dockerfile` configured for Hugging Face Spaces (SDK: docker)
- Port: 7860 (HF Spaces default, configurable via `$PORT` env)
- CI: GitHub Actions runs test suite on push to main/master

## Template System

Templates store reference shooting forms for comparison:
- Location: `templates/` directory
- Each template: `metadata.json` + 4 key frame images (preparation, lifting, release, follow_through)
- Comparison: angle differences between user and template at each phase

## Required regression workflow

After changing application behavior, run `venv/bin/python scripts/verify_site.py` (use `python` when no local venv exists). Add/update a regression case for any behavioral fix. Do not treat legacy print-only diagnostics as passing assertions.

- Fast iteration: `venv/bin/python scripts/verify_site.py --quick`.
- Changes affecting video analysis, image export or report lifecycle: additionally run `venv/bin/python scripts/verify_site.py --extended --video modelVideo/Booker-model.mp4` when the video and MediaPipe runtime are available. Missing fixtures or runtime access must be reported; do not claim these checks passed.
- Optional read-only live check: append `--live-url http://127.0.0.1:8000`.
- Inspect `artifacts/verification/index.html` and `summary.json`; resolve failed checks or explicitly report the blocker before handing off.
- Test storage/accounts must remain isolated. Never run real payment/signup writes as part of regression without explicit authorization.
- The HTML dashboard is local/CI tooling, not a production app route. Do not expose test execution through the public product.
- When adding test suites, register them in `scripts/verify_site.py` so the dashboard and CI run the same checks.
