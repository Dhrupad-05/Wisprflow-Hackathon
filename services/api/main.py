import json
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel
from typing import Literal
from dotenv import load_dotenv

from .dialog import choices, handle, helper_sheet, input_hint, pending_readback, progress
from .entities import detect_language
from .stt import STTError, STTRequest, stt_order, transcribe
from .tts import TTSError, synthesize
from .security import SecurityMiddleware, masked_log_text

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
WEB = ROOT / "apps/web"
PORTALS = ROOT / "packages/registries/portals"
MOCK_PORTALS = ROOT / "apps/mock-portals"


def provider_status() -> dict:
    stt = {
        "wispr_api": bool(os.getenv("WISPR_API_KEY")),
        "xai_stt": bool(os.getenv("XAI_STT_API_KEY")),
    }
    order = stt_order()
    voice_ready = any(stt.get(name) for name in order)
    return {
        "status": "ok",
        "demo_mode": not voice_ready,
        "voice_ready": voice_ready,
        "stt": stt,
        "stt_order": order,
        "llm": {
            "gemini": bool(os.getenv("GEMINI_API_KEY")),
            "xai": bool(os.getenv("XAI_LLM_API_KEY")),
            "openrouter": bool(os.getenv("OPENROUTER_API_KEY")),
            "fallback": bool(os.getenv("XAI_FALLBACK_API_KEY")),
        },
        "tts": {"xai_tts": bool(os.getenv("XAI_TTS_API_KEY"))},
        "browser_voice": "web_speech" in order,
    }


@asynccontextmanager
async def lifespan(_app):
    status = provider_status()
    if status["voice_ready"]:
        engines = [name for name, ready in status["stt"].items() if ready]
        print(f"[Bolo Sahayak] voice enabled via {', '.join(engines)}; STT_ORDER={','.join(status['stt_order'])}", flush=True)
    else:
        print(
            "[Bolo Sahayak] DEMO MODE: no speech-to-text key found. Typed input and browser Web Speech still work. "
            "Set WISPR_API_KEY (or XAI_STT_API_KEY) in .env to enable server voice.",
            flush=True,
        )
    yield


app = FastAPI(title="Bolo Sahayak API", lifespan=lifespan)
app.add_middleware(SecurityMiddleware)
sessions = {}
TTL = int(os.getenv("SESSION_TTL_SECONDS", "1800"))


class Start(BaseModel):
    lang_hint: str | None = None
    private_mode: bool = False


class Turn(BaseModel):
    session_id: str
    transcript: str
    lang_hint: str | None = None
    private_mode: bool = False
    trigger: Literal["typed", "end_word", "pause", "tap"] = "typed"


@app.get("/healthz")
def healthz():
    status = provider_status()
    return {"status": status["status"], "demo_mode": status["demo_mode"]}


@app.get("/v1/health")
def health():
    """Which server-side voice, LLM, and TTS engines are configured."""

    return provider_status()


def clean():
    now = time.time()
    for key, value in list(sessions.items()):
        if now - value.get("expires", 0) > TTL:
            sessions.pop(key, None)


@app.get("/", response_class=HTMLResponse)
def home():
    return FileResponse(WEB / "index.html")


@app.get("/app.js")
def js():
    return FileResponse(WEB / "app.js")


@app.get("/audio.js")
def audio_js():
    return FileResponse(WEB / "audio.js")


@app.get("/packages/voice/endpointing.js")
def endpointing_js():
    return FileResponse(ROOT / "packages/voice/endpointing.js")


@app.get("/packages/voice/vad.js")
def vad_js():
    return FileResponse(ROOT / "packages/voice/vad.js")


@app.get("/packages/voice/bargein.js")
def bargein_js():
    return FileResponse(ROOT / "packages/voice/bargein.js")


@app.get("/audio-worklet.js")
def audio_worklet():
    return FileResponse(WEB / "audio-worklet.js", media_type="text/javascript")


@app.get("/styles.css")
def css():
    return FileResponse(WEB / "styles.css")


@app.get("/i18n/{language}.json")
def prompts(language: str):
    if language not in {"en", "hi", "bn"}:
        raise HTTPException(404, "Language not found")
    return FileResponse(ROOT / "packages/i18n/prompts" / f"{language}.json")


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(WEB / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker():
    return FileResponse(WEB / "sw.js", media_type="text/javascript")


@app.get("/icons/{name}")
def icon(name: str):
    if name not in {"icon-192.png", "icon-512.png"}:
        raise HTTPException(404, "Icon not found")
    return FileResponse(WEB / "icons" / name, media_type="image/png")


@app.get("/mock/portal.css")
def mock_css():
    return FileResponse(MOCK_PORTALS / "portal.css")


@app.get("/mock/portal.js")
def mock_js():
    return FileResponse(MOCK_PORTALS / "portal.js")


@app.get("/mock/portal-bridge.js")
def mock_bridge():
    return FileResponse(MOCK_PORTALS / "portal-bridge.js")


@app.get("/mock/sbi/deposit", response_class=HTMLResponse)
def mock_sbi():
    return FileResponse(MOCK_PORTALS / "sbi-deposit.html")


@app.get("/mock/kcc", response_class=HTMLResponse)
def mock_kcc():
    return FileResponse(MOCK_PORTALS / "kcc.html")


@app.get("/mock/pension", response_class=HTMLResponse)
def mock_pension():
    return FileResponse(MOCK_PORTALS / "pension.html")


@app.get("/mock/ration", response_class=HTMLResponse)
def mock_ration():
    return FileResponse(MOCK_PORTALS / "ration.html")


@app.get("/mock/udyam", response_class=HTMLResponse)
def mock_udyam():
    return FileResponse(MOCK_PORTALS / "udyam.html")


@app.post("/v1/session")
def start(body: Start):
    sid = uuid.uuid4().hex
    lang = body.lang_hint or "en"
    sessions[sid] = {
        "session_id": sid,
        "lang": lang,
        "state": "IDLE",
        "entities": {},
        "log": [],
        "private_mode": body.private_mode,
        "filled_fields": {},
        "expires": time.time() + TTL,
    }
    return {
        "session_id": sid,
        "consent_text": "Demo mode: audio is sent only to the configured speech provider. OTP and passwords are always typed by you.",
        "prompt_text": "Bolun, ki lagbe? / Aap kya chahte hain?",
        "state": "IDLE",
        "progress": progress(sessions[sid]),
        "choices": choices(sessions[sid]),
    }


@app.post("/v1/turn")
def turn(body: Turn):
    clean()
    session = sessions.get(body.session_id)
    if not session:
        raise HTTPException(404, "Session expired")
    session["expires"] = time.time() + TTL
    session["lang"] = detect_language(
        body.transcript, body.lang_hint or session.get("lang")
    )
    session["private_mode"] = body.private_mode
    out = handle(session, body.transcript, session["lang"], body.trigger)
    session["log"].append(
        {
            "state": out["state"],
            "heard": "[masked]",
            "prompt": masked_log_text(out["prompt_text"]),
        }
    )
    actions = out.get("actions", [])
    summary = actions[-1].get("masked_summary") if actions else None
    return {
        **out,
        "prompt_lang": session["lang"],
        "masked_summary": summary,
        "field_type": input_hint(session),
        "progress": progress(session),
        "choices": choices(session),
        "readback": pending_readback(session),
    }


@app.get("/v1/session/{sid}/helper")
def helper(sid):
    """Printable, value-free checklist for a helper sitting beside the user."""

    session = sessions.get(sid)
    if not session:
        raise HTTPException(404, "Session expired")
    return helper_sheet(session)


@app.get("/v1/portals/{portal_id}")
def portal(portal_id):
    p = PORTALS / f"{portal_id}.json"
    if not p.exists():
        for candidate in PORTALS.glob("*.json"):
            if portal_id in candidate.read_text(encoding="utf-8").lower():
                p = candidate
                break
    if not p.exists():
        raise HTTPException(404, "Demo portal not found")
    return json.loads(p.read_text(encoding="utf-8"))


@app.post("/v1/session/{sid}/wipe")
def wipe(sid):
    sessions.pop(sid, None)
    return {"wiped": True}


@app.get("/v1/session/{sid}/log")
def log(sid):
    session = sessions.get(sid)
    if not session:
        raise HTTPException(404, "Session expired")
    return {
        "session_id": sid,
        "events": session["log"],
        "private_mode": session["private_mode"],
    }


@app.post("/v1/stt")
async def stt(body: dict):
    try:
        request = STTRequest(
            audio=body.get("audio", ""),
            language=body.get("language") or body.get("lang_hint"),
            dictionary_context=body.get("dictionary_context", []),
        )
        request.audio_bytes  # reject bad base64/oversized audio before any provider call
        return await transcribe(request)
    except STTError as exc:
        return {"text": "", "adapter": "none", "error_code": exc.code, "errors": [{"adapter": "request", "error": exc.code}], "tried": []}


@app.post("/v1/tts")
async def tts(body: dict):
    try:
        audio, content_type = await synthesize(
            str(body.get("text", ""))[:4000], body.get("language", "en")
        )
    except TTSError as exc:
        raise HTTPException(503, str(exc)) from exc
    return Response(content=audio, media_type=content_type)
