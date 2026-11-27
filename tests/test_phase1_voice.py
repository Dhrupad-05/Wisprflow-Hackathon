"""Phase 1 microphone and speech-to-text regression gates."""

import asyncio
import base64
import json
import threading
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

from services.api.main import app
from services.api.stt import (
    STTError,
    STTRequest,
    WisprSttAdapter,
    transcribe,
)

ROOT = Path(__file__).resolve().parents[1]
AUDIO = base64.b64encode(b"RIFF" + b"0" * 128).decode()


def run_async(coro):
    result = []
    error = []

    def runner():
        try:
            result.append(asyncio.run(coro))
        except BaseException as exc:  # pragma: no cover - transport helper
            error.append(exc)

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join()
    if error:
        raise error[0]
    return result[0]


class FakeAdapter:
    def __init__(self, name, text="", error=None):
        self.name = name
        self.text = text
        self.error = error

    async def transcribe(self, request):
        if self.error:
            raise STTError(self.error)
        return {"text": self.text, "adapter": self.name}


def test_wispr_adapter_matches_documented_rest_contract():
    seen = {}

    async def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["content_type"] = request.headers["content-type"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200, json={"text": " পাঁচ হাজার ", "detected_language": "bn"}
        )

    async def run():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = WisprSttAdapter(api_key="test-key", client=client)
        result = await adapter.transcribe(STTRequest(AUDIO, "bn", ["SBI", "Udyam"]))
        await client.aclose()
        return result

    result = run_async(run())
    assert result == {
        "text": "পাঁচ হাজার",
        "detected_language": "bn",
        "adapter": "wispr_api",
    }
    assert seen["url"].startswith("https://platform-api.wisprflow.ai/api/v1/dash/api")
    assert seen["auth"] == "Bearer test-key"
    assert seen["content_type"].startswith("application/json")
    assert seen["body"]["audio"] == AUDIO
    assert seen["body"]["language"] == ["bn"]
    assert seen["body"]["context"]["dictionary_context"] == ["SBI", "Udyam"]
    assert seen["body"]["context"]["app"]["type"] == "other"


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (401, "", "unauthorized"),
        (403, "", "unauthorized"),
        (413, "", "too_large"),
        (400, '{"error": "Incorrect API key provided"}', "unauthorized"),
        (400, '{"error": "language en is not supported"}', "unsupported_language"),
        (422, "", "unsupported_language"),
        (500, "", "provider_error"),
    ],
)
def test_wispr_errors_are_normalized(status, body, expected):
    async def handler(_request):
        return httpx.Response(status, text=body)

    async def run():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = WisprSttAdapter(api_key="test-key", client=client)
        try:
            await adapter.transcribe(STTRequest(AUDIO, "hi"))
        except STTError as error:
            return error.code
        finally:
            await client.aclose()
        return "no error"

    assert run_async(run()) == expected


def test_wispr_timeout_is_normalized():
    async def handler(_request):
        raise httpx.TimeoutException("slow")

    async def run():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = WisprSttAdapter(api_key="test-key", client=client)
        try:
            await adapter.transcribe(STTRequest(AUDIO, "en"))
        except STTError as error:
            return error.code
        finally:
            await client.aclose()

    assert run_async(run()) == "timeout"


def test_chain_falls_through_missing_key_errors_and_empty_text():
    adapters = {
        "wispr_api": FakeAdapter("wispr_api", error="missing_key"),
        "xai_stt": FakeAdapter("xai_stt", text=""),
        "web_speech": FakeAdapter("web_speech", error="client_side"),
        "other": FakeAdapter("other", text="paanch hazaar"),
    }
    result = run_async(
        transcribe(
            STTRequest(AUDIO, "hi"),
            adapters=adapters,
            order=["wispr_api", "xai_stt", "web_speech", "other"],
        )
    )
    assert result["text"] == "paanch hazaar"
    assert result["adapter"] == "other"
    assert result["error_code"] is None
    assert [item["error"] for item in result["errors"]] == ["missing_key", "empty", "client_side"]


def test_chain_reports_the_last_reason_when_every_engine_is_empty():
    adapters = {"a": FakeAdapter("a", text="   "), "b": FakeAdapter("b", error="unauthorized")}
    result = run_async(
        transcribe(STTRequest(AUDIO), adapters=adapters, order=["a", "b"])
    )
    assert result["adapter"] == "none"
    assert result["text"] == ""
    assert result["error_code"] == "unauthorized"
    assert result["tried"] == ["a", "b"]


def test_stt_endpoint_explains_demo_fallthrough(monkeypatch):
    monkeypatch.delenv("WISPR_API_KEY", raising=False)
    monkeypatch.delenv("XAI_STT_API_KEY", raising=False)
    monkeypatch.setenv("STT_ORDER", "wispr_api,xai_stt,web_speech,text")
    response = TestClient(app).post("/v1/stt", json={"audio": AUDIO, "language": "hi"})
    body = response.json()
    assert response.status_code == 200
    assert body["adapter"] == "text"
    assert body["demo_mode"] is True
    assert body["error_code"] == "empty"
    assert [item["adapter"] for item in body["errors"]] == ["wispr_api", "xai_stt", "web_speech"]


def test_stt_endpoint_rejects_bad_audio_without_a_provider_call():
    body = TestClient(app).post("/v1/stt", json={"audio": "not-base64"}).json()
    assert body["error_code"] == "invalid_audio"
    assert body["adapter"] == "none"


def test_health_reports_engine_booleans(monkeypatch):
    monkeypatch.delenv("WISPR_API_KEY", raising=False)
    monkeypatch.setenv("XAI_STT_API_KEY", "test")
    body = TestClient(app).get("/v1/health").json()
    assert body["stt"]["wispr_api"] is False
    assert body["stt"]["xai_stt"] is True
    assert body["voice_ready"] is True
    assert body["demo_mode"] is False
    assert "text" in body["stt_order"]
    assert set(body["llm"]) == {"gemini", "xai", "openrouter", "fallback"}
    assert set(body["tts"]) == {"xai_tts"}


def test_capture_path_has_no_fixed_stop_timer_or_permission_race():
    audio = (ROOT / "apps/web/audio.js").read_text(encoding="utf-8")
    assert "Promise.race" not in audio
    assert "microphone-timeout" not in audio
    assert "audioWorklet" in audio
    assert "context.resume()" in audio
    script = (ROOT / "apps/web/app.js").read_text(encoding="utf-8")
    assert "3750" not in script
    assert "HARD_MAX_MS = 30000" in script
    assert "startWebSpeech(message)" in script


@pytest.fixture(scope="module")
def vad_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=8768, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        if server.started:
            break
        threading.Event().wait(0.1)
    if not server.started:
        pytest.fail("phase 1 server did not start")
    yield "http://127.0.0.1:8768"
    server.should_exit = True
    thread.join(timeout=5)


def test_vad_uses_energy_thresholds_and_silence_window(page, vad_server):
    page.goto(vad_server + "/")
    result = page.evaluate(
        """
        async () => {
          const { VoiceActivityDetector } = await import('/packages/voice/vad.js');
          let now = 0;
          const detector = new VoiceActivityDetector({ silenceMs: 800, clock: () => now });
          detector.feed(0.2);
          const started = detector.feed(0.2);
          now = 700;
          const early = detector.feed(0.001);
          now = 900;
          const ended = detector.feed(0.001);
          const slow = new VoiceActivityDetector({ silenceMs: 1000, slow: true });
          return {
            started: started.started,
            earlyEnded: early.ended,
            ended: ended.ended,
            slowWait: slow.wait,
            thresholdIgnored: new VoiceActivityDetector().feed(0.001).spoke
          };
        }
        """
    )
    assert result == {
        "started": True,
        "earlyEnded": False,
        "ended": True,
        "slowWait": 1500,
        "thresholdIgnored": False,
    }
