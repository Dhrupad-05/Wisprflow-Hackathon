"""Generate the extension host allow-list from every registry."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRIES = ROOT / "packages/registries"
OUTPUT = ROOT / "apps/extension/allowlist.js"


def main():
    domains = {"127.0.0.1", "localhost"}
    files = [REGISTRIES / "banks.json", REGISTRIES / "schemes.json", *sorted((REGISTRIES / "portals").glob("*.json"))]
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        for entry in data if isinstance(data, list) else [data]:
            domains.update(entry.get("allowed_domains", []))
            for key in ("domains_allowed",):
                domains.update(entry.get(key, []))
    output = (
        "globalThis.ALLOWED_HOSTS = " + json.dumps(sorted(domains)) + ";\n"
        "globalThis.ALLOWED_DOMAINS = " + json.dumps(sorted(domains - {"127.0.0.1", "localhost"})) + ";\n"
    )
    OUTPUT.write_text(output, encoding="utf-8")
    print(f"Generated {OUTPUT}: {len(domains)} allowed hosts")


if __name__ == "__main__":
    main()
