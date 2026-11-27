"""whisper_local engine, the fallback chain, and the browser mic policy."""

import asyncio
import base64
import io
import json
import math
import shutil
import struct
import subprocess
import tempfile
import threading
import wave
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient
from playwright.sync_api import expect

from services.api import stt as stt_module
from services.api.main import app, provider_status
from services.api.stt import (
    STTError,
    STTRequest,
    WhisperLocalAdapter,
    WisprSttAdapter,
    transcribe,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/hello_hi.wav"
PORT = 8772


def make_wav(seconds=1.0, amplitude=0.35, frequency=440.0):
    rate = 16000
    frames = bytearray()
    for index in range(int(rate * seconds)):
        value = int(32767 * amplitude * math.sin(2 * math.pi * frequency * index / rate))
        frames.extend(struct.pack("<h", value))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(bytes(frames))
    return buffer.getvalue()


def run_async(coroutine):
    """Run a coroutine on a private loop; other suites may leave one running."""

    result, error = [], []

    def runner():
        try:
            result.append(asyncio.run(coroutine))
        except BaseException as exc:
            error.append(exc)

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join()
    if error:
        raise error[0]
    return result[0]


def encoded(audio):
    return base64.b64encode(audio).decode()


class FakeSegment:
    def __init__(self, text):
        self.text = text


class FakeInfo:
    language = "hi"


class FakeModel:
    """Stands in for faster_whisper.WhisperModel; records the call."""

    def __init__(self, text="SBI mein paanch hazaar jama karna hai"):
        self.text = text
        self.calls = []

    def transcribe(self, source, **kwargs):
        self.calls.append({"kwargs": kwargs, "source": source})
        return [FakeSegment(self.text)], FakeInfo()


def test_adapter_runs_in_memory_with_language_prompt_and_options():
    model = FakeModel()
    sizes = []

    def factory(size):
        sizes.append(size)
        return model

    adapter = WhisperLocalAdapter(model_size="small", model_factory=factory, auto_downgrade=False)
    result = run_async(
        adapter.transcribe(STTRequest(encoded(make_wav()), "hi", ["SBI", "Udyam"]))
    )

    assert result["text"] == "SBI mein paanch hazaar jama karna hai"
    assert result["adapter"] == "whisper_local"
    assert result["detected_language"] == "hi"
    assert isinstance(result["latency_ms"], int)
    assert sizes == ["small"]
    assert adapter.state == "ready"
    call = model.calls[0]
    # A decoded float32 array: in memory, never written to disk.
    assert call["source"].dtype == "float32"
    assert call["source"].size == 16000
    assert call["kwargs"]["language"] == "hi"
    assert call["kwargs"]["beam_size"] == 5
    assert call["kwargs"]["vad_filter"] is True
    assert call["kwargs"]["condition_on_previous_text"] is False
    prompt = call["kwargs"]["initial_prompt"]
    assert "SBI" in prompt
    assert "State Bank of India" in prompt  # pulled from the bank registry


def test_adapter_accepts_bcp47_language_hints():
    model = FakeModel()
    adapter = WhisperLocalAdapter(model_factory=lambda size: model)
    run_async(adapter.transcribe(STTRequest(encoded(make_wav()), "bn-IN")))
    assert model.calls[0]["kwargs"]["language"] == "bn"


@pytest.mark.parametrize(
    "audio",
    [make_wav(1.0, amplitude=0.0), make_wav(0.2)],
    ids=["silent", "too-short"],
)
def test_adapter_rejects_silent_or_short_audio_without_loading_a_model(audio):
    loaded = []
    adapter = WhisperLocalAdapter(model_factory=lambda size: loaded.append(size) or FakeModel())
    with pytest.raises(STTError) as error:
        run_async(adapter.transcribe(STTRequest(encoded(audio), "hi")))
    assert error.value.code == "empty"
    assert loaded == []


def test_adapter_rejects_non_wav_audio():
    adapter = WhisperLocalAdapter(model_factory=lambda size: FakeModel())
    with pytest.raises(STTError) as error:
        run_async(adapter.transcribe(STTRequest(encoded(b"not a wav"), "hi")))
    assert error.value.code == "invalid_audio"


def test_missing_faster_whisper_is_engine_unavailable(monkeypatch):
    monkeypatch.setattr(stt_module.importlib.util, "find_spec", lambda name: None)
    adapter = WhisperLocalAdapter()
    assert adapter.state == "unavailable"
    with pytest.raises(STTError) as error:
        run_async(adapter.transcribe(STTRequest(encoded(make_wav()), "hi")))
    assert error.value.code == "engine_unavailable"


class MissingKeyWispr:
    name = "wispr_api"

    async def transcribe(self, request):
        raise STTError("missing_key")


def test_chain_falls_through_wispr_missing_key_to_whisper():
    adapter = WhisperLocalAdapter(model_factory=lambda size: FakeModel())
    result = run_async(
        transcribe(
            STTRequest(encoded(make_wav()), "hi"),
            adapters={"wispr_api": MissingKeyWispr(), "whisper_local": adapter},
            order=["wispr_api", "whisper_local"],
        )
    )
    assert result["adapter"] == "whisper_local"
    assert result["text"].startswith("SBI")
    assert result["tried"] == ["wispr_api", "whisper_local"]
    assert result["errors"] == [{"adapter": "wispr_api", "error": "missing_key"}]


def test_chain_reports_empty_when_whisper_hears_nothing():
    adapter = WhisperLocalAdapter(model_factory=lambda size: FakeModel(text="  "))
    result = run_async(
        transcribe(
            STTRequest(encoded(make_wav()), "hi"),
            adapters={"whisper_local": adapter},
            order=["whisper_local"],
        )
    )
    assert result["adapter"] == "none"
    assert result["error_code"] == "empty"
    assert result["errors"] == [{"adapter": "whisper_local", "error": "empty"}]


def test_slow_cpu_utterance_downgrades_small_to_base(monkeypatch):
    monkeypatch.delenv("WHISPER_MODEL", raising=False)
    adapter = WhisperLocalAdapter(model_factory=lambda size: FakeModel())
    adapter._note_latency(3400, 6.0)
    assert adapter.downgraded is True
    assert adapter.model_size == "base"
    assert adapter.state == "idle"


def test_wispr_matches_documented_response_and_request(monkeypatch):
    monkeypatch.delenv("WISPR_API_URL", raising=False)
    seen = {}

    async def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        # Exact 200 shape from https://api-docs.wisprflow.ai/rest_api_transcribe
        return httpx.Response(
            200,
            json={
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "text": "SBI mein paanch hazaar jama karna hai",
                "detected_language": "hi",
                "total_time": 432,
                "generated_tokens": 9,
            },
        )

    async def run():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = WisprSttAdapter(api_key="test-key", client=client)
        try:
            return await adapter.transcribe(STTRequest(encoded(make_wav()), "hi", ["SBI"]))
        finally:
            await client.aclose()

    result = run_async(run())
    assert result == {
        "text": "SBI mein paanch hazaar jama karna hai",
        "detected_language": "hi",
        "adapter": "wispr_api",
    }
    assert seen["url"] == "https://platform-api.wisprflow.ai/api/v1/dash/api"
    assert seen["auth"] == "Bearer test-key"
    assert seen["body"]["language"] == ["hi"]
    assert seen["body"]["context"]["dictionary_context"] == ["SBI"]


def test_default_order_prefers_local_whisper_before_cloud_fallbacks(monkeypatch):
    monkeypatch.delenv("STT_ORDER", raising=False)
    assert stt_module.stt_order() == [
        "wispr_api",
        "whisper_local",
        "xai_stt",
        "web_speech",
        "text",
    ]


def test_health_reports_whisper_state(monkeypatch):
    monkeypatch.delenv("WISPR_API_KEY", raising=False)
    monkeypatch.delenv("XAI_STT_API_KEY", raising=False)
    monkeypatch.setenv("STT_ORDER", "whisper_local,text")
    status = provider_status()
    assert status["stt"]["whisper_local"] in {"ready", "loading", "unavailable"}
    assert set(status["whisper"]) >= {"status", "model", "downgraded", "installed"}
    assert isinstance(status["demo_mode"], bool)


def test_stt_endpoint_exposes_the_local_adapter(monkeypatch):
    adapter = WhisperLocalAdapter(model_factory=lambda size: FakeModel())
    original = stt_module.build_adapters

    def build():
        registry = original()
        registry["whisper_local"] = adapter
        return registry

    monkeypatch.setattr(stt_module, "build_adapters", build)
    body = TestClient(app).post(
        "/v1/stt", json={"audio": encoded(make_wav()), "language": "hi"}
    ).json()
    assert body["adapter"] == "whisper_local"
    assert body["text"].startswith("SBI")
    assert body["tried"][0] == "wispr_api"
    assert isinstance(body["server_engine_ready"], bool)


POLICY_SCRIPT = """
import {{ engineReady, readyEngineNames, serverEngineReady, speechErrorInfo, whisperHeardNothing }} from {url};
const out = {{
  ready: engineReady({{ stt: {{ wispr_api: false, whisper_local: "ready", xai_stt: false }} }}),
  loadingOnly: engineReady({{ stt: {{ wispr_api: false, whisper_local: "loading", xai_stt: false }} }}),
  cloud: engineReady({{ stt: {{ wispr_api: true, whisper_local: "unavailable" }} }}),
  names: readyEngineNames({{ stt: {{ wispr_api: true, whisper_local: "ready", text: true }} }}),
  whisperEmpty: whisperHeardNothing({{ tried: ["wispr_api", "whisper_local", "text"],
    errors: [{{ adapter: "wispr_api", error: "missing_key" }}, {{ adapter: "whisper_local", error: "empty" }}] }}),
  whisperUnavailable: whisperHeardNothing({{ tried: ["whisper_local"],
    errors: [{{ adapter: "whisper_local", error: "engine_unavailable" }}] }}),
  serverFalse: serverEngineReady({{ server_engine_ready: false }}, {{ stt: {{ wispr_api: true }} }}),
  serverFallback: serverEngineReady({{}}, {{ stt: {{ whisper_local: "ready" }} }}),
  network: speechErrorInfo("network"),
  service: speechErrorInfo("service-not-allowed"),
  invalid: speechErrorInfo("invalid-state"),
  language: speechErrorInfo("language-not-supported")
}};
console.log(JSON.stringify(out));
"""


def test_client_policy_never_starts_browser_speech_after_whisper_got_empty():
    node = shutil.which("node")
    if not node:
        pytest.skip("node is not installed")
    url = (ROOT / "apps/web/stt-policy.js").as_uri()
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, encoding="utf-8") as handle:
        handle.write(POLICY_SCRIPT.format(url=json.dumps(url)))
        path = handle.name
    try:
        output = subprocess.run(
            [node, path], capture_output=True, text=True, timeout=30, check=True
        ).stdout
    finally:
        Path(path).unlink(missing_ok=True)
    result = json.loads(output)

    assert result["ready"] is True
    assert result["loadingOnly"] is False
    assert result["cloud"] is True
    assert result["names"] == ["wispr_api", "whisper_local"]
    assert result["whisperEmpty"] is True
    assert result["whisperUnavailable"] is False
    assert result["serverFalse"] is False
    assert result["serverFallback"] is True
    assert result["network"] == {"code": "offline", "key": "stt_offline", "detail": "SpeechRecognition: network"}
    assert result["service"]["code"] == "service-not-allowed"
    assert result["invalid"]["code"] == "invalid-state"
    assert result["language"]["code"] == "language-not-supported"


def test_ui_contract_single_banner_and_no_double_mic_session():
    html = (ROOT / "apps/web/index.html").read_text(encoding="utf-8")
    script = (ROOT / "apps/web/app.js").read_text(encoding="utf-8")
    css = (ROOT / "apps/web/styles.css").read_text(encoding="utf-8")

    assert 'id="mic-error" class="mic-banner" role="alert"' in html
    assert 'id="mic-error-text"' in html
    assert 'id="mic-error-dismiss"' in html
    assert 'id="voice-diag"' in html and 'id="diag-list"' in html
    assert ".mic-banner" in css and "border-left: 6px solid" in css
    assert "mic-banner[data-tone=\"info\"]" in css

    assert "await releaseMicForRecognition()" in script
    assert script.index("async function releaseMicForRecognition") < script.index(
        "async function startWebSpeech"
    )
    assert "if (state.capture || state.bargeMonitor || state.recognition) return;" in script
    # The whisper-empty branch returns before any browser recognizer starts.
    empty_branch = script.index("if (noSpeech || serverEngineReady(result, state.health))")
    assert empty_branch < script.index("await startWebSpeech(message);", empty_branch)
    for error in (
        "service-not-allowed",
        "audio-capture",
        "language-not-supported",
        "aborted",
        "invalid-state",
    ):
        assert error in (ROOT / "apps/web/stt-policy.js").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def whisper_server():
    monkeypatch = pytest.MonkeyPatch()
    fake = WhisperLocalAdapter(model_factory=lambda size: FakeModel())
    original = stt_module.build_adapters

    def build():
        registry = original()
        registry["whisper_local"] = fake
        return registry

    monkeypatch.setattr(stt_module, "build_adapters", build)
    config = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        if server.started:
            break
        threading.Event().wait(0.1)
    if not server.started:
        pytest.fail("whisper server did not start")
    yield f"http://127.0.0.1:{PORT}"
    server.should_exit = True
    thread.join(timeout=5)
    monkeypatch.undo()


def test_fake_audio_reaches_whisper_and_shows_in_what_i_heard(playwright, whisper_server):
    assert FIXTURE.exists()
    browser = playwright.chromium.launch(
        args=[
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
            f"--use-file-for-fake-audio-capture={FIXTURE}",
            "--autoplay-policy=no-user-gesture-required",
        ]
    )
    context = browser.new_context()
    context.grant_permissions(["microphone"], origin=whisper_server)
    page = context.new_page()
    try:
        page.goto(whisper_server + "/")
        page.locator("#consent-yes").click()
        page.locator("#app").wait_for(state="visible")
        # Keep the barge-in monitor from opening its own stream during the test.
        page.locator("#barge-in").uncheck()
        page.locator("#mic").click()

        expect(page.locator("#heard")).to_contain_text("paanch hazaar", timeout=25000)
        expect(page.locator("#engine-badge")).to_have_text("Local voice", timeout=5000)
        assert page.locator("#mic-error").is_hidden()

        page.locator("#voice-diag summary").click()
        expect(page.locator("#diag-list")).to_contain_text("whisper_local", timeout=5000)
        expect(page.locator("#diag-list")).to_contain_text("len=37", timeout=5000)
    finally:
        context.close()
        browser.close()
