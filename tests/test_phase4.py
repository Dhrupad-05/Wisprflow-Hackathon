"""Phase 4 typed web application and live portal integration gates."""

import threading
from pathlib import Path

import pytest
import uvicorn
from playwright.sync_api import expect

from services.api.main import app


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def phase4_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=8766, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        if server.started:
            break
        threading.Event().wait(0.1)
    if not server.started:
        pytest.fail("phase 4 server did not start")
    yield "http://127.0.0.1:8766"
    server.should_exit = True
    thread.join(timeout=5)


def consent(page, base_url, language="en"):
    page.goto(base_url + "/")
    page.locator("#consent-lang").select_option(language)
    page.wait_for_timeout(100)
    page.locator("#consent-yes").click()
    page.locator("#app").wait_for(state="visible")


def say(page, text):
    page.locator("#text").fill(text)
    page.locator("#send").click()


def test_e1_bengali_typed_flow_fills_real_iframe_and_submits_after_yes(
    page, phase4_server
):
    page.set_viewport_size({"width": 390, "height": 844})
    consent(page, phase4_server, "bn")
    say(page, "Ami chashi amar loan lagbe")
    say(page, "SBI")
    say(page, "Na, taka jama dite chai")
    frame = page.frame_locator("#portal-frame")
    page.locator("#portal-frame").wait_for(state="visible")
    say(page, "one two three four five six seven eight nine zero one")
    page.locator("[data-command='yes']").click()
    expect(frame.locator("[data-field='account_no']")).to_have_value("12345678901")
    say(page, "paanch hazaar")
    page.locator("[data-command='yes']").click()
    expect(frame.locator("[data-field='amount']")).to_have_value("5000")
    page.locator("[data-command='no']").click()
    expect(page.locator("#prompt")).not_to_contain_text("Is anyone near", timeout=10000)
    expect(page.locator("#sensitive-done")).to_be_visible()
    frame.locator("[data-field='otp']").fill("123456")
    page.locator("#sensitive-done").click()
    expect(page.locator("#status")).to_have_text("CONFIRMING")
    assert frame.locator("[data-step='success']").is_hidden()
    page.locator("[data-command='yes']").click()
    expect(frame.locator("[data-step='success']")).to_be_visible()


@pytest.mark.parametrize("language", ["en", "hi", "bn"])
@pytest.mark.parametrize("viewport", [(390, 844), (1280, 800)])
def test_e2_i18n_responsive_screenshots_and_accessible_controls(
    page, phase4_server, language, viewport
):
    page.set_viewport_size({"width": viewport[0], "height": viewport[1]})
    consent(page, phase4_server, language)
    assert page.locator("#mic").get_attribute("aria-label")
    assert int(page.locator("#mic").bounding_box()["height"]) >= 56
    assert page.locator("#portal-frame").get_attribute("title") == "Demo portal"
    screenshot_dir = ROOT / "reports/screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    page.screenshot(
        path=str(screenshot_dir / f"phase4-{language}-{viewport[0]}.png"),
        full_page=True,
    )


def test_e3_routes_cancel_forget_and_digit_correction(page, phase4_server):
    consent(page, phase4_server)
    say(page, "deposit")
    say(page, "cancel")
    expect(page.locator("#status")).to_contain_text("CANCEL")
    page.locator("#wipe").click()
    page.locator("#consent-gate").wait_for(state="visible")
    consent(page, phase4_server)
    say(page, "deposit")
    say(page, "SBI")
    say(page, "one two three four five six seven eight nine zero one")
    say(page, "nahi")
    assert "account" in page.locator("#prompt").text_content().lower()
