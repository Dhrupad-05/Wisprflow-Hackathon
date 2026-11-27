"""End-to-end: after yes, the extension opens the registry URL in a new tab."""

import threading
from pathlib import Path

import pytest
import uvicorn
from playwright.sync_api import expect

from services.api.main import app

ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "apps/extension"


@pytest.fixture(scope="session")
def site_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=8775, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        if server.started:
            break
        threading.Event().wait(0.1)
    if not server.started:
        pytest.fail("open-site server did not start")
    yield "http://127.0.0.1:8775"
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
        ],
    )
    yield context
    context.close()


def test_yes_opens_registry_url_in_a_new_tab(extension_context, site_server):
    page = extension_context.new_page()
    page.goto(site_server + "/")
    page.locator("#consent-yes").click()
    page.locator("#text").fill("I need to borrow 50,000 from my SBI account")
    page.locator("#send").click()
    expect(page.locator("#prompt")).to_contain_text("50,000")
    page.locator("#text").fill("yes")
    page.locator("#send").click()
    expect(page.locator("#status")).to_have_text("PORTAL_OPEN")
    opened = None
    for _ in range(50):
        opened = next((tab for tab in extension_context.pages if "sbi.bank.in" in (tab.url or "")), None)
        if opened:
            break
        page.wait_for_timeout(100)
    assert opened is not None, [tab.url for tab in extension_context.pages]
    assert opened.url.startswith("https://sbi.bank.in")
    opened.close()
