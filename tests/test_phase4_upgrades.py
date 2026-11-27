"""Phase 4 upgrades: tap choices, digit correction, language lockstep, retry, helper sheet, PWA."""

import json
import struct
import threading
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient
from playwright.sync_api import expect

from services.api.dialog import choices
from services.api.main import app, sessions

ROOT = Path(__file__).resolve().parents[1]
client = TestClient(app)


def start(lang="en"):
    return client.post("/v1/session", json={"lang_hint": lang}).json()


def turn(sid, text, trigger="typed"):
    response = client.post(
        "/v1/turn",
        json={"session_id": sid, "transcript": text, "trigger": trigger},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_narrowing_choices_come_from_the_bank_registry_and_are_tappable():
    banks = json.loads((ROOT / "packages/registries/banks.json").read_text(encoding="utf-8"))
    session = start()
    assert session["choices"] == []

    first = turn(session["session_id"], "deposit")
    assert first["state"] == "NARROWING"
    assert [option["id"] for option in first["choices"]] == [bank["id"] for bank in banks]
    assert all(option["type"] == "bank" for option in first["choices"])
    assert any(option["label"] == "Punjab National Bank" for option in first["choices"])

    # A chip tap sends its label exactly like speech would.
    second = turn(session["session_id"], "Punjab National Bank")
    assert second["state"] == "FORM_FILLING"
    assert second["actions"][0]["type"] == "OPEN_PORTAL"
    assert second["choices"] == []


def test_choices_only_exist_while_narrowing():
    assert choices({"state": "FORM_FILLING"}) == []
    assert choices({"state": "CONFIRMING"}) == []
    assert choices({"state": "SUBMITTED"}) == []


def test_dictating_a_corrected_number_replaces_the_pending_value():
    sid = start()["session_id"]
    turn(sid, "deposit")
    turn(sid, "SBI")
    first = turn(sid, "one two three four five six seven eight nine zero one")
    assert first["state"] == "CONFIRMING_FIELD"
    assert first["readback"] == "1 2 3 4 5 6 7 8 9 0 1"

    fixed = turn(sid, "four five six seven eight nine zero one two three four")
    assert fixed["state"] == "CONFIRMING_FIELD"
    assert fixed["readback"] == "4 5 6 7 8 9 0 1 2 3 4"
    assert fixed["prompt_text"].startswith("I heard")
    assert sessions[sid]["filled_fields"] == {}

    accepted = turn(sid, "haan")
    assert accepted["state"] == "FORM_FILLING"
    assert sessions[sid]["filled_fields"]["account_no"] == "45678901234"
    assert accepted["readback"] is None


def test_no_still_rejects_the_heard_number_and_amount_correction_parses():
    sid = start()["session_id"]
    turn(sid, "deposit")
    turn(sid, "SBI")
    turn(sid, "one two three four five six seven eight nine zero one")
    rejected = turn(sid, "nahi")
    assert rejected["state"] == "FORM_FILLING"
    assert sessions[sid]["filled_fields"] == {}

    turn(sid, "one two three four five six seven eight nine zero one")
    turn(sid, "haan")
    amount = turn(sid, "paanch hazaar")
    assert amount["readback"] == "₹5,000"
    corrected = turn(sid, "सात हज़ार")
    assert corrected["readback"] == "₹7,000"
    assert corrected["state"] == "CONFIRMING_FIELD"


def test_helper_sheet_lists_localized_labels_and_never_values():
    sid = start("hi")["session_id"]
    turn(sid, "जमा")
    turn(sid, "SBI")
    turn(sid, "one two three four five six seven eight nine zero one")
    turn(sid, "haan")

    response = client.get(f"/v1/session/{sid}/helper")
    assert response.status_code == 200
    sheet = response.json()
    assert [step["label"] for step in sheet["steps"]] == ["खाता नंबर", "राशि", "ओटीपी"]
    assert sheet["steps"][0]["filled"] is True
    assert sheet["steps"][2]["sensitive"] is True
    assert sheet["step"] == 2
    text = json.dumps(sheet, ensure_ascii=False)
    assert "12345678901" not in text
    assert "1 2 3 4 5" not in text

    assert client.get("/v1/session/missing/helper").status_code == 404


def test_pwa_manifest_icons_and_worker_are_served():
    manifest = client.get("/manifest.webmanifest")
    assert manifest.status_code == 200
    data = json.loads(manifest.text)
    assert data["start_url"] == "/"
    assert data["display"] == "standalone"
    assert {icon["sizes"] for icon in data["icons"]} == {"192x192", "512x512"}

    worker = client.get("/sw.js")
    assert worker.status_code == 200
    assert "/v1/" in worker.text
    assert "caches.match" in worker.text

    for size in (192, 512):
        icon = client.get(f"/icons/icon-{size}.png")
        assert icon.status_code == 200
        body = icon.content
        assert body[:8] == b"\x89PNG\r\n\x1a\n"
        assert struct.unpack(">II", body[16:24]) == (size, size)
    assert client.get("/icons/icon-64.png").status_code == 404


def test_csp_allows_the_service_worker_and_manifest():
    csp = client.get("/healthz").headers["content-security-policy"]
    assert "worker-src 'self'" in csp
    assert "manifest-src 'self'" in csp


def test_ui_contract_for_the_upgrades():
    html = (ROOT / "apps/web/index.html").read_text(encoding="utf-8")
    script = (ROOT / "apps/web/app.js").read_text(encoding="utf-8")
    css = (ROOT / "apps/web/styles.css").read_text(encoding="utf-8")

    assert 'rel="manifest"' in html
    for element in ('id="retry"', 'id="helper"', 'id="answer-hint"', 'id="lang-note"'):
        assert element in html
    for token in (
        "switchLanguage",
        "prompt_lang",
        "state.choices",
        "editAnswer",
        "fix_digits",
        "lastText",
        "printHelper",
        "serviceWorker",
    ):
        assert token in script
    assert ".chips.banks" in css
    assert "button{min-height:56px}" in css


@pytest.fixture(scope="module")
def upgrade_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=8771, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        if server.started:
            break
        threading.Event().wait(0.1)
    if not server.started:
        pytest.fail("upgrade server did not start")
    yield "http://127.0.0.1:8771"
    server.should_exit = True
    thread.join(timeout=5)


def test_bank_chip_and_digit_fix_in_the_browser(page, upgrade_server):
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(upgrade_server + "/")
    page.locator("#consent-yes").click()
    page.locator("#app").wait_for(state="visible")

    page.locator("#text").fill("deposit")
    page.locator("#send").click()
    expect(page.locator("#answer-hint")).to_contain_text("Tap your bank")

    chip = page.locator("#quick-replies .chip", has_text="State Bank of India")
    expect(chip).to_be_visible()
    chip.click()
    expect(page.locator("#portal-frame")).to_be_visible()
    expect(page.locator("#digit-pad")).to_be_visible()

    page.locator("#text").fill("12345678901")
    page.locator("#send").click()
    fix = page.locator("[data-command='edit']")
    expect(fix).to_be_visible()
    fix.click()
    assert page.locator("#text").input_value() == "12345678901"

    page.locator("#text").fill("45678901234")
    page.locator("#send").click()
    expect(page.locator("#prompt")).to_contain_text("4 5 6 7 8 9 0 1 2 3 4")
