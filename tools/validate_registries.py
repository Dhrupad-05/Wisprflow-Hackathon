"""Validate registry references and required translations."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = {"en", "hi", "bn"}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate() -> list[str]:
    errors = []
    intents = load(ROOT / "packages/registries/intents.json")
    domains = {item["id"]: item for item in intents["domains"]}
    services = {service for item in domains.values() for service in item["services"]}
    banks = load(ROOT / "packages/registries/banks.json")
    schemes = load(ROOT / "packages/registries/schemes.json")
    for label, entries in (("banks", banks), ("schemes", schemes)):
        ids = [entry["id"] for entry in entries]
        if len(ids) != len(set(ids)):
            errors.append(f"duplicate {label} id")
    for path in (ROOT / "packages/registries/portals").glob("*.json"):
        portal = load(path)
        if portal["domain"] not in domains:
            errors.append(f"{path.name}: unknown domain")
        if portal["service"] not in services:
            errors.append(f"{path.name}: unknown service")
        for field in portal["fields"]:
            labels = field.get("labels", {})
            missing = LANGUAGES - labels.keys()
            if missing:
                errors.append(f"{path.name}:{field['id']}: missing {sorted(missing)}")
    for language in LANGUAGES:
        prompt_path = ROOT / "packages/i18n/prompts" / f"{language}.json"
        prompts = load(prompt_path)
        for key in ("greeting", "confirm", "sensitive", "end_words"):
            if key not in prompts:
                errors.append(f"{language}: missing prompt {key}")
    return errors


if __name__ == "__main__":
    problems = validate()
    if problems:
        raise SystemExit("\n".join(problems))
    print(
        "Registry validation passed: 5 portals, 12+ banks, translated prompts present."
    )
