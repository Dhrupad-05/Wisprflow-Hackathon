"""Registry-only site resolution and allow-list gates."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from services.api import sites
from services.api.main import app

client = TestClient(app)
ROOT = Path(__file__).resolve().parents[1]


class FakeClient:
    def __init__(self, response):
        self.response = response

    def complete(self, _prompt):
        return self.response


def start(lang="en"):
    return client.post("/v1/session", json={"lang_hint": lang}).json()["session_id"]


def turn(session_id, text):
    response = client.post("/v1/turn", json={"session_id": session_id, "transcript": text})
    assert response.status_code == 200, response.text
    return response.json()


def test_every_official_url_is_https_and_on_its_own_allow_list():
    for record in sites._records():
        if record.get("official_url"):
            assert sites.is_allowed(record["official_url"], record["allowed_domains"]), record


def test_unverifiable_gramin_and_kcc_are_todo_not_guesses():
    banks = json.loads((ROOT / "packages/registries/banks.json").read_text(encoding="utf-8"))
    gramin = next(bank for bank in banks if bank["id"] == "grameen")
    assert gramin["official_url"] is None and "TODO" in gramin["notes"]
    kcc = json.loads((ROOT / "packages/registries/portals/kcc.json").read_text(encoding="utf-8"))
    assert kcc["official_url"] is None and "TODO" in kcc["notes"]


def test_bank_service_uses_bank_registry_url():
    site = sites.resolve_site("loan", "sbi")
    assert site["url"] == "https://sbi.bank.in"
    assert site["mode"] == "guide"
    assert sites.resolve_site("deposit", "pnb")["url"] == "https://pnb.bank.in"


def test_scheme_uses_scheme_registry_url():
    assert sites.resolve_site("pm_kisan")["url"] == "https://pmkisan.gov.in"
    assert sites.resolve_site("udyam")["url"] == "https://udyamregistration.gov.in"
    assert sites.resolve_site("widow_pension")["url"] == "https://nsap.dord.gov.in"


def test_non_allow_listed_overrides_are_refused():
    with pytest.raises(ValueError):
        sites.resolve_site("loan", "sbi", url_override="https://evil.example/login")
    with pytest.raises(ValueError):
        sites.resolve_site("loan", "sbi", url_override="http://sbi.bank.in")
    with pytest.raises(ValueError):
        sites.resolve_site("loan", "sbi", url_override="https://sbi.bank.in.evil.example")


def test_llm_may_only_pick_a_registry_id_never_a_url():
    picked = sites.resolve_site(
        "cooperative bank", query="cooperative bank", client=FakeClient('{"id": "bank:pnb"}')
    )
    assert picked["url"] == "https://pnb.bank.in"
    invented = sites.resolve_site(
        "cooperative bank",
        query="cooperative bank",
        client=FakeClient('{"id": "https://evil.example"}'),
    )
    assert invented is None
    url_field = sites.resolve_site(
        "cooperative bank",
        query="cooperative bank",
        client=FakeClient('{"url": "https://evil.example"}'),
    )
    assert url_field is None


def test_unknown_site_offers_at_most_three_registry_options():
    options = sites.site_options("completely unknown portal", 3)
    assert 1 <= len(options) <= 3
    assert all(option["url"].startswith("https://") for option in options)


def test_yes_after_intent_confirmation_returns_registry_open_site_action():
    session_id = start("en")
    first = turn(session_id, "I need to borrow 50,000 from my SBI account")
    assert first["state"] == "CONFIRMING_INTENT"
    opened = turn(session_id, "yes")
    action = next(item for item in opened["actions"] if item["type"] == "OPEN_SITE")
    assert action["url"] == "https://sbi.bank.in"
    assert action["portal_id"] == "bank:sbi" or action["portal_id"] == "sbi"
    assert action["mode"] == "guide"


def test_demo_use_mock_returns_registry_mock_url(monkeypatch):
    monkeypatch.setenv("DEMO_USE_MOCK", "true")
    site = sites.resolve_site("deposit", "sbi")
    assert site["url"] == "/mock/sbi/deposit"
    assert site["mode"] == "fill"


def test_extension_allowlist_contains_registry_domains():
    source = (ROOT / "apps/extension/allowlist.js").read_text(encoding="utf-8")
    assert "sbi.bank.in" in source
    assert "pmkisan.gov.in" in source
    assert "udyamregistration.gov.in" in source
