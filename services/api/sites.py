"""Registry-only site resolution and allow-list enforcement for OPEN_SITE."""

from __future__ import annotations

import difflib
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
REGISTRIES = ROOT / "packages/registries"
PORTALS = REGISTRIES / "portals"


def _load(name: str) -> list[dict]:
    return json.loads((REGISTRIES / name).read_text(encoding="utf-8"))


def _portal_files() -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(PORTALS.glob("*.json"))
    ]


def _records() -> list[dict]:
    """Flatten banks, schemes and portals into one registry of sites."""

    records: list[dict] = []
    for bank in _load("banks.json"):
        records.append(
            {
                "id": f"bank:{bank['id']}",
                "kind": "bank",
                "title": bank["name"],
                "service": None,
                "bank": bank["id"],
                "official_url": bank.get("official_url"),
                "allowed_domains": bank.get("allowed_domains", []),
                "mock_url": None,
                "login_required": bank.get("login_required", True),
                "fillable": False,
                "notes": bank.get("notes", ""),
            }
        )
    for scheme in _load("schemes.json"):
        records.append(
            {
                "id": f"scheme:{scheme['id']}",
                "kind": "scheme",
                "title": scheme["name"],
                "service": scheme["id"],
                "bank": None,
                "official_url": scheme.get("official_url"),
                "allowed_domains": scheme.get("allowed_domains", []),
                "mock_url": None,
                "login_required": scheme.get("login_required", True),
                "fillable": False,
                "notes": scheme.get("notes", ""),
            }
        )
    for portal in _portal_files():
        records.append(
            {
                "id": f"portal:{portal['id']}",
                "kind": "portal",
                "title": portal.get("title", portal["id"]).replace(" (DEMO)", ""),
                "service": portal.get("service"),
                "bank": portal.get("bank"),
                "official_url": portal.get("official_url"),
                "allowed_domains": portal.get("allowed_domains", []),
                "mock_url": portal.get("mock_url"),
                "login_required": portal.get("login_required", True),
                "fillable": portal.get("fillable", False),
                "notes": portal.get("notes", ""),
            }
        )
    return records


def is_allowed(url: str, domains: list[str]) -> bool:
    """Only absolute HTTPS URLs on an explicitly allowed host (or subdomain)."""

    if not url or not domains:
        return False
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def _uses_mock() -> bool:
    return os.getenv("DEMO_USE_MOCK", "false").strip().lower() in {"1", "true", "yes"}


def _site(record: dict) -> dict | None:
    mock = _uses_mock() and record.get("mock_url")
    url = record["mock_url"] if mock else record.get("official_url")
    if not url:
        return None
    if not mock and not is_allowed(url, record["allowed_domains"]):
        return None
    return {
        "id": record["id"].split(":", 1)[-1],
        "title": record["title"],
        "url": url,
        "official_url": record.get("official_url"),
        "allowed_domains": record["allowed_domains"],
        "login_required": bool(record.get("login_required")),
        "fillable": bool(record.get("fillable")),
        "mode": "fill" if mock else "guide",
        "notes": record.get("notes", ""),
    }


def _bank_record(bank: str | None) -> dict | None:
    if not bank:
        return None
    return next(
        (item for item in _records() if item["kind"] == "bank" and item["bank"] == bank),
        None,
    )


def _score(query: str, record: dict) -> float:
    return difflib.SequenceMatcher(
        None, query.lower(), f"{record['title']} {record['service'] or ''}".lower()
    ).ratio()


def site_options(query: str = "", limit: int = 3) -> list[dict]:
    """Up to ``limit`` registry sites the user can pick instead of guessing."""

    ranked = sorted(_records(), key=lambda item: _score(query, item), reverse=True)
    options = []
    for record in ranked:
        site = _site(record)
        if site:
            options.append(site)
        if len(options) >= limit:
            break
    return options


def pick_site_id(query: str, client=None) -> str | None:
    """Ask an LLM to choose an id; it can never invent a URL."""

    records = [item for item in _records() if _site(item)]
    if not records or not client:
        return None
    catalog = [
        {"id": item["id"], "title": item["title"], "kind": item["kind"]}
        for item in records
    ]
    prompt = (
        "Choose the single best site id for the user request from this registry. "
        "Reply with strict JSON only: {\"id\": \"<one of the ids>\"}. "
        "Never invent an id or a URL. If nothing matches, use null. "
        f"Registry: {json.dumps(catalog, ensure_ascii=False)} "
        f"Request: {query}"
    )
    try:
        text = client.complete(prompt)
        match = re.search(r"\{.*\}", text, flags=re.S)
        chosen = json.loads(match.group())["id"] if match else None
    except Exception:  # noqa: BLE001 - any provider/parse failure falls back
        return None
    if not isinstance(chosen, str) or chosen not in {item["id"] for item in records}:
        return None
    return chosen


def _choose(query: str, client=None) -> dict | None:
    chosen = pick_site_id(query, client) if client else None
    if chosen:
        record = next((item for item in _records() if item["id"] == chosen), None)
        site = _site(record) if record else None
        if site:
            return site
    return None


def resolve_site(
    service: str | None,
    bank: str | None = None,
    query: str = "",
    client=None,
    url_override: str | None = None,
) -> dict | None:
    """Registry exact -> bank -> fuzzy -> LLM(id only). URLs never come from prose."""

    records = _records()
    if url_override:
        domains = [record["allowed_domains"] for record in records if record.get("official_url") == url_override]
        if not is_allowed(url_override, domains[0] if domains else []):
            raise ValueError("url-not-allow-listed")
        record = next(
            (item for item in records if item.get("official_url") == url_override), None
        )
        if not record:
            raise ValueError("url-not-in-registry")
        return _site(record)

    # 1. Exact bank + service (a portal entry bound to the bank).
    for record in records:
        if (
            record["kind"] == "portal"
            and service
            and record["service"] == service
            and record["bank"] == bank
            and _site(record)
        ):
            return _site(record)
    # 2. Exact service (scheme or portal), plus bank fallback.
    for record in records:
        if (
            record["kind"] in {"portal", "scheme"}
            and service
            and record["service"] == service
            and record["bank"] in (None, bank)
            and _site(record)
        ):
            return _site(record)
    bank_record = _bank_record(bank)
    service_record = next(
        (item for item in records if item["service"] == service and item["kind"] == "portal"),
        None,
    )
    if bank_record and service_record and not service_record.get("official_url"):
        # Bank-specific service (loan/account/MSME): use the bank's official site.
        return _site(bank_record)
    if bank_record:
        return _site(bank_record)
    # 3. Fuzzy match on the spoken query.
    if query:
        ranked = sorted(records, key=lambda item: _score(query, item), reverse=True)
        if ranked and _score(query, ranked[0]) >= 0.6:
            site = _site(ranked[0])
            if site:
                return site
        # 4. LLM chooses an id from the registry, never a URL.
        site = _choose(query, client)
        if site:
            return site
    return None


def open_site_action(site: dict) -> dict:
    return {
        "type": "OPEN_SITE",
        "url": site["url"],
        "portal_id": site["id"],
        "mode": site["mode"],
        "title": site["title"],
    }
