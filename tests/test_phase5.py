"""Phase 5 endpointing, STT adapter, and microphone browser gates."""

import asyncio
import base64
import threading

import httpx
import pytest
import uvicorn

from services.api.main import app
from services.api.stt import STTRequest, STTError, XaiSttAdapter, transcribe


@pytest.fixture(scope="session")
def phase5_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=8767, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        if server.started:
            break
        threading.Event().wait(0.1)
    if not server.started:
        pytest.fail("phase 5 server did not start")
    yield "http://127.0.0.1:8767"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def browser_type_launch_args():
    return {"args": ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"]}


def audio_request():
    return STTRequest(audio=base64.b64encode(b"RIFF" + b"0" * 100).decode(), language="bn")


def run_async(coro):
    result = []
    error = []

    def runner():
        try:
            result.append(asyncio.run(coro))
        except BaseException as exc:  # pragma: no cover - test transport helper
            error.append(exc)

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join()
    if error:
        raise error[0]
    return result[0]


def test_stt_xai_success_and_multipart_request():
    seen = {}

    async def handler(request):
        seen["content_type"] = request.headers["content-type"]
        seen["body"] = request.content
        return httpx.Response(200, json={"text": "পাঁচ হাজার", "detected_language": "bn"})

    async def run():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = XaiSttAdapter(api_key="secret", api_url="https://xai.test/v1/stt", client=client)
        result = await adapter.transcribe(audio_request())
        await client.aclose()
        return result

    result = run_async(run())
    assert result["text"] == "পাঁচ হাজার"
    assert b'name="model"' in seen["body"]
    assert b'name="file"' in seen["body"]


@pytest.mark.parametrize(
    ("status", "expected"), [(401, "unauthorized"), (413, "too_large"), (422, "unsupported_language")]
)
def test_stt_errors_are_normalized(status, expected):
    async def handler(_request):
        return httpx.Response(status)

    async def run():
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter = XaiSttAdapter(api_key="secret", client=client)
        with pytest.raises(STTError) as error:
            await adapter.transcribe(audio_request())
        await client.aclose()
        return error.value.code

    assert run_async(run()) == expected


def test_stt_missing_key_falls_through_to_text(monkeypatch):
    monkeypatch.setenv("STT_ORDER", "xai_stt,text")
    monkeypatch.delenv("XAI_STT_API_KEY", raising=False)
    result = run_async(transcribe(audio_request()))
    assert result["adapter"] == "text"
    assert result["demo_mode"] is True


def test_endpointing_fake_clock_covers_thresholds(page, phase5_server):
    page.goto(phase5_server + "/")
    result = page.evaluate(
        """
        async () => {
          const { EndpointingEngine } = await import('/packages/voice/endpointing.js');
          let now = 1; const timers = []; const ended = [];
          const engine = new EndpointingEngine({
            clock: () => now,
            setTimer: (fn, ms) => { timers.push({fn, ms}); return timers.length - 1; },
            clearTimer: () => {}, onEnd: (value) => ended.push(value)
          });
          engine.begin({fieldType: 'amount'}); engine.update('paanch hazaar');
          const amountWait = timers.at(-1).ms;
          engine.update('paanch hazaar aur'); const connectorWait = timers.at(-1).ms;
          engine.begin({fieldType: 'digits'}); engine.update('one two');
          const digitWait = timers.at(-1).ms;
          engine.begin({fieldType: 'short'}); engine.update('haan'); timers.at(-1).fn();
          engine.begin({fieldType: 'short', language: 'hi'}); engine.update('ho gaya');
          return {amountWait, connectorWait, digitWait, ended: ended.map(item => item.reason)};
        }
        """
    )
    assert result == {"amountWait": 2500, "connectorWait": 3750, "digitWait": 3000, "ended": ["pause", "end_word"]}


def test_endpointing_slow_mode_and_low_confidence_reask(page, phase5_server):
    page.goto(phase5_server + "/")
    result = page.evaluate(
        """
        async () => {
          const { EndpointingEngine } = await import('/packages/voice/endpointing.js');
          const timers = []; const reasks = [];
          const engine = new EndpointingEngine({slow: true, setTimer: (fn, ms) => { timers.push(ms); return 1; }, clearTimer: () => {}, onReask: value => reasks.push(value)});
          engine.begin({fieldType: 'short'}); engine.update('yes', 0.1);
          engine.update('yes');
          return {wait: timers.at(-1), reasks: reasks.length};
        }
        """
    )
    assert result == {"wait": 1800, "reasks": 1}


def test_fake_microphone_reaches_stt_proxy(page, phase5_server):
    page.context.grant_permissions(["microphone"], origin=phase5_server)
    page.goto(phase5_server + "/")
    page.locator("#consent-yes").click()
    page.locator("#mic").click()
    page.wait_for_timeout(3200)
    assert "speech" in page.locator("#status").text_content().lower()
