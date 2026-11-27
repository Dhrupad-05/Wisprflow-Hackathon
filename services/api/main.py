import json
import os
import time
import uuid
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel
from typing import Literal
from dotenv import load_dotenv

from .dialog import handle
from .entities import detect_language
from .stt import STTRequest, transcribe
from .tts import TTSError, synthesize
from .security import SecurityMiddleware, masked_log_text

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
WEB = ROOT / "apps/web"
PORTALS = ROOT / "packages/registries/portals"
MOCK_PORTALS = ROOT / "apps/mock-portals"
app = FastAPI(title="Bolo Sahayak API")
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
    return {"status": "ok", "demo_mode": not bool(os.getenv("XAI_STT_API_KEY"))}


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


@app.get("/styles.css")
def css():
    return FileResponse(WEB / "styles.css")


@app.get("/i18n/{language}.json")
def prompts(language: str):
    if language not in {"en", "hi", "bn"}:
        raise HTTPException(404, "Language not found")
    return FileResponse(ROOT / "packages/i18n/prompts" / f"{language}.json")


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
    return {**out, "prompt_lang": session["lang"], "masked_summary": summary}


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
    request = STTRequest(
        audio=body.get("audio", ""),
        language=body.get("language") or body.get("lang_hint"),
        dictionary_context=body.get("dictionary_context", []),
    )
    return await transcribe(request)


@app.post("/v1/tts")
async def tts(body: dict):
    try:
        audio, content_type = await synthesize(
            str(body.get("text", ""))[:4000], body.get("language", "en")
        )
    except TTSError as exc:
        raise HTTPException(503, str(exc)) from exc
    return Response(content=audio, media_type=content_type)
