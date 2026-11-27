"""Server-side speech-to-text adapters.

Audio is never persisted, logged, or echoed back. Every adapter returns the same
shape and raises ``STTError`` for normalized failures, so the chain can fall
through to the next engine and the browser can explain exactly what happened.
"""

from __future__ import annotations

import array
import asyncio
import base64
import importlib.util
import io
import json
import math
import os
import sys
import threading
import time
import wave
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]

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
    "engine_unavailable",
}

DEFAULT_ORDER = "wispr_api,whisper_local,xai_stt,web_speech,text"
MAX_AUDIO_BYTES = 25 * 1024 * 1024

# Whisper uses ISO 639-1 codes; the app's hints may be BCP-47 (e.g. hi-IN).
WHISPER_LANGUAGES = {
    "en": "en",
    "en-in": "en",
    "en-us": "en",
    "en-gb": "en",
    "hi": "hi",
    "hi-in": "hi",
    "bn": "bn",
    "bn-in": "bn",
}

WHISPER_BASE_PROMPT = ("SBI", "Kisan Credit Card", "Udyam", "PM-KISAN")


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


def _read_wav(audio: bytes) -> tuple[int, int, array.array]:
    """Parse a 16-bit PCM WAV in memory and return its samples."""

    try:
        reader = wave.Wave_read(io.BytesIO(audio))
        try:
            channels = reader.getnchannels()
            width = reader.getsampwidth()
            rate = reader.getframerate()
            frames = reader.getnframes()
            raw = reader.readframes(frames)
        finally:
            reader.close()
    except (wave.Error, EOFError) as exc:
        raise STTError("invalid_audio", "Expected a PCM WAV recording") from exc
    if width != 2 or rate <= 0 or not raw:
        raise STTError("invalid_audio", "Expected 16-bit PCM WAV audio")
    samples = array.array("h")
    samples.frombytes(raw[: len(raw) - (len(raw) % 2)])
    if sys.byteorder == "big":
        samples.byteswap()
    if not samples:
        raise STTError("empty", "The recording was empty")
    return channels, rate, samples


def wav_stats(audio: bytes) -> tuple[float, float]:
    """Return ``(seconds, rms)`` for a 16-bit PCM WAV, decoded in memory."""

    channels, rate, samples = _read_wav(audio)
    energy = sum(value * value for value in samples) / len(samples)
    rms = math.sqrt(energy) / 32768.0
    frames_per_channel = len(samples) / max(1, channels)
    return frames_per_channel / rate, rms


def prepare_audio(audio: bytes):
    """Decode WAV bytes to a mono float32 array at 16 kHz for Whisper.

    Passing an array avoids a second decoder (and its native dependencies) while
    keeping the audio entirely in memory.
    """

    channels, rate, samples = _read_wav(audio)
    seconds = len(samples) / max(1, channels) / rate
    energy = sum(value * value for value in samples) / len(samples)
    rms = math.sqrt(energy) / 32768.0
    try:
        import numpy as np
    except ImportError as exc:  # faster-whisper installs numpy
        raise STTError("engine_unavailable", "numpy is required for whisper_local") from exc
    values = np.asarray(samples, dtype="float32") / 32768.0
    if channels > 1:
        values = values.reshape(-1, channels).mean(axis=1)
    if rate != 16000 and values.size:
        target = max(1, int(round(values.size * 16000 / rate)))
        values = np.interp(
            np.linspace(0, values.size - 1, target), np.arange(values.size), values
        ).astype("float32")
    return values, seconds, rms


@lru_cache(maxsize=1)
def registry_terms() -> tuple[str, ...]:
    """Bank and scheme names from the JSON registries, not hardcoded lists."""

    terms: list[str] = []
    for name in ("banks.json", "schemes.json"):
        try:
            data = json.loads((ROOT / "packages/registries" / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for item in data if isinstance(data, list) else []:
            if isinstance(item, dict) and item.get("name"):
                terms.append(str(item["name"]))
    return tuple(terms)


def initial_prompt(dictionary_context: list[str] | None = None) -> str:
    """Bias Whisper toward the demo's Hindi/Bengali code-mixed vocabulary."""

    merged = [str(item).strip() for item in (dictionary_context or []) if str(item).strip()]
    merged.extend(WHISPER_BASE_PROMPT)
    merged.extend(registry_terms())
    seen: list[str] = []
    for term in merged:
        if term and term.lower() not in {item.lower() for item in seen}:
            seen.append(term)
    return ", ".join(seen)[:900]


def _whisper_language(language: str | None) -> str | None:
    if not language:
        return None
    return WHISPER_LANGUAGES.get(str(language).strip().lower())


class WisprSttAdapter:
    """Wispr Flow REST transcription.

    Contract from https://api-docs.wisprflow.ai/rest_api_transcribe:
    ``POST /api`` on ``https://platform-api.wisprflow.ai/api/v1/dash`` with a
    bearer API key, a base64 16 kHz PCM16 WAV ``audio`` field, an optional
    ISO 639-1 ``language`` array, and an optional ``context`` object.
    The 200 response is ``{id, text, detected_language, total_time,
    generated_tokens}``.
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


class WhisperLocalAdapter:
    """Offline speech-to-text with faster-whisper on the server's CPU.

    The model is a process-wide singleton, loaded lazily (or preloaded at
    startup). Audio stays in memory and is never written to disk or logged.
    """

    name = "whisper_local"

    def __init__(
        self,
        model_size: str | None = None,
        model_dir: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
        model_factory=None,
        auto_downgrade: bool | None = None,
    ):
        self.requested_model = model_size or os.getenv("WHISPER_MODEL", "small")
        self.model_size = self.requested_model
        self.model_dir = model_dir if model_dir is not None else (os.getenv("WHISPER_MODEL_DIR") or None)
        self.device = device or os.getenv("WHISPER_DEVICE", "cpu")
        self.compute_type = compute_type or os.getenv("WHISPER_COMPUTE_TYPE", "int8")
        self.model_factory = model_factory
        self.auto_downgrade = (
            os.getenv("WHISPER_AUTO_DOWNGRADE", "1") != "0"
            if auto_downgrade is None
            else auto_downgrade
        )
        self.enabled = os.getenv("WHISPER_ENABLED", "1") != "0"
        self.min_seconds = float(os.getenv("WHISPER_MIN_SECONDS", "0.3"))
        self.silence_rms = float(os.getenv("WHISPER_SILENCE_RMS", "0.004"))
        self.downgraded = False
        self.last_latency_ms: int | None = None
        self._model = None
        self._lock = threading.Lock()
        self.state = "idle" if self.installed() else "unavailable"

    def installed(self) -> bool:
        if self.model_factory is not None:
            return True
        if not self.enabled:
            return False
        try:
            return importlib.util.find_spec("faster_whisper") is not None
        except (ImportError, ValueError):
            return False

    def load(self):
        """Load the model once and memoize it. Safe to call from a thread."""

        with self._lock:
            if self._model is not None:
                return self._model
            if not self.installed():
                self.state = "unavailable"
                raise STTError(
                    "engine_unavailable",
                    "faster-whisper is not installed; run pip install -r services/api/requirements.txt",
                )
            self.state = "loading"
            factory = self.model_factory
            try:
                if factory is None:
                    from faster_whisper import WhisperModel

                    def factory(size):
                        return WhisperModel(
                            size,
                            device=self.device,
                            compute_type=self.compute_type,
                            download_root=self.model_dir,
                        )

                self._model = factory(self.model_size)
            except STTError:
                self.state = "unavailable"
                raise
            except Exception as exc:  # a missing model must not crash the demo
                self.state = "unavailable"
                raise STTError(
                    "engine_unavailable",
                    f"whisper_local could not load the '{self.model_size}' model",
                ) from exc
            self.state = "ready"
            return self._model

    def _note_latency(self, elapsed_ms: int, seconds: float) -> None:
        self.last_latency_ms = elapsed_ms
        if (
            self.auto_downgrade
            and not self.downgraded
            and self.model_size == "small"
            and not os.getenv("WHISPER_MODEL")
            and seconds <= 8
            and elapsed_ms > 3000
        ):
            # Warm-up on a CPU-only demo box can be slow; try the base model on
            # the next utterance instead of making every turn miss the budget.
            self.downgraded = True
            self.model_size = "base"
            with self._lock:
                self._model = None
            self.state = "idle"

    def _run(self, model, audio, language: str | None, prompt: str) -> tuple[str, str | None]:
        segments, info = model.transcribe(
            audio,
            language=language,
            initial_prompt=prompt or None,
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        text = " ".join(getattr(segment, "text", "").strip() for segment in segments).strip()
        return text, getattr(info, "language", None)

    async def transcribe(self, request: STTRequest) -> dict:
        audio = request.audio_bytes
        samples, seconds, rms = prepare_audio(audio)
        if seconds < self.min_seconds:
            raise STTError("empty", "The recording was too short")
        if rms < self.silence_rms:
            raise STTError("empty", "The recording was silent")

        language = _whisper_language(request.language)
        prompt = initial_prompt(request.dictionary_context)
        model = await asyncio.to_thread(self.load)
        started = time.perf_counter()
        try:
            text, detected = await asyncio.to_thread(self._run, model, samples, language, prompt)
        except STTError:
            raise
        except Exception as exc:  # provider-style failure, never a 500
            raise STTError("provider_error", "whisper_local failed to transcribe") from exc
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        self._note_latency(elapsed_ms, seconds)
        return {
            "text": text,
            "detected_language": detected or language,
            "adapter": self.name,
            "latency_ms": elapsed_ms,
        }


_WHISPER: WhisperLocalAdapter | None = None
_WHISPER_LOCK = threading.Lock()


def get_whisper_adapter() -> WhisperLocalAdapter:
    """Process-wide local engine so health, preload and turns share one model."""

    global _WHISPER
    with _WHISPER_LOCK:
        if _WHISPER is None:
            _WHISPER = WhisperLocalAdapter()
        return _WHISPER


def reset_whisper_adapter() -> None:
    """Test helper: forget the singleton (and its loaded model)."""

    global _WHISPER
    with _WHISPER_LOCK:
        _WHISPER = None


def whisper_health() -> dict:
    adapter = get_whisper_adapter()
    status = adapter.state
    if status == "idle":
        status = "loading"
    return {
        "status": status,
        "model": adapter.model_size,
        "requested_model": adapter.requested_model,
        "downgraded": adapter.downgraded,
        "last_latency_ms": adapter.last_latency_ms,
        "installed": adapter.installed(),
    }


async def preload_whisper() -> None:
    """Warm the local model in the background so the first turn is fast."""

    if os.getenv("WHISPER_PRELOAD", "1") == "0":
        return
    adapter = get_whisper_adapter()
    if not adapter.installed():
        return
    try:
        await asyncio.to_thread(adapter.load)
        print("[Bolo Sahayak] whisper_local ready", flush=True)
    except STTError as exc:
        print(f"[Bolo Sahayak] whisper_local unavailable: {exc.code}", flush=True)


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
        "whisper_local": get_whisper_adapter(),
        "xai_stt": XaiSttAdapter(),
        "web_speech": WebSpeechAdapter(),
        "text": TextAdapter(),
    }


def stt_order() -> list[str]:
    configured = os.getenv("STT_ORDER", DEFAULT_ORDER)
    return [item.strip() for item in configured.split(",") if item.strip()]


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
