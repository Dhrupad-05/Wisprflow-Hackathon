"""Phase 3 visual redesign: stepper, digit keypad, large choices, a11y contract."""

import threading
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient
from playwright.sync_api import expect

from services.api.dialog import progress
from services.api.main import app

ROOT = Path(__file__).resolve().parents[1]


def test_progress_is_registry_driven_across_the_journey():
    idle = progress({"state": "IDLE", "entities": {}, "filled_fields": {}})
    assert idle["step"] == 1
    assert idle["field"]["total"] == 0

    choosing_bank = progress(
        {"state": "NARROWING", "service": "deposit", "field_index": 0}
    )
    assert choosing_bank["step"] == 2
    assert choosing_bank["field"]["index"] == 0
    assert choosing_bank["field"]["type"] == "short"

    account = progress(
        {"state": "FORM_FILLING", "service": "deposit", "field_index": 0}
    )
    assert account["step"] == 2
    assert account["field"] == {"type": "digits", "sensitive": False, "index": 1, "total": 3}

    otp = progress(
        {"state": "FORM_FILLING", "service": "deposit", "field_index": 2}
    )
    assert otp["field"]["sensitive"] is True
    assert otp["field"]["index"] == 3

    confirm = progress(
        {"state": "CONFIRMING_FIELD", "service": "deposit", "field_index": 1}
    )
    assert confirm["step"] == 3
    assert progress({"state": "SUBMITTED", "service": "deposit"})["step"] == 4


def test_turn_response_carries_field_and_progress_metadata():
    client = TestClient(app)
    started = client.post("/v1/session", json={"lang_hint": "en"}).json()
    assert started["progress"]["step"] == 1
    sid = started["session_id"]

    first = client.post("/v1/turn", json={"session_id": sid, "transcript": "deposit"}).json()
    assert first["progress"]["step"] == 2
    assert first["progress"]["field"]["index"] == 0
    assert first["progress"]["state"] == "NARROWING"

    second = client.post("/v1/turn", json={"session_id": sid, "transcript": "SBI"}).json()
    field = second["progress"]["field"]
    assert field["type"] == "digits"
    assert field["sensitive"] is False
    assert field["index"] == 1
    assert field["total"] == 3
    assert second["field_type"] == "digits"


def test_redesign_contract_in_served_ui():
    html = (ROOT / "apps/web/index.html").read_text(encoding="utf-8")
    css = (ROOT / "apps/web/styles.css").read_text(encoding="utf-8")
    script = (ROOT / "apps/web/app.js").read_text(encoding="utf-8")

    assert 'id="stepper"' in html
    assert 'id="step-note"' in html
    assert 'aria-label="Progress"' in html
    assert 'id="digit-pad"' in html
    assert 'id="quick-replies"' in html
    assert 'aria-label="Start voice input"' in html
    assert 'aria-live="polite"' in html
    assert 'title="Demo portal"' in html

    assert "button{min-height:56px}" in css
    assert ".chip{min-height:56px}" in css
    assert ".step.current" in css
    assert ".choice-yes" in css
    assert ".digit" in css
    assert "prefers-reduced-motion" in css
    assert ":focus-visible" in css

    assert "renderProgress" in script
    assert "renderDigitPad" in script
    assert "choiceButton" in script
    assert 'aria-current' in script


@pytest.fixture(scope="module")
def redesign_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=8770, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        if server.started:
            break
        threading.Event().wait(0.1)
    if not server.started:
        pytest.fail("redesign server did not start")
    yield "http://127.0.0.1:8770"
    server.should_exit = True
    thread.join(timeout=5)


def say(page, text):
    page.locator("#text").fill(text)
    page.locator("#send").click()


def test_stepper_keypad_and_choices_drive_the_flow(page, redesign_server):
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(redesign_server + "/")
    page.locator("#consent-yes").click()
    page.locator("#app").wait_for(state="visible")

    assert page.locator("#stepper li").count() == 4
    expect(page.locator("#stepper .step.current .step-dot")).to_have_text("1")
    expect(page.locator("#step-note")).to_contain_text("Step 1 of 4")

    say(page, "deposit")
    expect(page.locator("#stepper .step.current .step-dot")).to_have_text("2")
    assert page.locator("#digit-pad").is_hidden()

    say(page, "SBI")
    page.locator("#digit-pad").wait_for(state="visible")
    expect(page.locator("#step-note")).to_contain_text("Field 1 of 3")
    page.locator("[data-digit='4']").click()
    page.locator("[data-digit='2']").click()
    assert page.locator("#text").input_value() == "42"
    page.locator(".digit-clear").click()
    assert page.locator("#text").input_value() == ""

    page.locator("#text").fill("12345678901")
    page.locator("#send").click()
    expect(page.locator(".choice[data-command='yes']")).to_be_visible()
    expect(page.locator(".choice[data-command='no']")).to_be_visible()
    expect(page.locator("#stepper .step.current .step-dot")).to_have_text("3")
    assert int(page.locator(".choice[data-command='yes']").bounding_box()["height"]) >= 56
    assert page.locator("#digit-pad").is_hidden()

    no_overflow = page.evaluate(
        "() => document.documentElement.scrollWidth <= window.innerWidth + 1"
    )
    assert no_overflow is True


def test_dark_mode_and_language_switch_keep_the_stepper_localized(page, redesign_server):
    page.goto(redesign_server + "/")
    page.locator("#consent-yes").click()
    page.locator("#app").wait_for(state="visible")
    page.locator("#lang").select_option("hi")
    expect(page.locator("#stepper .step").first).to_contain_text("काम चुनें")
    page.emulate_media(color_scheme="dark")
    background = page.evaluate(
        "() => getComputedStyle(document.body).backgroundColor"
    )
    assert background not in {"rgb(243, 246, 251)", "rgba(0, 0, 0, 0)"}
