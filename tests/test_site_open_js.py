"""Node checks for the OPEN_SITE fallback helper."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_site_open_helpers():
    script = """
import { absoluteSiteUrl, needsOpenSiteFallback } from './apps/web/site-open.js';
const assert = (value, message) => { if (!value) { console.error(message); process.exit(1); } };
assert(absoluteSiteUrl('/mock/sbi/deposit', 'http://127.0.0.1:8000') === 'http://127.0.0.1:8000/mock/sbi/deposit', 'relative');
assert(absoluteSiteUrl('https://sbi.bank.in', 'http://127.0.0.1:8000') === 'https://sbi.bank.in/', 'https');
assert(absoluteSiteUrl('javascript:alert(1)', 'http://127.0.0.1:8000') === '', 'javascript blocked');
assert(absoluteSiteUrl('http://evil.example', 'http://127.0.0.1:8000') === '', 'cross-origin http blocked');
assert(needsOpenSiteFallback(null, null) === true, 'no ack and no popup');
assert(needsOpenSiteFallback({ ok: true }, null) === false, 'extension ack');
assert(needsOpenSiteFallback({ ok: false }, {}) === false, 'popup opened');
console.log('site-open ok');
"""
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "site-open ok" in result.stdout
