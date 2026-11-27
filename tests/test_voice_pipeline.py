import base64
import threading

import httpx

from services.api.stt import STTRequest, XaiSttAdapter
from services.api.tts import TTSError, synthesize


def run_async(coroutine):
    result = []
    error = []

    def runner():
        try:
            result.append(__import__("asyncio").run(coroutine))
        except BaseException as exc:
            error.append(exc)

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join()
    if error:
        raise error[0]
    return result[0]


def test_xai_stt_uses_multipart_audio_and_normalizes_language():
    seen = {}

    async def handler(request):
        seen["content_type"] = request.headers["content-type"]
        seen["body"] = request.content
        return httpx.Response(200, json={"text": "deposit", "language": "en"})

    async def run():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = XaiSttAdapter(api_key="test", client=client)
        result = await adapter.transcribe(STTRequest(base64.b64encode(b"RIFFdemo").decode(), "en"))
        await client.aclose()
        return result

    result = run_async(run())
    assert result == {"text": "deposit", "detected_language": "en", "adapter": "xai_stt"}
    assert "multipart/form-data" in seen["content_type"]
    assert b'name="file"' in seen["body"]


def test_tts_without_key_is_explicit(monkeypatch):
    monkeypatch.delenv("XAI_TTS_API_KEY", raising=False)

    async def run():
        try:
            await synthesize("hello")
        except TTSError as error:
            return str(error)
        return "missing error"

    assert run_async(run()) == "missing_key"
