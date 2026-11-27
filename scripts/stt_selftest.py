#!/usr/bin/env python
"""Send a short bundled WAV through /v1/stt and print what came back.

Usage:
    python scripts/stt_selftest.py
    python scripts/stt_selftest.py --url http://127.0.0.1:8000 --language hi
    python scripts/stt_selftest.py --audio path/to/recording.wav
"""

from __future__ import annotations

import argparse
import base64
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIO = ROOT / "tests/fixtures/hello_hi.wav"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--audio", default=str(DEFAULT_AUDIO))
    parser.add_argument("--language", default="hi")
    parser.add_argument(
        "--context",
        default="SBI,Kisan Credit Card,Udyam,PM-KISAN",
        help="Comma-separated dictionary context for the adapter",
    )
    args = parser.parse_args()

    audio_path = Path(args.audio)
    if not audio_path.exists():
        print(f"audio not found: {audio_path}")
        return 2
    payload = {
        "audio": base64.b64encode(audio_path.read_bytes()).decode(),
        "language": args.language,
        "dictionary_context": [item for item in args.context.split(",") if item],
    }
    request = urllib.request.Request(
        args.url.rstrip("/") + "/v1/stt",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        print(f"HTTP {error.code}: {error.read().decode()[:500]}")
        return 1
    except urllib.error.URLError as error:
        print(f"could not reach {args.url}: {error.reason}")
        return 1

    elapsed = int((time.perf_counter() - started) * 1000)
    print(
        json.dumps(
            {
                "adapter": body.get("adapter"),
                "error_code": body.get("error_code"),
                "text": body.get("text"),
                "latency_ms": body.get("latency_ms", elapsed),
                "round_trip_ms": elapsed,
                "tried": body.get("tried"),
                "errors": body.get("errors"),
                "server_engine_ready": body.get("server_engine_ready"),
                "whisper": body.get("whisper"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if body.get("text") else 1


if __name__ == "__main__":
    raise SystemExit(main())
