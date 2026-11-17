# Admin operations and analysis quality

Open `/admin` with a local administrator account. The default page is **运营与分析质量**.

## Data definitions

- The operations page reads `reports` in `TRIAL_DB_PATH`: all newly uploaded anonymous/account tasks are included once by task ID. Claiming a report changes its owner, not its task count.
- Choose 7, 30 or 90 days. Task cards use task creation time; durations measure upload reservation to completed analysis. Missing historical quality data is unknown, not zero.
- Trial funnel: recorded visitor → trial started after visit → trial completed → report claimed. Counts are unique signed-cookie visitors from the same cohort, not event ratios. Claiming means saved to an account, not necessarily a new registration.
- Attribution uses the first recorded source in the selected period: `utm_source`, external referrer hostname, or `direct`. This is browser-level attribution, not cross-device identity. Development hosts and `skip_tracking` browsers do not send visits. Visitors are recorded after the trial cookie has been established, avoiding competing cookie initialization.
- Repeat accounts have at least two completed reports created in the selected period. This is not a D7 retention metric.
- User quality survey has two optional yes/no questions. One response per completed private report; submitting again updates the response. Report ownership/expiry rules also apply to feedback.
- Old cloud data remains under **Legacy account overview**, rather than silently mixing incompatible sources. User count there means accounts with credit records.

## Storage and limits

Tables `ops_events`, `ops_quality`, `ops_feedback`, and `credit_changes` are created automatically in the trial SQLite database. Keep its persistent volume mounted and backed up. Multi-instance deployments need a shared database before these metrics can be treated as site-wide totals. No raw IP or video content is copied into these tables.

Visitor events retain 90 days. Recent task and credit-adjustment tables display the latest 100 rows; summary metrics cover the entire selected period. No historical channels, duration or feedback are fabricated.

Credits require a reason and record actor, target, observed before/after balances and time. Credit writes remain in Supabase; the local audit write is a separate transaction, so it is not an accounting ledger or a concurrency-safe replacement for the payment system.

## Verification

`venv/bin/python scripts/verify_site.py` includes `tests/admin`: cookie/quota isolation, same-cohort funnel, claim deduplication, historical unknown duration, permissions, feedback privacy/idempotence and credit adjustment outcomes.

For upload instrumentation changes also run:

```sh
venv/bin/python scripts/verify_site.py --extended --video modelVideo/Booker-model.mp4
```

Results appear in `artifacts/verification/index.html`. Tests use temporary storage and mocked account credits; no production payments or user balances are modified.

## P0/P1 completion: journeys and drill-down

The operations page now includes:

- Ordered, unique-cookie trial journey: visit → file selection → analysis started → completed → result viewed → claimed → another analysis started. All steps must have evidence in the selected window, in order. This is an anonymous-first acquisition funnel, not a count of all signed-in traffic.
- Registration is a branch after result viewing. **Submitted registration** is a client signal; **registered** uses the verified auth provider's account creation timestamp on login/claim. Returning accounts are not treated as new registrations. Email confirmation across another device cannot be attributed without the original cookie; unknown conversions are not invented.
- Source, landing path (no query string), and UTM campaign breakdowns. Guides are instrumented too. The earliest recorded landing within the window supplies attribution.
- Comparison counts after a claim, actual repeat analysis creation, and a directory of accounts that analyzed in the selected period.
- Missing-keyframe breakdown and an anomaly queue (failures, observed missing phases, or processing for over an hour). The eight expected phase labels are diagnostic references: an absent phase may be intentionally withheld for insufficient evidence and does not prove a form problem.
- Task detail includes parameters, timing, failure text, observed phases, timestamps, angles and private image previews. Existing report JSON can be inspected for historical detail; expired/deleted images remain unavailable. The automatic missing-phase aggregate uses only newly captured diagnostics.
- User detail is accessible from the existing Users table, the operations directory, task details, or ID lookup. It combines attributed events, local and cloud analyses (deduplicated by task ID), quality responses, training feedback and follow-ups, credit changes, subscription state and processed checkouts. Cloud errors are shown explicitly. Payment amounts/refunds are not present in the existing checkout schema and are not inferred.

New tables `ops_journey`, `ops_identity`, and `ops_task_details` are automatically initialized alongside the existing SQLite tables. No Supabase migration is required. Journey events retain 90 days. Identity links and task diagnostics persist with the operational store. Authentication and ownership checks protect event-report references; all admin drill-down and media endpoints require the existing local admin role. Frontend text uses DOM text nodes, and private preview images are fetched with authorization and rendered through short-lived blob URLs.

Run the normal verification command to exercise the new ordered-cohort, registration, cloud-unavailable, task details, media expiry, account isolation and frontend detail rendering cases. The full extended run also validates a real video and exports. Browser preview fixtures contain synthetic data, never production user data.
