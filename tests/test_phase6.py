"""Phase 6 unpacked MV3 extension and DOM safety gates."""

import json
import threading
from pathlib import Path

import pytest
import uvicorn

from services.api.main import app


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "apps/extension"


@pytest.fixture(scope="session")
def phase6_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=8768, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(50):
        if server.started:
            break
        threading.Event().wait(0.1)
    if not server.started:
        pytest.fail("phase 6 server did not start")
    yield "http://127.0.0.1:8768"
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="function")
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


def post_message(page, message):
    return page.evaluate(
        """
        message => new Promise((resolve, reject) => {
          const listener = event => {
            if (event.data?.source === 'bolo-sahayak-extension') {
              window.removeEventListener('message', listener);
              resolve(event.data);
            }
          };
          window.addEventListener('message', listener);
          window.postMessage(message, location.origin);
          setTimeout(() => reject(new Error('extension relay timeout')), 5000);
        })
        """,
        {"source": "bolo-sahayak", **message},
    )


def test_extension_manifest_is_mv3_and_registry_allowlist_is_generated():
    manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == 3
    assert manifest["background"]["service_worker"] == "background.js"
    assert "allowlist.js" in manifest["content_scripts"][0]["js"]
    assert "127.0.0.1" in (EXTENSION / "allowlist.js").read_text(encoding="utf-8")


def test_allowed_origin_fills_non_sensitive_field_and_refuses_otp(
    extension_context, phase6_server
):
    page = extension_context.new_page()
    page.goto(phase6_server + "/mock/sbi/deposit")
    page.wait_for_timeout(500)
    response = post_message(page, {"type": "FILL_FIELD", "field": "account_no", "value": "12345678901", "sensitive": False})
    assert response["ok"] is True
    assert response["filled"] is True
    page.wait_for_timeout(100)
    refused = post_message(page, {"type": "FILL_FIELD", "field": "otp", "value": "123456", "sensitive": False})
    assert refused == {"source": "bolo-sahayak-extension", "ok": False, "reason": "sensitive-field-refused"}
    assert page.locator("[data-field='otp']").input_value() == ""


def test_unlisted_origin_has_no_content_script(extension_context):
    page = extension_context.new_page()
    page.goto("data:text/html,<input id='account_no'>")
    page.locator("#account_no").fill("")
    page.evaluate("window.postMessage({source:'bolo-sahayak',type:'FILL_FIELD',field:'account_no',value:'secret'}, '*')")
    page.wait_for_timeout(100)
    assert page.locator("#account_no").input_value() == ""
