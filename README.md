# Bolo Sahayak

Bolo Sahayak is a demo-safe, voice-first assistant for Bengali, Hindi, English, and code-mixed users. It routes requests, fills mock portals, and keeps OTPs and other authentication secrets with the user.

## Quick start — Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r services/api/requirements.txt
Copy-Item .env.example .env
python run.py
```

Open <http://127.0.0.1:8000>. Voice works without any provider key: the server runs `faster-whisper` on the CPU and downloads the `small` model (~500 MB) on first use. The page shows `Voice engine loading…` until it is ready, then `Voice ready: Local voice`. Typed input and mock portals always work.

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process Bypass` and activate again. You can also run `.venv\Scripts\python.exe run.py` without activating.

## Quick start — macOS/Linux

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r services/api/requirements.txt
cp .env.example .env
python run.py
```

Open <http://127.0.0.1:8000>. Python 3.11 or newer is required. Docker is optional; the normal run path needs only Python.

## Configuration

Copy `.env.example` to `.env`. `.env` is server-only and is ignored by Git. Empty provider keys intentionally select demo fallbacks.

| Variable | Purpose |
|---|---|
| `APP_ENV` | `demo` or deployment environment label. |
| `WISPR_API_KEY` | Server-only Wispr Flow API key (primary speech engine). |
| `WISPR_API_URL` | Wispr REST endpoint, default `https://platform-api.wisprflow.ai/api/v1/dash/api`. |
| `WISPR_TIMEOUT_SECONDS` | Wispr request timeout, default `20`. |
| `XAI_STT_API_KEY` | Optional server-only xAI speech-to-text key. |
| `XAI_STT_API_URL` | xAI `/v1/stt` endpoint. |
| `XAI_STT_MODEL` | xAI transcription model. |
| `XAI_TTS_API_KEY` | Server-only xAI text-to-speech key. |
| `XAI_TTS_API_URL` | xAI `/v1/tts` endpoint. |
| `XAI_TTS_VOICE` | xAI voice id, default `eve`. |
| `WHISPER_MODEL` | Local model size, default `small` (`base` is faster, `tiny` is a quick smoke test). Auto-downgrades to `base` when a short utterance takes over 3 s unless this variable is set explicitly. |
| `WHISPER_MODEL_DIR` | Optional download/cache directory for the model. |
| `WHISPER_DEVICE` / `WHISPER_COMPUTE_TYPE` | Default `cpu` / `int8`. |
| `WHISPER_ENABLED` | `1` (default) enables the offline engine; `0` reports it as unavailable. |
| `WHISPER_PRELOAD` | `1` (default) warms the model at startup in the background. |
| `WHISPER_AUTO_DOWNGRADE` | `1` (default) drops `small` to `base` after a slow short utterance. |
| `STT_ORDER` | Comma-separated adapter order, default `wispr_api,whisper_local,xai_stt,web_speech,text`. Empty keys, errors, timeouts, unsupported languages and empty transcripts all fall through. |
| `GEMINI_API_KEY` | Primary server-only Gemini routing key. |
| `GEMINI_MODEL` | Gemini routing model. |
| `XAI_LLM_API_KEY` | Alternate server-only Grok-compatible routing key. |
| `XAI_LLM_MODEL` | Alternate Grok-compatible routing model. |
| `OPENROUTER_API_KEY` | Fallback server-only OpenRouter key. |
| `OPENROUTER_MODEL` | Fallback OpenRouter model. |
| `SESSION_TTL_SECONDS` | In-memory session lifetime. |
| `RATE_LIMIT_PER_MINUTE` | Per-client HTTP request limit; default is 1000 for the demo. |
| `ALLOWED_ORIGINS` | Documentation/configuration value for deployment origin policy; the app itself does not enable permissive CORS. |
| `LOG_LEVEL` | Process log level. |

`GET /v1/health` reports which engines are configured (`stt`, `llm`, `tts` booleans), the active `stt_order`, and whether voice is ready. The UI shows the same state as a chip plus an engine badge (Wispr / Server voice / Web Speech / Typed / Demo).

With no provider key, `/v1/stt` decodes the captured 16 kHz WAV in memory and transcribes it with `faster-whisper` (`small`, CPU, `int8`) — audio is never written to disk or logged. With a Wispr key, Wispr is tried first; whisper is the fallback. `/v1/tts` returns provider audio to the browser without exposing any key.

The browser only opens its own Web Speech recognizer when the server has no working engine. If `whisper_local` ran and legitimately heard nothing, the app asks the user to try the same microphone again instead of starting a second microphone session. `/v1/health` reports `whisper_local` as `ready`, `loading` or `unavailable`.

## Tests and evaluation

```powershell
ruff check .
pytest -q
python tests/eval/run_eval.py --split test
```

```bash
ruff check .
pytest -q
python tests/eval/run_eval.py --split test
```

The mock portals are served by the same FastAPI process under `/mock/*`. They are not real bank or government sites. The unpacked MV3 extension is in `apps/extension`; generate its host list with `python tools/build_extension.py`.

## Microphone troubleshooting

Open the app at `http://127.0.0.1:8000` (localhost is a secure context). Use the **Mic test** button: it records for three seconds and reports *Mic OK*, *no sound detected*, or a specific permission/device error.

| Symptom | Cause | Fix |
|---|---|---|
| "Microphone needs https:// or http://127.0.0.1" | The page is not a secure context (file://, LAN IP over http). | Use `http://127.0.0.1:8000` or https. |
| "Microphone permission is blocked" | Chrome denied the mic for this origin. | Click the padlock in the address bar, allow Microphone, reload. |
| Mic test says "no sound arrived" | Wrong input device or OS-level mic privacy block. | Pick the right device in the mic dropdown; on Windows check Settings → Privacy → Microphone; on macOS check System Settings → Privacy & Security → Microphone. |
| Level meter moves but text stays empty | The local engine is installed but its model failed to load, or no engine is ready. | Open `Voice diagnostics` at the bottom of the assistant panel; `/v1/health` shows `whisper_local`. Reinstall with `python -m pip install -r services/api/requirements.txt`. |
| "I could not hear speech, please try again" | The local engine transcribed silence (too quiet, wrong device, or a very short clip). | Pick the right input device, tap **Mic test**, then retry. The app does not start a second recognizer here. |
| "The speech key was rejected" | Provider key is wrong or expired. | Rotate the key in the provider console and update `.env`. |
| "The speech service could not be reached" | Offline, firewall, or provider outage. | The app falls back to browser Web Speech, then to typed input. |
| Level meter never moves | Another app holds the mic, or the input is muted. | Close the other app, unmute, and re-run **Mic test**. |
| Status stays on "Thinking…" | A provider call is slow. | Wait for the 20 s timeout; the app then shows the reason and falls back. |

Diagnostics: `curl http://127.0.0.1:8000/v1/health` (or open it in the browser). The server also prints a startup banner saying whether voice is enabled or the app is in DEMO MODE.

## Three-minute demo

Follow [DEMO_SCRIPT.md](DEMO_SCRIPT.md). The shortest path is: consent, type `Ami chashi amar loan lagbe`, choose `SBI`, change to `Na, taka jama dite chai`, enter the account digits and amount, confirm with `haan`, type the demo OTP directly in the portal, and say `ho gaya`.

## Desktop dictation and extension

The UI captures 16 kHz PCM16 WAV through an `AudioWorklet` (with a `ScriptProcessor` fallback), stops on energy-based endpointing instead of a fixed timer, and shows a live level meter, engine badge, and a three-second mic test. Capture falls through Wispr Flow → optional xAI → browser Web Speech → typed input, and every degradation has a plain-language reason on screen. Load `apps/extension` as an unpacked MV3 extension in Chrome/Chromium for allow-listed mock-origin field filling. It refuses OTP, PIN, password, CVV, Aadhaar, and unlisted origins.

- Confirmations are intent-based: one yes advances (pending intent, field, or summary) instead of re-asking; “yes, it is correct”/“haan, sahi hai”/“haan thik ache” all match, and “yes but 40,000”/“no, SBI” counts as a correction.
- After the intent yes, the server emits `OPEN_SITE {url, portal_id, mode}` from the registry only (`official_url` per bank/scheme/portal); `DEMO_USE_MOCK=true` swaps in the mock URL. The extension opens the tab (`chrome.tabs.create`) and the page offers an “Open site” button if a popup is blocked.
- Official domains are HTTPS and allow-listed end to end: server resolver, generated `allowlist.js`, content script, and service worker. Unknown sites offer up to three registry options.
- On allow-listed pages the extension adds a 56 px Shadow-DOM bubble with idle/listening/thinking/speaking/error states, Yes/No/Repeat/Stop, language, and a typed fallback. Mic capture stays in the extension side panel, and the page is already open, so state continues on the same `session_id`.
- Only a visible-field schema (label, type, options, sensitivity) leaves the page; values never do. Sensitive fields are highlighted and spoken, never filled. Submit is sent only on explicit yes for localhost mock portals.

See [docs/voice-providers.md](docs/voice-providers.md) for the server-only key mapping and pipeline.

## Safety and limitations

OTP, PIN, password, CVV, and full Aadhaar are never captured by voice, auto-filled, stored, or logged. Submission requires an explicit yes in the user’s language. `forget everything` wipes the in-memory session.

Known limitations are listed in `reports/phase-8.md`: live xAI/Gemini calls, axe-core scanning, and throttled CDP performance verification were not run in this environment.
