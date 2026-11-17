# FormRefine 2.0.0

Release snapshot: 2026-11-18.

- Unified landing page and analysis workflow, readable shared styling, sticky navigation and compact template selection.
- One anonymous analysis with persistent trial limits, account handoff and private report access.
- Saved analysis history, personal keyframe comparisons, and three interactive trends: release elbow angle, deepest knee angle and dip-to-release time. Missing measurements remain missing; changes are not improvement scores.
- Shooting guides, server-rendered SEO metadata, canonical URLs, sitemap and preview noindex handling.
- Improved keyframe timing and boundary handling, chronological presentation and additional Booker, Lillard and Ray Allen reference templates.
- Expanded administration: analysis quality, user timelines, journey metrics and credit/account operations.
- Reusable regression runner, local HTML test dashboard and matching CI checks.
- Human-feedback pilot entry removed from the public UI. Historical private records and backend APIs are retained; normal uploads no longer request retention for human review.

## Validation

Run `venv/bin/python scripts/verify_site.py`. With the local MediaPipe runtime and video fixture, also run `venv/bin/python scripts/verify_site.py --extended --video modelVideo/Booker-model.mp4`.
Generated reports, local credentials/settings, user uploads/results, private databases and raw model videos are not part of the release commit.

Release verification passed: 14 groups / 104 cases, including the real-video pipeline (2026-11-18).

## Deployment notes

Persist the trial database and report storage together. Configure the canonical production origin and secrets through the deployment environment. The local test dashboard is not a public product route. This release commit does not deploy or push the application.
