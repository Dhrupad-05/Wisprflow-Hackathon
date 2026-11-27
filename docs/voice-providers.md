# Voice provider setup

The browser never receives provider credentials. Everything below is server-side
configuration in `.env`.

```bash
# Offline default. No key required; the model is downloaded on first use.
WHISPER_MODEL=small
WHISPER_MODEL_DIR=
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
WHISPER_ENABLED=1
WHISPER_PRELOAD=1
WHISPER_AUTO_DOWNGRADE=1

# Optional cloud engines, tried before whisper when their keys are set.
WISPR_API_KEY=<Wispr Flow API key for speech-to-text>
XAI_STT_API_KEY=<optional alternate speech-to-text key>
XAI_TTS_API_KEY=<xAI key for text-to-speech>

# Routing keys.
GEMINI_API_KEY=<primary routing key>
XAI_LLM_API_KEY=<alternate Grok-compatible routing key>
OPENROUTER_API_KEY=<fallback routing key>
XAI_FALLBACK_API_KEY=<last-resort Grok-compatible routing key>
```

## Pipeline

`microphone → AudioWorklet PCM16 16 kHz WAV → POST /v1/stt → wispr_api → whisper_local → xai_stt → web_speech marker → text`

* **whisper_local** is the offline default. `faster-whisper` runs on the server's
  CPU (`small`, `int8`), the model is a lazy process-wide singleton, and
  transcription runs in a worker thread so the event loop stays responsive. The
  base64 WAV is decoded and validated in memory: durations under 0.3 s, RMS below
  the silence threshold, non-WAV input, and empty results all return
  `error_code: "empty"` or `"invalid_audio"` without loading a model. Audio is
  never written to disk, logged, or sent anywhere but the configured provider.
  `WHISPER_MODEL` defaults to `small`; if a short (≤8 s) utterance takes more than
  3 s on CPU and the model was not pinned explicitly, the adapter downgrades to
  `base` for the next turn and says so in `/v1/health`.
  Code-mixed Hindi/Bengali gets a language hint plus an `initial_prompt` built
  from `dictionary_context` and the bank/scheme registries, with `beam_size=5`,
  `vad_filter=True` and `condition_on_previous_text=False`.
* **Wispr Flow** (`POST https://platform-api.wisprflow.ai/api/v1/dash/api`,
  bearer API key, JSON body with base64 16 kHz PCM16 WAV, an ISO 639-1
  `language` array and a `context` object; 200 response
  `{id, text, detected_language, total_time, generated_tokens}`) is tried first
  when `WISPR_API_KEY` is present. See
  <https://api-docs.wisprflow.ai/rest_api_transcribe>.
* **xAI** is optional and kept for comparison; it is skipped when its key is absent.
* **web_speech** is a marker: the server cannot run it, so it answers
  `client_side`. The browser starts `webkitSpeechRecognition` **only when the
  server has no working engine**, after closing every barge-in and capture
  stream. Every recognizer error (`not-allowed`, `service-not-allowed`,
  `audio-capture`, `no-speech`, `network`, `language-not-supported`, `aborted`,
  `InvalidStateError`) maps to its own code, is logged raw to the console, and
  appears in the small details line under the status.
* **text** is the demo terminal: `{text: "", adapter: "text", demo_mode: true, error_code: "empty"}`.

`STT_ORDER` controls the chain and every step falls through on a missing key,
error, timeout, unsupported language, or an empty transcript. `/v1/stt` always
answers `{text, adapter, error_code, errors, tried, server_engine_ready, whisper}`
so the UI can show an engine badge and a plain-language reason instead of a
silent failure.

## What the browser does with an empty result

1. If `tried` includes `whisper_local` and its error was `empty`, the app shows
   *"I could not hear speech, please try again"* and asks for the same microphone
   again. It does **not** start Web Speech — that would open a second microphone
   session and hide the real cause.
2. If a server engine is ready but the turn was empty for another reason, the app
   shows that reason and keeps the typed fallback.
3. Only when no server engine is ready does it release the capture and barge-in
   streams, wait for the tracks to stop, and start the browser recognizer.

The collapsed **Voice diagnostics** panel shows the browser, secure-context flag,
selected input device, peak level, server engine states, and the last STT response
(adapter, error code, attempted adapters, transcript length), with a copy button.

`GET /v1/health` reports `stt.wispr_api` / `stt.xai_stt` as booleans and
`stt.whisper_local` as `ready`, `loading` or `unavailable`, plus a `whisper`
object (`model`, `requested_model`, `downgraded`, `last_latency_ms`, `installed`),
`voice_ready` and `voice_loading`. The UI shows the same state as a chip and a
startup banner is printed by the server.

## What is verified

* `whisper_local` is covered with a fake model (in-memory WAV, language mapping,
  prompt contents, empty/short/silent/invalid audio, auto-downgrade,
  `engine_unavailable`) and an end-to-end browser test that feeds a bundled WAV
  through Chromium's fake audio device and asserts the transcript appears in
  “What I heard” via the whisper path.
* Wispr's request and documented 200 response shape are covered with mocked HTTP;
  a live call still requires `WISPR_API_KEY`.
* A live xAI call with the local `.env` key answered HTTP 400 "Incorrect API key
  provided"; that is normalized to `unauthorized` and falls through. Rotate that
  key in the xAI console if the engine is wanted.

Because credentials were pasted into a chat, rotate them in the provider consoles
if they are real production keys, then place only replacement values in the local
ignored `.env` file.
