# FAILED — Phase 8 — hardening and full verification

## Built

- Added `SecurityMiddleware` with CSP, `X-Content-Type-Options`, frame/referrer/permission policies, no-store API responses, configurable per-IP rate limiting, and safe internal-error responses.
- Applied redaction to API log prompts and strengthened secret redaction for OTP, PIN, password, CVV, Aadhaar, and account-like values.
- Added safety tests covering S1–S10 concerns, including negative-control assertions for the extension sensitivity and origin guards.
- Added TRD error-path tests, a 50-concurrent-session benchmark, touch-target checks, ARIA/keyboard contracts, and repository/browser secret scanning.

## Gate results

| Check | Exact command | Result | Evidence |
|---|---|---|---|
| Lint | `ruff check .` | PASS | `All checks passed!` |
| Phase 8 hardening | `pytest -q tests/test_phase8.py` | PASS | `12 passed, 1 warning` |
| Full suite | `pytest -q` | PASS | `205 passed, 2 warnings` |
| Routing gate | `python tests/eval/run_eval.py --split test` | PASS | 91.96% exact; 100% named entities |
| Concurrency | included in `tests/test_phase8.py` | PASS | 50 concurrent sessions, all HTTP 200, p95 under 2.5s |
| axe-core | required by Phase 8 gate | NOT RUN | axe-core is not installed in this environment |

## Raw output tails

```text
All checks passed!
............                                                             [100%]
12 passed, 1 warning

........................................................................ [ 35%]
........................................................................ [ 70%]
.............................................................            [100%]
205 passed, 2 warnings in 22.85s
```

## Not verified live / limitations

- axe-core was not installed, so a real axe serious/critical-violation scan was not run. The Playwright accessibility contract, ARIA checks, keyboard-oriented controls, and 56px touch-target assertions passed.
- Wispr, Anthropic, and OpenAI live calls were not run because no credentials were configured.
- The concurrency measurement is local and unthrottled; the required Slow 4G/4x CPU CDP profile was not run.
- Negative-control evidence is automated for the extension sensitivity and allow-list guards; the remaining safety checks are blocking regression tests but do not yet have independent fault-injection harnesses.
