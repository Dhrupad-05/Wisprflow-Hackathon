"""Phase 3 portal consistency and browser gates."""

import json
import threading
from html.parser import HTMLParser
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

from services.api.main import app

ROOT = Path(__file__).resolve().parents[1]
PORTAL_DIR = ROOT / "packages/registries/portals"
MOCK_DIR = ROOT / "apps/mock-portals"
PORTALS = {
    "sbi_deposit_mock": ("sbi-deposit.html", "/mock/sbi/deposit"),
    "kcc_loan_mock": ("kcc.html", "/mock/kcc"),
    "pension_mock": ("pension.html", "/mock/pension"),
    "ration_mock": ("ration.html", "/mock/ration"),
    "udyam_mock": ("udyam.html", "/mock/udyam"),
}


class FieldParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.fields = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if "data-field" in attributes:
            self.fields.append(attributes)


def load_portal(portal_id):
    for path in PORTAL_DIR.glob("*.json"):
        value = json.loads(path.read_text(encoding="utf-8"))
        if value["id"] == portal_id:
            return value
    raise AssertionError(f"missing registry {portal_id}")


def test_registry_and_html_fields_are_consistent():
    for portal_id, (filename, url) in PORTALS.items():
        registry = load_portal(portal_id)
        parser = FieldParser()
        parser.feed((MOCK_DIR / filename).read_text(encoding="utf-8"))
        page_fields = {field["data-field"] for field in parser.fields}
        registry_fields = {field["id"] for field in registry["fields"]}
        assert page_fields == registry_fields, portal_id
        for field in parser.fields:
            assert field["id"] == field["name"] == field["data-field"]
        sensitive = {
            field["id"] for field in registry["fields"] if field.get("sensitive")
        }
        for field in parser.fields:
            if field["data-field"] in sensitive:
                assert field.get("data-sensitive") == "true"
                assert field.get("autocomplete") == "one-time-code"


def test_mock_routes_and_bridge_are_served():
    client = TestClient(app)
    for _, (_, url) in PORTALS.items():
        response = client.get(url)
        assert response.status_code == 200
        assert "DEMO" in response.text
    bridge = client.get("/mock/portal-bridge.js")
    assert bridge.status_code == 200
    assert "event.origin === window.location.origin" in bridge.text
    assert "data-sensitive" in bridge.text


@pytest.fixture(scope="session")
def live_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=8765, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        if server.started:
            break
        threading.Event().wait(0.1)
    if not server.started:
        pytest.fail("demo server did not start")
    yield "http://127.0.0.1:8765"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.mark.parametrize("portal_id", list(PORTALS))
def test_portal_browser_flow(page, live_server, portal_id):
    filename, url = PORTALS[portal_id]
    registry = load_portal(portal_id)
    page.set_viewport_size({"width": 390, "height": 844})
    page.goto(live_server + url)
    for field in registry["fields"]:
        if not field.get("sensitive"):
            value = "12345678901" if field["type"] == "digits" else "5000"
            page.locator(f"[data-field='{field['id']}']").fill(value)
    page.locator("form[data-step='details'] button").click()
    page.locator("[data-step='review'] button").click()
    page.locator("[data-field='otp']").fill("123456")
    page.locator("form[data-step='otp'] button").click()
    assert page.locator("[data-step='success']").is_visible()
    screenshot_dir = ROOT / "reports/screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(screenshot_dir / f"{portal_id}-390.png"), full_page=True)
    page.set_viewport_size({"width": 1280, "height": 800})
    page.screenshot(path=str(screenshot_dir / f"{portal_id}-1280.png"), full_page=True)
