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

Open <http://127.0.0.1:8000>. The page shows `DEMO MODE` when provider keys are absent. Typed input and mock portals work without keys.

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
| `STT_ORDER` | Comma-separated adapter order, default `wispr_api,xai_stt,web_speech,text`. Empty keys, errors, timeouts, unsupported languages and empty transcripts all fall through. |
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

With a Wispr or xAI key, `/v1/stt` sends the captured 16 kHz WAV to that server-side adapter and `/v1/tts` returns provider audio to the browser without exposing the key. With no key, `/v1/stt` answers `{text: "", adapter: "text", demo_mode: true, error_code: "empty"}` and the browser automatically starts its own Web Speech recognizer with the same endpointing before showing any "type below" hint.

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
| Level meter moves but text stays empty | No server speech key, so it is in DEMO MODE. | Add `WISPR_API_KEY` (or `XAI_STT_API_KEY`) to `.env`, restart `python run.py`; the chip turns green. |
| "The speech key was rejected" | Provider key is wrong or expired. | Rotate the key in the provider console and update `.env`. |
| "The speech service could not be reached" | Offline, firewall, or provider outage. | The app falls back to browser Web Speech, then to typed input. |
| Level meter never moves | Another app holds the mic, or the input is muted. | Close the other app, unmute, and re-run **Mic test**. |
| Status stays on "Thinking…" | A provider call is slow. | Wait for the 20 s timeout; the app then shows the reason and falls back. |

Diagnostics: `curl http://127.0.0.1:8000/v1/health` (or open it in the browser). The server also prints a startup banner saying whether voice is enabled or the app is in DEMO MODE.

## Three-minute demo

Follow [DEMO_SCRIPT.md](DEMO_SCRIPT.md). The shortest path is: consent, type `Ami chashi amar loan lagbe`, choose `SBI`, change to `Na, taka jama dite chai`, enter the account digits and amount, confirm with `haan`, type the demo OTP directly in the portal, and say `ho gaya`.

## Desktop dictation and extension

The UI captures 16 kHz PCM16 WAV through an `AudioWorklet` (with a `ScriptProcessor` fallback), stops on energy-based endpointing instead of a fixed timer, and shows a live level meter, engine badge, and a three-second mic test. Capture falls through Wispr Flow → optional xAI → browser Web Speech → typed input, and every degradation has a plain-language reason on screen. Load `apps/extension` as an unpacked MV3 extension in Chrome/Chromium for allow-listed mock-origin field filling. It refuses OTP, PIN, password, CVV, Aadhaar, and unlisted origins.

See [docs/voice-providers.md](docs/voice-providers.md) for the server-only key mapping and pipeline.

## Safety and limitations

OTP, PIN, password, CVV, and full Aadhaar are never captured by voice, auto-filled, stored, or logged. Submission requires an explicit yes in the user’s language. `forget everything` wipes the in-memory session.

Known limitations are listed in `reports/phase-8.md`: live xAI/Gemini calls, axe-core scanning, and throttled CDP performance verification were not run in this environment.
