"""Map a page's field schema to registry fields. Values are never accepted."""

from __future__ import annotations

import difflib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PORTALS = ROOT / "packages/registries/portals"


def _portals() -> list[dict]:
    return [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(PORTALS.glob("*.json"))
    ]


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9\u0900-\u097f\u0980-\u09ff]+", " ", str(value).lower()).strip()


def _score(field: dict, registry: dict) -> float:
    if _norm(field.get("id", "")) == _norm(registry["id"]):
        return 1.0
    names = [registry["id"], *registry.get("labels", {}).values()]
    return max(
        (
            1.0 if _norm(name) and _norm(name) in _norm(field.get("label", "")) else 0.0
            for name in names
        ),
        default=0.0,
    ) or difflib.SequenceMatcher(
        None, _norm(field.get("label", "")), _norm(registry.get("labels", {}).get("en", ""))
    ).ratio()


def _clean_fields(fields: list[dict]) -> list[dict]:
    """Keep only schema keys; drop any submitted value/label content that is not a string."""

    cleaned = []
    for field in fields[:200]:
        if not isinstance(field, dict):
            continue
        cleaned.append(
            {
                "id": str(field.get("id", ""))[:120],
                "label": str(field.get("label", ""))[:200],
                "type": str(field.get("type", "text"))[:40],
                "sensitive": bool(field.get("sensitive")),
                "options": [str(option)[:80] for option in (field.get("options") or [])][:20],
            }
        )
    return cleaned


def _llm_unmatched(unmatched: list[dict], registry: list[dict], client) -> dict[str, dict]:
    if not unmatched or not client:
        return {}
    catalog = [{"id": item["id"], "label": item.get("labels", {}).get("en", item["id"])} for item in registry]
    prompt = (
        "Match page field labels to registry field ids. Reply with strict JSON only: "
        '{"mapping": [{"field": "<page id>", "registry_id": "<id or null>"}]}. '
        "Never include values or URLs. "
        f"Registry: {json.dumps(catalog)} Page: {json.dumps([{'id': f['id'], 'label': f['label']} for f in unmatched])}"
    )
    try:
        text = client.complete(prompt)
        match = re.search(r"\{.*\}", text, flags=re.S)
        payload = json.loads(match.group()) if match else {}
    except Exception:  # noqa: BLE001 - provider failure uses the label fallback
        return {}
    valid_ids = {item["id"] for item in registry}
    page_ids = {field["id"] for field in unmatched}
    result = {}
    for item in payload.get("mapping", []):
        if (
            isinstance(item, dict)
            and item.get("field") in page_ids
            and item.get("registry_id") in valid_ids
        ):
            result[item["field"]] = {"registry_id": item["registry_id"]}
    return result


def map_page_fields(
    fields: list[dict],
    portal_id: str | None = None,
    language: str = "en",
    client=None,
) -> dict:
    """Return questions and sensitivity from the registry, never from page values."""

    cleaned = _clean_fields(fields)
    portal = next((item for item in _portals() if item["id"] == portal_id), None)
    registry = portal["fields"] if portal else []
    matched, unmatched = [], []
    for field in cleaned:
        best, score = None, 0.0
        for item in registry:
            candidate = _score(field, item)
            if candidate > score:
                best, score = item, candidate
        if best and score >= 0.72:
            matched.append((field, best))
        else:
            unmatched.append(field)
    llm = _llm_unmatched(unmatched, registry, client) if registry else {}
    mapping = []
    for field, item in matched:
        mapping.append(
            {
                "field": field["id"],
                "registry_id": item["id"],
                "label": item.get("labels", {}).get(language, item.get("labels", {}).get("en", item["id"])),
                "sensitive": bool(item.get("sensitive")) or field["sensitive"],
                "source": "registry",
            }
        )
    for field in unmatched:
        picked = llm.get(field["id"])
        item = next((entry for entry in registry if entry["id"] == (picked or {}).get("registry_id")), None)
        mapping.append(
            {
                "field": field["id"],
                "registry_id": item["id"] if item else None,
                "label": item.get("labels", {}).get(language, item.get("labels", {}).get("en", field["label"]))
                if item
                else field["label"],
                "sensitive": bool(item.get("sensitive")) if item else field["sensitive"],
                "source": "llm" if item else "label",
            }
        )
    return {
        "portal_id": portal["id"] if portal else None,
        "fields": mapping,
        "unmatched": [field["id"] for field in unmatched if field["id"] not in llm],
        "source": "registry" if not unmatched else ("llm" if llm else "label"),
    }
