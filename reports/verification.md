# Verification snapshot

Date: 2026-11-27

- Unit/integration checks: 6 passed, 0 failed (`pytest -q`).
- E1 API flow: 6 turns, states FORM_FILLING → FORM_FILLING → FORM_FILLING → FORM_FILLING → CONFIRMING → SUBMITTED.
- Routing fixture evaluation: 7/7, 100%, confusion matrix emitted by `tests/eval/run_eval.py`.
- Safety checks covered in automated code: explicit confirmation gate, wipe, masked logs, sensitive-field block in extension, fixed origin allow-list, no audio persistence.
- Compile check: `python -m compileall -q services packages` passed.

## Not verified live

- Wispr Flow API: no `WISPR_API_KEY` was present; only the server-side adapter seam and demo fallback were exercised.
- Hosted LLM: no `LLM_API_KEY` was present; deterministic router was exercised.
- Docker, Playwright E1-E7, axe, throttled latency, real MV3 browser interaction, and phone/desktop screenshots were not run in this environment.

## Known limitations

- The current runnable client is a lightweight static PWA shell rather than a bundled React/Vite build.
- The routing fixture is a smoke set of 7 cases, not the full 150-utterance acceptance corpus.
- Mock portal pages are represented by registry schemas and the assistant flow; full visual portal replicas and browser extension E2E are next work.
