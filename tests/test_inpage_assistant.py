"""In-page bubble: schema scanning, typed voice pipeline, sensitive refusal."""

import threading
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient
from playwright.sync_api import expect

from services.api.main import app

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "apps/extension"
client = TestClient(app)


@pytest.fixture(scope="session")
def bubble_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=8776, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        if server.started:
            break
        threading.Event().wait(0.1)
    if not server.started:
        pytest.fail("bubble server did not start")
    yield "http://127.0.0.1:8776"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture()
def extension_context(browser_type, tmp_path):
    context = browser_type.launch_persistent_context(
        str(tmp_path / "profile"),
        headless=False,
        args=[
            f"--disable-extensions-except={EXTENSION}",
            f"--load-extension={EXTENSION}",
            "--headless=new",
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
        ],
    )
    yield context
    context.close()


def open_bubble(page):
    page.locator("#bolo-bubble-host").locator("#bubble").click()
    expect(page.locator("#bolo-bubble-host").locator("#panel")).to_be_visible()


def bolo_say(page, text):
    page.locator("#bolo-bubble-host").locator("#typed").fill(text)
    page.locator("#bolo-bubble-host").locator("#send").click()


def drive_to_amount(session_id):
    def turn(text):
        return client.post("/v1/turn", json={"session_id": session_id, "transcript": text}).json()

    turn("deposit")
    turn("SBI")
    turn("one two three four five six seven eight nine zero one")
    assert turn("haan")["state"] == "FORM_FILLING"


def test_scan_reports_labels_types_and_sensitive_without_values(extension_context, bubble_server):
    page = extension_context.new_page()
    page.goto(bubble_server + "/mock/fixture/fields")
    expect(page.locator("#bolo-bubble-host").locator("#fields")).to_contain_text("5 fields")
    expect(page.locator("#bolo-bubble-host").locator("#fields")).to_contain_text("2 sensitive")
    open_bubble(page)
    expect(page.locator("#bolo-bubble-host").locator("#prompt")).to_be_visible()
    assert "secret123" not in page.locator("#bolo-bubble-host").inner_text()


def test_spa_field_change_is_rescanned(extension_context, bubble_server):
    page = extension_context.new_page()
    page.goto(bubble_server + "/mock/fixture/fields")
    expect(page.locator("#bolo-bubble-host").locator("#fields")).to_contain_text("5 fields")
    page.evaluate(
        """
        () => {
          const input = document.createElement('input');
          input.id = 'extra_input';
          input.name = 'extra_input';
          input.setAttribute('aria-label', 'Extra field');
          document.getElementById('extra').appendChild(input);
        }
        """
    )
    expect(page.locator("#bolo-bubble-host").locator("#fields")).to_contain_text("6 fields")


def test_shared_session_fills_non_sensitive_field_and_never_otp(extension_context, bubble_server):
    session_id = client.post("/v1/session", json={"lang_hint": "en"}).json()["session_id"]
    drive_to_amount(session_id)
    page = extension_context.new_page()
    page.goto(bubble_server + "/mock/sbi/deposit")
    page.evaluate(
        "sid => window.postMessage({source: 'bolo-sahayak', type: 'SESSION', session_id: sid}, location.origin)",
        session_id,
    )
    open_bubble(page)
    bolo_say(page, "paanch hazaar")
    expect(page.locator("#bolo-bubble-host").locator("#prompt")).to_contain_text("Amount")
    bolo_say(page, "yes")
    expect(page.locator("#amount")).to_have_value("5000")
    expect(page.locator("#bolo-bubble-host").locator("#prompt")).to_contain_text("OTP")
    assert page.locator("#otp").input_value() == ""
    bolo_say(page, "123456")
    page.wait_for_timeout(400)
    assert page.locator("#otp").input_value() == ""
