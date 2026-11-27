"""Server-side xAI speech-to-text adapters; audio is never persisted or logged."""

import base64
import os
from dataclasses import dataclass

import httpx


ERRORS = {"missing_key", "unauthorized", "timeout", "unsupported_language", "too_large"}


class STTError(Exception):
    def __init__(self, code: str, detail: str = ""):
        self.code = code if code in ERRORS else "timeout"
        super().__init__(detail or self.code)


@dataclass
class STTRequest:
    audio: str
    language: str | None = None
    dictionary_context: list[str] | None = None

    @property
    def audio_bytes(self) -> bytes:
        try:
            return base64.b64decode(self.audio, validate=True)
        except (ValueError, UnicodeError) as exc:
            raise STTError("too_large", "Invalid audio encoding") from exc


class XaiSttAdapter:
    name = "xai_stt"

    def __init__(self, api_key: str | None = None, api_url: str | None = None, model: str | None = None, client=None):
        self.api_key = api_key if api_key is not None else os.getenv("XAI_STT_API_KEY", "")
        self.api_url = api_url or os.getenv("XAI_STT_API_URL", "https://api.x.ai/v1/stt")
        self.model = model or os.getenv("XAI_STT_MODEL", "grok-voice-transcribe-2.0")
        self.client = client

    async def transcribe(self, request: STTRequest) -> dict:
        if not self.api_key:
            raise STTError("missing_key")
        audio = request.audio_bytes
        if len(audio) > 25 * 1024 * 1024:
            raise STTError("too_large")
        data = {"model": self.model, "format": "true"}
        if request.language:
            data["language"] = request.language
        if request.dictionary_context:
            data["keyterm"] = ", ".join(request.dictionary_context)
        files = {"file": ("speech.wav", audio, "audio/wav")}
        client = self.client or httpx.AsyncClient(timeout=15)
        owns_client = self.client is None
        try:
            try:
                response = await client.post(
                    self.api_url,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    data=data,
                    files=files,
                )
            except httpx.TimeoutException as exc:
                raise STTError("timeout") from exc
        finally:
            if owns_client:
                await client.aclose()
        if response.status_code in {401, 403}:
            raise STTError("unauthorized")
        if response.status_code == 413:
            raise STTError("too_large")
        if response.status_code in {400, 422}:
            raise STTError("unsupported_language")
        if response.status_code >= 400:
            raise STTError("timeout")
        value = response.json()
        return {
            "text": value.get("text", ""),
            "detected_language": value.get("language") or value.get("detected_language"),
            "adapter": self.name,
        }


class UnavailableAdapter:
    def __init__(self, name: str):
        self.name = name

    async def transcribe(self, request: STTRequest) -> dict:
        raise STTError("missing_key", f"{self.name} is unavailable")


class TextAdapter:
    name = "text"

    async def transcribe(self, request: STTRequest) -> dict:
        return {"text": "", "detected_language": request.language, "adapter": self.name, "demo_mode": True}


async def transcribe(request: STTRequest) -> dict:
    adapters = {
        "xai_stt": XaiSttAdapter(),
        "web_speech": UnavailableAdapter("web_speech"),
        "text": TextAdapter(),
    }
    order = [item.strip() for item in os.getenv("STT_ORDER", "xai_stt,text").split(",")]
    errors = []
    for name in order:
        adapter = adapters.get(name)
        if not adapter:
            continue
        try:
            return await adapter.transcribe(request)
        except STTError as exc:
            errors.append(exc.code)
    return {"text": "", "adapter": "none", "error": errors[-1] if errors else "missing_key", "errors": errors}
