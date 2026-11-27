# Voice provider setup

The browser never receives provider credentials. Set these variables in `.env` on the server:

```bash
WISPR_API_KEY=<Wispr Flow API key for speech-to-text>
XAI_STT_API_KEY=<optional alternate speech-to-text key>
XAI_TTS_API_KEY=<xAI key for text-to-speech>
GEMINI_API_KEY=<primary routing key>
XAI_LLM_API_KEY=<alternate Grok-compatible routing key>
OPENROUTER_API_KEY=<fallback routing key>
XAI_FALLBACK_API_KEY=<last-resort Grok-compatible routing key>
```

The pipeline is:

`microphone → AudioWorklet PCM16 16 kHz WAV → POST /v1/stt → wispr_api → xai_stt (optional) → web_speech marker → text`

* **Wispr Flow** (`platform-api.wisprflow.ai/api/v1/dash/api`, bearer API key, JSON body with base64 16 kHz PCM16 WAV, an ISO 639-1 `language` array and a `context` object) is the primary engine. See <https://api-docs.wisprflow.ai/rest_api_transcribe>.
* **xAI** is optional and kept for comparison; it is skipped when its key is absent.
* **web_speech** is a marker: the server cannot run it, so it answers `client_side` and the browser starts `webkitSpeechRecognition` with the same endpointing.
* **text** is the demo terminal: `{text: "", adapter: "text", demo_mode: true, error_code: "empty"}`.

`STT_ORDER` controls the chain and every step falls through on a missing key, error, timeout, unsupported language, or an empty transcript. `/v1/stt` always answers `{text, adapter, error_code, errors, tried}` so the UI can show an engine badge and a plain-language reason instead of a silent failure.

`GET /v1/health` returns booleans for every configured engine, the active order, and `voice_ready`. The UI shows the same state as a chip and a startup banner is printed by the server.

## What is verified

* Wispr request/response shape is implemented from the published REST docs and covered with mocked HTTP tests.
* A live Wispr call requires `WISPR_API_KEY`; without it the chain reports `missing_key` and the browser uses Web Speech or typed input.
* A live xAI call was attempted with the local `.env` key and the provider answered HTTP 400 "Incorrect API key provided". That is normalized to `unauthorized`, surfaced on screen, and falls through — rotate the key in the xAI console if that engine is wanted.

Because credentials were pasted into a chat, rotate them in the provider consoles if they are real production keys, then place only replacement values in the local ignored `.env` file.
