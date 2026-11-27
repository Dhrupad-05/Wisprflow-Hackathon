# Voice pipeline migration

## Change

The browser voice path now uses:

`microphone → WAV → /v1/stt → xAI STT → /v1/turn → /v1/tts → xAI TTS → browser audio`

Wispr adapters and Wispr environment intake were removed. Gemini is the primary LLM router, followed by xAI-compatible, OpenRouter, and last-resort xAI-compatible clients. All credentials are server-side environment variables.

## Verification

- `ruff check .`: passed
- `pytest -q`: `208 passed, 2 warnings`
- Mock xAI multipart STT test: passed
- Mock TTS missing-key fallback test: passed
- Live endpoint smoke requests reached both xAI endpoints, but both returned HTTP 400 with `Incorrect API key provided`. The supplied credentials were cleared from the user environment and should be rotated/replaced before live voice testing.

No key values are stored in the repository, browser bundle, reports, or local `.env`.
