# Anonymous trial and personal history

Implemented 2026-11-15.

## User flow

- Anonymous visitors receive one successful analysis, up to 10 seconds. The complete report is visible without signup.
- A signed HttpOnly, SameSite cookie identifies the browser for one year. Quota is stored server-side, not in localStorage. Refreshing or restarting the server does not reset it.
- A running job reserves the opportunity atomically. Failed analysis (including no usable keyframes) releases it. Simultaneous requests cannot reserve twice.
- Reports can be reopened from the upload section for 24 hours. Expired anonymous media is removed during trial-status maintenance or server startup.
- Signing in automatically claims unexpired reports from that browser, including jobs still processing. Repeated sign-in events are idempotent. Claiming never changes account credits; the existing three-credit new-account policy remains in effect.
- History is account-scoped. Two completed reports can be selected to compare matching keyframes, angles and numeric differences. This does not infer that a change is an improvement.
- The anonymous report retains keyframes and measurements, not the source video for the human-feedback workflow. Logged-in users retain the existing optional feedback-video feature.

## Persistence and deployment

This version uses the project's persistent-disk model, like the feedback service. Set `TRIAL_DB_PATH` on a persistent volume (default `data/trials.sqlite3`) and persist `RESULTS_DIR` on that same deployment. SQLite and report media must survive restarts/redeployments. All workers must share the same local volume. Independent replicas require migrating the quota/ownership store to a shared transactional database and media to private shared storage before scaling out.

- `TRIAL_DAILY_LIMIT=100`: maximum anonymous analysis attempts per UTC day.
- `TRIAL_IP_HOURLY_LIMIT=10`: maximum anonymous attempts per direct client IP per rolling hour; failed attempts count toward this abuse limit.
- IP addresses are stored as keyed hashes. Forwarded headers are deliberately not trusted by application code. Configure the server's trusted proxy policy for the actual ingress, otherwise users behind the same proxy share this limit.
- Set a strong `JWT_SECRET` before production. It signs both existing authentication and purpose-separated visitor/media values.
- Clear cookies / a different browser / a different network can still obtain another anonymous identity. This is cost containment, not per-human identification.
- Processing jobs older than one hour are treated as abandoned during maintenance and become retryable.

New reports' API results, status, deletion, exports and `/results` media enforce ownership. Account images use a signed one-hour media-only cookie; opening History refreshes it. Logging out clears it. Legacy public demonstration media is unchanged, and legacy DB reports remain available to their owners. Unowned legacy disk reports are not shown in normal users' history.

New saved reports are excluded from the old ten-report cleanup. Account holders can delete them from History. No paid analysis or live account changes are needed by the automated suite.

## Verification

```bash
venv/bin/python scripts/verify_site.py
# Fast check including trial HTTP/concurrency tests and frontend flow tests:
venv/bin/python scripts/verify_site.py --quick
```

Tests use temporary storage, mocked identities and synthetic video. They cover persistent quotas, concurrent reservations, failure refunds, invalid video rejection, budget limits, forged visitor cookies, claim idempotency, cross-account access, static-media authorization, logout, expiry, history, deletion, and frontend login continuation. Results are written to `artifacts/verification/summary.json`.

For a real video integration check (analysis, ZIP/PDF export, claim, history, account isolation and deletion in temporary storage):

```bash
venv/bin/python scripts/verify_trial_video.py modelVideo/Booker-model.mp4
```

The default regression runner now also includes installed-template asset/curve checks and phase-transition regressions. Expanded task-lifecycle coverage verifies that timed-out tasks stop polling and late workers cannot revive deleted/abandoned reports.
