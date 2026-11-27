"""Server-side speech-to-text adapters.

Audio is never persisted, logged, or echoed back. Every adapter returns the same
shape and raises ``STTError`` for normalized failures, so the chain can fall
through to the next engine and the browser can explain exactly what happened.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass

import httpx

ERRORS = {
    "missing_key",
    "unauthorized",
    "timeout",
    "unsupported_language",
    "too_large",
    "invalid_audio",
    "provider_error",
    "client_side",
    "empty",
}

DEFAULT_ORDER = "wispr_api,xai_stt,web_speech,text"
MAX_AUDIO_BYTES = 25 * 1024 * 1024


class STTError(Exception):
    """A normalized provider failure that is safe to return to the browser."""

    def __init__(self, code: str, detail: str = ""):
        self.code = code if code in ERRORS else "provider_error"
        super().__init__(detail or self.code)


@dataclass
class STTRequest:
    audio: str
    language: str | None = None
    dictionary_context: list[str] | None = None

    @property
    def audio_bytes(self) -> bytes:
        try:
            audio = base64.b64decode(self.audio, validate=True)
        except (ValueError, UnicodeError) as exc:
            raise STTError("invalid_audio", "Invalid audio encoding") from exc
        if len(audio) > MAX_AUDIO_BYTES:
            raise STTError("too_large", "Audio larger than 25MB")
        return audio


def _languages(request: STTRequest) -> list[str]:
    return [request.language] if request.language else []


def provider_error(status: int, detail: str = "") -> STTError:
    """Map a provider status/body to an actionable, non-leaky error code.

    Some providers answer an invalid key with HTTP 400, so the body is checked
    before assuming the language was the problem.
    """

    text = (detail or "").lower()
    if status in {401, 403}:
        return STTError("unauthorized")
    if status == 413:
        return STTError("too_large")
    if any(word in text for word in ("api key", "unauthorized", "authentication", "forbidden", "permission")):
        return STTError("unauthorized")
    if any(word in text for word in ("language", "locale", "not supported for")):
        return STTError("unsupported_language")
    if status == 422:
        return STTError("unsupported_language")
    return STTError("provider_error")


class WisprSttAdapter:
    """Wispr Flow REST transcription.

    Contract from https://api-docs.wisprflow.ai/rest_api_transcribe:
    ``POST /api`` on ``https://platform-api.wisprflow.ai/api/v1/dash`` with a
    bearer API key, a base64 16 kHz PCM16 WAV ``audio`` field, an optional
    ISO 639-1 ``language`` array, and an optional ``context`` object.
    """

    name = "wispr_api"

    def __init__(
        self,
        api_key: str | None = None,
        api_url: str | None = None,
        timeout: float | None = None,
        client=None,
    ):
        self.api_key = api_key if api_key is not None else os.getenv("WISPR_API_KEY", "")
        self.api_url = api_url or os.getenv(
            "WISPR_API_URL", "https://platform-api.wisprflow.ai/api/v1/dash/api"
        )
        self.timeout = (
            timeout
            if timeout is not None
            else float(os.getenv("WISPR_TIMEOUT_SECONDS", "20"))
        )
        self.client = client

    def payload(self, request: STTRequest) -> dict:
        return {
            "audio": request.audio,
            "language": _languages(request),
            "context": {
                "app": {"type": "other"},
                "dictionary_context": [
                    str(item) for item in (request.dictionary_context or [])
                ],
                "textbox_contents": {
                    "before_text": "",
                    "selected_text": "",
                    "after_text": "",
                },
            },
        }

    async def transcribe(self, request: STTRequest) -> dict:
        if not self.api_key:
            raise STTError("missing_key")
        request.audio_bytes  # validate encoding and size before spending a request
        client = self.client or httpx.AsyncClient(timeout=self.timeout)
        owns_client = self.client is None
        try:
            try:
                response = await client.post(
                    self.api_url,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json=self.payload(request),
                )
            except httpx.TimeoutException as exc:
                raise STTError("timeout") from exc
            except httpx.HTTPError as exc:
                raise STTError("provider_error") from exc
        finally:
            if owns_client:
                await client.aclose()
        if response.status_code >= 400:
            raise provider_error(response.status_code, response.text[:500])
        try:
            value = response.json()
        except ValueError as exc:
            raise STTError("provider_error") from exc
        return {
            "text": str(value.get("text") or "").strip(),
            "detected_language": value.get("detected_language"),
            "adapter": self.name,
        }


# Backwards-compatible alias for code that referred to the Wispr adapter by name.
WisprAdapter = WisprSttAdapter


class XaiSttAdapter:
    name = "xai_stt"

    def __init__(
        self,
        api_key: str | None = None,
        api_url: str | None = None,
        model: str | None = None,
        client=None,
    ):
        self.api_key = api_key if api_key is not None else os.getenv("XAI_STT_API_KEY", "")
        self.api_url = api_url or os.getenv("XAI_STT_API_URL", "https://api.x.ai/v1/stt")
        self.model = model or os.getenv("XAI_STT_MODEL", "grok-voice-transcribe-2.0")
        self.client = client

    async def transcribe(self, request: STTRequest) -> dict:
        if not self.api_key:
            raise STTError("missing_key")
        audio = request.audio_bytes
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
            except httpx.HTTPError as exc:
                raise STTError("provider_error") from exc
        finally:
            if owns_client:
                await client.aclose()
        if response.status_code >= 400:
            raise provider_error(response.status_code, response.text[:500])
        try:
            value = response.json()
        except ValueError as exc:
            raise STTError("provider_error") from exc
        return {
            "text": str(value.get("text") or "").strip(),
            "detected_language": value.get("language") or value.get("detected_language"),
            "adapter": self.name,
        }


class UnavailableAdapter:
    """Explicitly unavailable engine, kept for registry compatibility."""

    def __init__(self, name: str, code: str = "missing_key"):
        self.name = name
        self.code = code

    async def transcribe(self, request: STTRequest) -> dict:
        raise STTError(self.code, f"{self.name} is unavailable server-side")


class WebSpeechAdapter:
    """Marker for the browser recognizer.

    The server cannot run Web Speech, so it reports ``client_side`` and the web
    app starts ``webkitSpeechRecognition`` itself with the same endpointing.
    """

    name = "web_speech"

    async def transcribe(self, request: STTRequest) -> dict:
        raise STTError("client_side", "Web Speech runs in the browser")


class TextAdapter:
    """Demo-mode terminal adapter: typed input is the interface."""

    name = "text"

    async def transcribe(self, request: STTRequest) -> dict:
        return {
            "text": "",
            "detected_language": request.language,
            "adapter": self.name,
            "demo_mode": True,
            "error_code": "empty",
        }


def build_adapters() -> dict:
    return {
        "wispr_api": WisprSttAdapter(),
        "xai_stt": XaiSttAdapter(),
        "web_speech": WebSpeechAdapter(),
        "text": TextAdapter(),
    }


def stt_order() -> list[str]:
    configured = os.getenv("STT_ORDER", DEFAULT_ORDER)
    return [item.strip() for item in configured.split(",") if item.strip()]


async def transcribe(
    request: STTRequest,
    adapters: dict | None = None,
    order: list[str] | None = None,
) -> dict:
    """Run the adapter chain, skipping missing keys, errors, and empty text."""

    registry = adapters if adapters is not None else build_adapters()
    chain = order if order is not None else stt_order()
    errors: list[dict] = []
    tried: list[str] = []
    for name in chain:
        adapter = registry.get(name)
        if adapter is None:
            continue
        tried.append(name)
        try:
            result = await adapter.transcribe(request)
        except STTError as exc:
            errors.append({"adapter": name, "error": exc.code})
            continue
        except Exception:  # a provider bug must never break the demo
            errors.append({"adapter": name, "error": "provider_error"})
            continue
        text = str(result.get("text") or "").strip()
        if not text and not result.get("demo_mode"):
            errors.append({"adapter": name, "error": "empty"})
            continue
        return {
            **result,
            "text": text,
            "adapter": name,
            "error_code": result.get("error_code") or (None if text else "empty"),
            "errors": errors,
            "tried": tried,
        }
    last = errors[-1]["error"] if errors else "missing_key"
    return {
        "text": "",
        "adapter": "none",
        "error_code": last,
        "errors": errors,
        "tried": tried,
    }
