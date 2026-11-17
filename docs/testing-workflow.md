# Automated verification and test dashboard

## Daily use

```bash
# Full deterministic suite; generates an offline HTML dashboard
venv/bin/python scripts/verify_site.py
# Faster iteration
venv/bin/python scripts/verify_site.py --quick
# Watch source saves and automatically rerun quick checks (Ctrl+C to stop)
venv/bin/python scripts/watch_tests.py
# Watch source saves and run full checks instead
venv/bin/python scripts/watch_tests.py --full
# Real video + MediaPipe drawing + full suite, without using real accounts
venv/bin/python scripts/verify_site.py --extended --video modelVideo/Booker-model.mp4
# Add read-only validation against an existing server
venv/bin/python scripts/verify_site.py --live-url http://127.0.0.1:8000
```

Open `artifacts/verification/index.html` directly in a browser. No report server or network dependency is required. The dashboard shows module descriptions, individual unittest/function/Node test cases, status, duration, exception details and log links. Dependency imports, real-video lifecycle and live website checks are explicitly labeled process-level checks rather than invented individual assertions. Search names/reasons, filter results, and select earlier runs. Refresh while the runner is active to see updated progress.

Each invocation writes `runs/<UTC timestamp>-<unique id>/summary.json`, case JSON and full logs. The root `summary.json` points to the latest run. The dashboard displays the most recent 40 runs; older files are retained. Different runs never overwrite one another's logs. Concurrent invocations have independent directories; the last report writer controls the root view.

`passed` means all **selected** checks passed. Unselected checks are marked skipped and never counted as passing. `--extended` requires a playable video and MediaPipe access; a missing file or unavailable runtime fails the selected check. On macOS, Metal may require execution outside the sandbox. Ctrl+C records an interrupted run. Hard OS termination can leave an in-progress snapshot; check its timestamp and rerun rather than interpreting it as success.

## Automatic execution

- GitHub Actions runs the full deterministic suite on pushes and pull requests; manual dispatch is also available. It uploads the HTML/JSON/log bundle even when tests fail and adds a check table to the Actions summary. Download/extract the artifact and open `index.html`.
- The local watcher is opt-in and runs only while its process is open. It debounces changes, avoids overlapping runs and ignores generated reports/data to prevent loops. It is not installed as an OS background service.
- `AGENTS.md` instructs future coding sessions to run the same checks and add regression coverage after behavioral changes.

## Adding tests

Add unittest cases under the appropriate `tests/` folder. Descriptive method names and docstrings appear in the dashboard. The case runner preserves failure traces and skips. New groups must be registered in the runner's `CATALOG`; this is the shared test inventory for CLI, HTML and CI. JavaScript behavior tests stay in `tests/web/frontend-flow.cjs` and use Node's TAP output.

The reporting system itself tests failure/skip recording, command timeouts, missing executables, history preservation, injected-output escaping and watcher change detection.

## Scope boundaries

The default suite uses temporary upload/report/feedback databases and disables external database/payment credentials. No real subscription charge, registration email, production deployment, load test or full browser login is included. Those external integrations need a separate staging setup. The four locally installed templates are tested when present; clean CI checks its checked-in reference set.
