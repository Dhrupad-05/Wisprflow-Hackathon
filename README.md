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
| `XAI_STT_API_KEY` | Server-only xAI speech-to-text key. |
| `XAI_STT_API_URL` | xAI `/v1/stt` endpoint. |
| `XAI_STT_MODEL` | xAI transcription model. |
| `XAI_TTS_API_KEY` | Server-only xAI text-to-speech key. |
| `XAI_TTS_API_URL` | xAI `/v1/tts` endpoint. |
| `XAI_TTS_VOICE` | xAI voice id, default `eve`. |
| `STT_ORDER` | Comma-separated adapter order, normally `xai_stt,text`. |
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

With an xAI key, `/v1/stt` sends the captured WAV to the server-side xAI adapter and `/v1/tts` returns provider audio to the browser without exposing the key. With no key, typed input, browser speech fallback, and mock adapters remain available.

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

## Three-minute demo

Follow [DEMO_SCRIPT.md](DEMO_SCRIPT.md). The shortest path is: consent, type `Ami chashi amar loan lagbe`, choose `SBI`, change to `Na, taka jama dite chai`, enter the account digits and amount, confirm with `haan`, type the demo OTP directly in the portal, and say `ho gaya`.

## Desktop dictation and extension

The UI supports browser microphone capture through the server-side xAI STT adapter and xAI TTS audio playback. Desktop dictation is not required for this pipeline. Load `apps/extension` as an unpacked MV3 extension in Chrome/Chromium for allow-listed mock-origin field filling. It refuses OTP, PIN, password, CVV, Aadhaar, and unlisted origins.

See [docs/voice-providers.md](docs/voice-providers.md) for the server-only key mapping and pipeline.

## Safety and limitations

OTP, PIN, password, CVV, and full Aadhaar are never captured by voice, auto-filled, stored, or logged. Submission requires an explicit yes in the user’s language. `forget everything` wipes the in-memory session.

Known limitations are listed in `reports/phase-8.md`: live xAI/Gemini calls, axe-core scanning, and throttled CDP performance verification were not run in this environment.
