"""Generate the extension host allow-list from portal registries."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REGISTRIES = ROOT / "packages/registries/portals"
OUTPUT = ROOT / "apps/extension/allowlist.js"


def main():
    hosts = sorted({host for path in REGISTRIES.glob("*.json") for host in json.loads(path.read_text(encoding="utf-8")).get("domains_allowed", [])})
    OUTPUT.write_text("globalThis.ALLOWED_HOSTS = " + json.dumps(hosts) + ";\n", encoding="utf-8")
    print(f"Generated {OUTPUT}: {len(hosts)} allowed hosts")


if __name__ == "__main__":
    main()
