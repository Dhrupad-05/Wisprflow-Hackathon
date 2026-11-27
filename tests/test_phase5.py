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


def wait_until(page, predicate, timeout_ms=8000):
    for _ in range(max(1, timeout_ms // 200)):
        if predicate():
            return True
        page.wait_for_timeout(200)
    return predicate()


def test_fake_microphone_opens_capture_and_reports_a_reason(playwright, phase5_server):
    # Launch a dedicated browser so the fake media device is guaranteed on
    # (the session-wide browser may already be running without the flag).
    browser = playwright.chromium.launch(
        args=["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"]
    )
    context = browser.new_context()
    context.grant_permissions(["microphone"], origin=phase5_server)
    page = context.new_page()
    try:
        page.goto(phase5_server + "/")
        page.locator("#consent-yes").click()
        page.locator("#app").wait_for(state="visible")
        page.locator("#mic").click()

        def level():
            return int(page.locator("#meter").get_attribute("aria-valuenow") or 0)

        def settled():
            return page.locator("#status").text_content().strip().lower()

        assert wait_until(page, lambda: level() > 0, timeout_ms=15000), "level meter never moved"
        assert "listening" in page.locator("#mic-label").text_content().lower()
        page.locator("#mic").click()

        def has_reason():
            return page.locator("#mic-error").text_content().strip() != ""

        def stopped_thinking():
            return settled() and not any(word in settled() for word in ("thinking", "processing"))

        assert wait_until(page, has_reason, timeout_ms=25000) or wait_until(
            page, stopped_thinking, timeout_ms=5000
        ), "no engine reason and no settled state"
        status = page.locator("#status").text_content().strip()
        assert status and status != "No speech heard; type below."
        assert page.locator("#text").is_enabled()
        assert page.locator("#engine-badge").text_content().strip()
    finally:
        context.close()
        browser.close()
