# PHASE 0 REPORT

Built:

- Added a single FastAPI process with `/healthz` and `python run.py`.
- Added optional `.env` compose configuration and matching `.env.example` settings.
- Added environment and D1–D16 audit records, `PROGRESS.md`, and `STUBS.md`.
- Added ruff, pytest, and GitHub Actions configuration.
- Kept the home page explicitly marked DEMO MODE.

Gate results:

| Check | Exact command | Result | Evidence |
|---|---|---|---|
| Fresh environment and health check | `python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r services/api/requirements.txt; python run.py` then `Invoke-RestMethod http://127.0.0.1:8000/healthz` | PASS | See raw output below: HTTP response was `status=ok`, `demo_mode=True`. |
| pytest | `pytest -q` | PASS | `6 passed`. |
| ruff | `ruff check .` | PASS | `All checks passed!`. |
| Audit coverage | `Get-Content reports/audit.md` | PASS | D1–D16 and salvage/rewrite table present; unavailable zip explicitly recorded. |

Raw output:

```text
HTTP health check: status=ok, demo_mode=True
......                                                                   [100%]
6 passed in 0.42s
All checks passed!
```

Try it yourself:

1. `python run.py`
2. In another PowerShell window, run `Invoke-RestMethod http://127.0.0.1:8000/healthz`.
3. Open `http://127.0.0.1:8000/` and confirm the `DEMO MODE` banner.

Stubs / not verified live / deviations:

- The supplied `WisprFlow.zip` was not found, so prior-build runtime defects could not be independently rerun.
- Docker, Chrome/Chromium, and Playwright browser availability were not verified because those tools are absent.
- `/v1/stt` remains an explicit typed-input demo fallback; it is listed in `STUBS.md`.
- The existing six tests are only the pre-Phase-0 suite; all later phase gates remain unimplemented.
- The fixed decision to use plain FastAPI/static files instead of React/Vite is recorded in `DECISIONS.md`.

Next: Phase 1. Reply `continue`.
