# Public UI and progress tracking — 2026-11-17

## Navigation and workspace
- Public header stays visible; ResizeObserver updates native anchor scroll padding as the header wraps or account controls change.
- History opens in view, even when the independent trial claim fails. It holds saved reports, before/after comparison and recent trends.
- Feedback & follow-up is the invitation-only human review workspace. Users return after requesting a review to read feedback and submit a follow-up, rather than treating it as an automatic exercise library.

## Landing story (SB7)
1. Character: a player who wants a shot they can trust in games.
2. Problem: putting in repetitions without knowing what to adjust.
3. Guide: acknowledge the frustration; provide visible video evidence rather than promises of performance.
4. Plan: upload, review one focus, film again and compare.
5. Action: Analyze my shot; secondary action: view example.
6. Stakes: continued guessing about what practice changes.
7. Success: a clear practice focus and a record of measured changes.

Retain basketball shooting form in H1. Avoid claims that a thousand repetitions necessarily worsen form or that analysis guarantees beating an opponent.

## Trends
Latest ten completed reports through the existing authenticated result endpoint. No new public endpoint or account writes. Chronological chart and exact-value table; gaps remain missing, inaccessible reports are labelled unavailable. Metrics: sync_frame_1 to release_frame time, knee_min_frame knee angle, release_frame elbow angle. These are video estimates, not ball velocity or a performance score. Slow-motion clips, camera view, distance and shot type must be comparable; conditions are currently a user judgement, not automatically classified.

## Verification
Run `venv/bin/python scripts/verify_site.py`. Frontend suite includes dynamic anchor offset, history navigation on claim failure, guest login, and missing/reversed timing data. Chrome verification covered native anchor navigation, feedback dialog appearance, saved history/trend loading and template comparison image heights. Local file selection was blocked by the extension file-access setting; no fresh analysis was run. The optional ui-layout-fixture.html contains synthetic data only and is not a product route.

## Pilot entry removed (2026-11-17)
At the owner's request the public page no longer loads the human feedback workspace, mounts its result CTA, or offers video retention for human review. New frontend uploads no longer send `retain_for_feedback=true`. Guide/home copy no longer promotes the pilot. Ordinary History, personal comparisons, trends and analysis-quality surveys remain. Existing private pilot records and backend APIs are retained rather than deleted; this is a withdrawal from the public UI, not a data migration or removal of the historical backend.

## Direct trend overview
History now shows three charts simultaneously: release elbow angle, deepest knee angle and dip-to-release time. Each shows the latest measurement and its difference from the immediately previous report; missing values remain missing, rather than silently comparing a different pair. Angle axes are fixed at 0–180 degrees and timing axes start at zero. Report points support mouse and Enter/Space navigation to the existing detail view. The exact-value table is collapsible. Empty, missing-data, escaped filenames and delta rendering are covered by the frontend regression suite. Live chart visual verification needs a signed-in session; the current Chrome session had expired during verification.
