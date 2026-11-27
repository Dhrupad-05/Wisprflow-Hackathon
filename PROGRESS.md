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

## Phase 5b — offline voice path (complete)

- Added `whisper_local`, an on-server faster-whisper adapter (CPU, `int8`, model `small` by default) so voice works with no provider key at all. The model is a lazy process-wide singleton, preloaded in a background startup task; audio is decoded from the base64 16 kHz PCM16 WAV entirely in memory and transcribed with `asyncio.to_thread`.
- The adapter validates audio before loading a model: under 0.3 s, silent (RMS below `WHISPER_SILENCE_RMS`) and non-WAV input return `empty`/`invalid_audio` without a provider call. Hindi/Bengali get a language hint plus an `initial_prompt` built from `dictionary_context` and the bank/scheme registries, with `beam_size=5`, `vad_filter=True` and `condition_on_previous_text=False`.
- Default `STT_ORDER` is now `wispr_api,whisper_local,xai_stt,web_speech,text`. `/v1/health` reports `stt.whisper_local` as `ready`, `loading` or `unavailable`, plus a `whisper` object (`model`, `requested_model`, `downgraded`, `last_latency_ms`, `installed`), `voice_ready`, `voice_loading` and `stt_ready`.
- Fixed the client fallback bug: the app no longer starts Web Speech after the local engine heard nothing, and it only starts Web Speech when no server engine is ready, after `releaseMicForRecognition()` closes the barge-in and capture streams and waits for the tracks to end. Every `SpeechRecognition` error gets its own code and copy, is logged raw to the console, and appears in a details line.
- Replaced the duplicated red error text with one `role="alert"` banner (light text on dark red, left accent, dismiss button) that clears on the next successful capture. Added a collapsed **Voice diagnostics** panel (browser, secure context, device, peak level, server engines, last STT adapter/error/errors/tried/text length) with copy-to-clipboard.
- Added `scripts/stt_selftest.py` and `tests/test_whisper_local.py` (fake model + Playwright fake-audio capture); added `WHISPER_*` configuration and documentation; added `WHISPER_ENABLED=0` for the test suite so it never downloads a model.
- Decoding note: faster-whisper 1.1.1 cannot open files through `av 19` (`metadata_errors`), so the adapter feeds a mono float32 16 kHz NumPy array instead of a file-like object. This also removes any second decoder from the audio path.

### Gate evidence

- `ruff check .`: `All checks passed!`
- `pytest -q`: `258 passed, 3 warnings` (was 242 before this phase)
- `pytest -q tests/test_whisper_local.py`: `16 passed`
- Live `/v1/health` on `127.0.0.1:8000`: `"whisper_local":"ready"`, `"voice_ready":true`, model `small`, `downgraded:false`
- Live selftest (`scripts/stt_selftest.py` with a synthesized 4.4-second English utterance, local engine): transcript `Please deposit 5,000 rupees in my state bank account.` with `adapter=whisper_local`, `error_code=null`.
- Playwright with `--use-fake-device-for-media-stream` and `--use-file-for-fake-audio-capture=tests/fixtures/hello_hi.wav` asserts the transcript appears in “What I heard” via the whisper path and diagnostics shows `whisper_local`.

### Measured latency (CPU, model `small`, `int8`, 4.4 s utterance)

| Run | STT adapter | `/v1/stt` round trip |
|---|---|---|
| 1 | 2777 ms | 2841 ms |
| 2 | 2588 ms | 2625 ms |
| 3 | 2477 ms | 2532 ms |
| 4 | 2494 ms | 2533 ms |

Median STT latency is **2.49 s**, worst observed 2.78 s, both inside the 3 s target for utterances up to 8 s. A detached `/v1/turn` after transcription adds **~23 ms**, so end-of-speech to the next prompt is ~2.5 s. The auto-downgrade to `base` (when a short utterance exceeds 3 s and `WHISPER_MODEL` is not pinned) did not trigger in these runs.

### Open issues

- Real human microphone and real Hindi/Bengali speech were not used; the browser gate uses a synthetic WAV and a fake model, and the live selftest used Windows TTS English.
- Live Wispr round trip is still unverified (`WISPR_API_KEY` absent); the local xAI STT key is rejected by the provider (`unauthorized`), so rotate it.
- axe-core was not re-run after the new banner and diagnostics panel; the existing markup/touch-target checks pass.
- The first-ever run downloads the `small` model (~500 MB) before health shows `ready`; `/v1/health` reports `loading` until then and the UI chip polls.
