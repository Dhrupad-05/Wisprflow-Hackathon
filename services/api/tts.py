"""Server-side xAI text-to-speech proxy."""

import os

import httpx


class TTSError(Exception):
    """A normalized provider error safe to return to the browser."""


async def synthesize(text: str, language: str = "en") -> tuple[bytes, str]:
    api_key = os.getenv("XAI_TTS_API_KEY", "")
    if not api_key:
        raise TTSError("missing_key")
    payload = {
        "text": text,
        "voice_id": os.getenv("XAI_TTS_VOICE", "eve"),
        "language": language,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                os.getenv("XAI_TTS_API_URL", "https://api.x.ai/v1/tts"),
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
    except httpx.TimeoutException as exc:
        raise TTSError("timeout") from exc
    if response.status_code in {401, 403}:
        raise TTSError("unauthorized")
    if response.status_code >= 400:
        raise TTSError("provider_error")
    content_type = response.headers.get("content-type", "audio/mpeg").split(";", 1)[0]
    return response.content, content_type
