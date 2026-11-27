# PHASE 5 REPORT

Built:

- Added `packages/voice/endpointing.js`, a pure endpointing engine with injectable clock/timers for deterministic tests.
- Implemented 1.2s short-answer, 2.5s amount/name, and 3.0s digit thresholds; 1.5x slow mode; language end words; trailing connector extension; pause and low-confidence handling.
- Added browser microphone capture, PCM16 WAV encoding, 16 kHz resampling, and `/v1/stt` submission. Audio is streamed to the adapter and not stored.
- Added `WisprApiAdapter` using the documented bearer-auth REST request with `audio`, `language`, and `context.dictionary_context`; normalized missing-key, unauthorized, timeout, unsupported-language, and size errors.
- Added adapter fall-through controlled by `STT_ORDER`, with unavailable desktop/Web Speech seams and a demo text fallback.
- Updated `WISPR_API_URL` to the current REST endpoint in `.env.example`.

Gate results:

| Check | Exact command | Result | Evidence |
|---|---|---|---|
| Ruff | `ruff check .` | PASS | `All checks passed!` |
| Phase 5 gate | `pytest -q tests/test_phase5.py` | PASS | `8 passed, 2 warnings`; fake-clock, HTTP mock, fallback, and fake-mic browser checks. |
| Full regression | `pytest -q` | PASS | `186 passed, 2 warnings` |
| Live Wispr round trip | Hindi + Bengali sample WAV | Not verified live | `WISPR_API_KEY` is not present in the environment. |

The REST payload follows the current Wispr documentation: base64 16 kHz WAV, optional one-language list, and `context.dictionary_context` ([REST API](https://api-docs.wisprflow.ai/rest_api_transcribe), [request schema](https://api-docs.wisprflow.ai/request_schema)).

Notes:

- The browser uses the REST path first; WebSocket streaming remains optional and is deferred until the REST path is live-verified.
- No API key is exposed to browser code or returned by the proxy.

Next: Phase 6. Reply `continue`.
