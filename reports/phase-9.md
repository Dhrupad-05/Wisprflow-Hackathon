# Phase 9 — documentation, demo, and clean-machine proof

## Built

- Added cross-platform README instructions for Windows PowerShell and macOS/Linux.
- Documented demo mode, Wispr REST configuration, LLM providers, desktop dictation limitations, MV3 extension installation, tests, safety guarantees, and known limitations.
- Replaced the duplicated `.env.example` with a complete, explained server-only configuration template.
- Added automatic `.env` loading through `python-dotenv`.
- Updated the demo script, decisions log, and report index.

## Gate results

| Check | Exact command/process | Result | Evidence |
|---|---|---|---|
| Lint | `ruff check .` | PASS | `All checks passed!` |
| Full suite | `pytest -q` | PASS | `206 passed, 2 warnings` |
| Fresh environment | `python -m venv .venv` and `pip install -r services/api/requirements.txt` in an isolated copy | PASS | Install completed successfully |
| Fresh server | `python run.py` in the isolated copy | PASS | `/healthz` returned `{"status":"ok","demo_mode":true}` |
| Fresh UI E1 | Playwright against the isolated copy | PASS | `clean_machine_e1=PASS`; account and amount iframe values were verified |

## Clean-machine proof

The proof copy was `C:\Users\KIIT\CODING\WisprFlow-phase9-clean-1270697238`. It excluded `.venv`, pytest/ruff caches, and generated screenshots from the source copy. The browser completed the code-mixed Bengali farmer-loan-to-deposit correction flow and verified `account_no=12345678901` and `amount=5000` in the real portal iframe.

## Not verified live

- Wispr, Anthropic, and OpenAI provider calls were not run without credentials.
- Phase 8 axe-core and throttled-CDP checks remain explicitly incomplete, as documented in `reports/phase-8.md`.
- Manual testing with 5–8 target users and native-speaker review were not performed.
