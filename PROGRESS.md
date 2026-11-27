# Progress

## Phase 0 — complete

- Added the single-process FastAPI entrypoint, `/healthz`, and `python run.py`.
- Added environment, audit, decisions, and stub tracking documents.
- Added ruff, pytest, and GitHub Actions configuration.
- Reproduced the available current-build checks; the original `WisprFlow.zip` was not present in the supplied locations.

### Run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r services/api/requirements.txt
python run.py
Invoke-RestMethod http://127.0.0.1:8000/healthz
```

### Open issues

- Phases 1–8 are not started.
- Docker and browser-based gates are not verified on this machine because Docker and Chrome/Chromium were not found.
- The current six legacy tests are not the Phase 1+ acceptance suite.

## Phase 1 — complete

- Replaced the prototype entity parser with multilingual amount and digit parsing.
- Added whole-word command matching, fuzzy bank/scheme resolvers, and sensitive redaction.
- Added registry-backed low-confidence routing and PM-KISAN support.
- Expanded the bank registry to 13 entries and added translated portal OTP labels.
- Added `tools/validate_registries.py` and a 144-case Phase 1 NLU suite.

### Gate evidence

- `ruff check .`: `All checks passed!`
- `pytest -q`: `150 passed, 1 warning`
- `python tools/validate_registries.py`: `Registry validation passed: 5 portals, 12+ banks, translated prompts present.`

### Open issues

- Phase 2 dialog state machine and registry-driven form engine are not started.

## Phase 2 — complete

- Added explicit `State`/event transition table with illegal-transition errors.
- Added registry-driven field parsing, read-back, confirmation, validation, summary, and actions.
- Added bank narrowing, safe-entity rerouting, privacy checkpoint, sensitive user-input handling, and session wipe behavior.
- Added `trigger` validation and pause handling; pauses cannot submit or advance sensitive fields.
- Added E1–E7-style integration and safety tests, including four E1 language variants.

### Gate evidence

- `ruff check .`: `All checks passed!`
- `pytest -q -s`: `163 passed, 1 warning`
- `pytest -q -s tests/test_phase2.py`: `13 passed, 1 warning`

### Open issues

- Phase 3 mock portal HTML pages and Playwright consistency/e2e tests are not started.

## Phase 3 — complete

- Added five responsive multi-step demo portals under `/mock/`.
- Added same-origin `FILL_FIELD`, `HIGHLIGHT`, and `PING` bridge handling that refuses sensitive fields.
- Added stable field metadata, OTP autocomplete, review, validation, and success states.
- Added registry/HTML consistency tests and Playwright browser flows with screenshots at both required widths.
- Installed and verified the Playwright Chromium browser in this environment.

### Gate evidence

- `ruff check .`: `All checks passed!`
- `pytest -q`: `170 passed, 3 warnings`
- `pytest -q tests/test_phase3.py -s`: `7 passed, 3 warnings`
- Screenshots: 10 files in `reports/screenshots/`, visually reviewed.

### Open issues

- The in-app browser surface could not reach the Windows localhost process due to host-network isolation; Python Playwright against the live server passed all portal flows.
- Phase 5 endpointing/STT is not started.

## Phase 4 — complete

- Replaced the prototype web client with a typed-input, consent-gated assistant UI using plain ES modules.
- Added i18n-loaded English/Hindi/Bengali UI strings, responsive assistant/portal layout, large voice/status control, quick replies, private mode masking, slow-speaker toggle, forget-everything, and formatted masked-log printing.
- Added same-origin iframe action execution for opening portals, filling non-sensitive fields, focusing OTP, showing summaries, and submitting only after final confirmation.
- Corrected the portal bridge parent-source validation and added interaction serialization so rapid clicks cannot race turns.
- Added live E1–E7-style browser checks and six responsive language screenshots.

### Gate evidence

- `ruff check . --fix`: `All checks passed!`
- `pytest -q tests/test_phase4.py`: `8 passed, 2 warnings`
- `pytest -q`: `178 passed, 2 warnings`
- Screenshot review: `reports/screenshots/phase4-{en,hi,bn}-{390,1280}.png`, visually reviewed.

### Open issues

- Phase 5 endpointing/STT is complete; the live Wispr round trip remains unverified because `WISPR_API_KEY` is absent.

## Phase 5 — complete

- Added a pure JavaScript endpointing engine with injectable clock/timers, per-field thresholds, slow-speaker multiplier, end words, connector extension, pause read-back trigger, and low-confidence re-asks.
- Added browser WAV capture with microphone permission, PCM16 conversion, 16 kHz resampling, energy callbacks, and a fallback path.
- Added server-side Wispr REST adapter, normalized errors, dictionary context, adapter ordering via `STT_ORDER`, and demo text fallback. Audio is not persisted or logged.
- Added fake-clock, mocked HTTP, adapter fall-through, and Chromium fake-microphone tests.

### Gate evidence

- `ruff check .`: `All checks passed!`
- `pytest -q tests/test_phase5.py`: `8 passed, 2 warnings`
- `pytest -q`: `186 passed, 2 warnings`
- Live Wispr Hindi/Bengali round trip: Not verified live; `WISPR_API_KEY` is missing.

### Open issues

- Phase 6 browser extension is not started.

## Phase 6 — complete

- Added MV3 background service worker, action/side-panel wiring, connection state, current portal, allow-list, and last-fill display.
- Added registry-generated host allow-list via `tools/build_extension.py`.
- Added content-script relay for assistant messages and native input/change events.
- Added DOM-derived sensitivity checks for OTP/PIN/password/CVV/Aadhaar/passcode, password inputs, one-time-code autocomplete, `data-sensitive`, and labels/metadata.
- Added unpacked-extension Chromium tests for allowed origins, sensitive refusal, claimed non-sensitive OTP refusal, and unlisted origins.

### Gate evidence

- `ruff check .`: `All checks passed!`
- `python tools/build_extension.py`: generated 2 allowed hosts.
- `pytest -q tests/test_phase6.py`: `3 passed, 2 warnings`
- `pytest -q`: `189 passed, 2 warnings`

### Open issues

- Phase 8 implementation is complete, but its hard gate remains incomplete because axe-core and throttled CDP performance verification were unavailable; Phase 9 proceeded at the user's request.

## Phase 9 — complete

- Rewrote `README.md` for Windows PowerShell and macOS/Linux, with and without provider keys, Wispr server-side STT, desktop-dictation limitations, extension installation, tests, safety, and known limitations.
- Cleaned and documented `.env.example`, added automatic `.env` loading, and documented every configuration variable.
- Updated `DECISIONS.md`, `DEMO_SCRIPT.md`, and `reports/README.md`.
- Fresh-copy proof used `C:\Users\KIIT\CODING\WisprFlow-phase9-clean-1270697238`, excluding the source venv and caches; dependencies installed successfully, health returned demo mode, and browser E1 completed with real iframe values.

### Gate evidence

- `ruff check .`: `All checks passed!`
- `pytest -q`: `206 passed, 2 warnings`
- Clean-copy health: `{"status":"ok","demo_mode":true}`
- Clean-copy browser E1: `clean_machine_e1=PASS`

## Phase 8 — implementation complete; gate incomplete

- Added centralized PII redaction for log output, strict security headers/CSP, same-origin-only browser access, configurable rate limiting, no-store API responses, and safe 500 handling.
- Added blocking safety coverage for sensitive-field refusal, log/session redaction, origin allow-listing, explicit confirmation, pause behavior, private summaries, wipe, audio non-persistence, prompt injection, and repository/browser secret scanning.
- Added TRD error-path coverage and a 50-concurrent-session benchmark; the measured local p95 turn latency was below the 2.5-second budget.
- Raised browser touch targets to 56px and verified keyboard/ARIA contracts in the web markup.

### Gate evidence

- `ruff check .`: `All checks passed!`
- `pytest -q tests/test_phase8.py`: `12 passed, 1 warning`
- `pytest -q`: `205 passed, 2 warnings`
- Full axe-core scan: not verified; axe-core is not installed in this environment. The existing Playwright accessibility contract and touch-target checks passed.

## Phase 7 — complete

- Added provider-neutral `LLMClient`, Anthropic Messages and OpenAI-compatible adapters, mock client, strict Pydantic structured output, one invalid-response retry, 1.5-second client timeouts, and deterministic keyword fallback.
- Added prompt safeguards treating user utterances as data, with intent-tree/few-shot guidance and native-script clarification support.
- Added 224-row multilingual evaluation fixture: 56 English, 56 Hindi, 56 Bengali, and 56 code-mixed rows; each domain has at least 25 rows and each language has at least 40 rows, split evenly into dev/test.
- Added evaluator JSON, Markdown, and confusion-matrix CSV outputs under `reports/`.

### Gate evidence

- `ruff check .`: `All checks passed!`
- `python tests/eval/run_eval.py --split test`: 91.96% exact accuracy; 100% named-entity accuracy (9 named-entity test rows).
- `pytest -q`: `194 passed, 2 warnings`
- `LLM_API_KEY`: absent; production path uses deterministic fallback. Live LLM provider verification: not run.
