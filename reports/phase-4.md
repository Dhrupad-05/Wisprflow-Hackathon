# PHASE 4 REPORT

Built:

- Replaced the prototype client with a typed-input web assistant and consent/language gate.
- Added responsive assistant-plus-portal layout, quick replies, touch-sized controls, private mode, slow speaker toggle, voice fallback notice, forget-everything, and a readable masked-log print view.
- Added i18n JSON loading for English, Hindi, and Bengali UI strings.
- Added real same-origin iframe action execution: open portal, fill non-sensitive fields, move to OTP, focus sensitive input, show masked summary, and submit only after final confirmation.
- Fixed the portal bridge to trust the parent window source and serialized frontend turns to prevent rapid-click races.

Gate results:

| Check | Exact command | Result | Evidence |
|---|---|---|---|
| Ruff | `ruff check . --fix` | PASS | `All checks passed!` |
| Phase 4 browser gate | `pytest -q tests/test_phase4.py` | PASS | `8 passed, 2 warnings`; Bengali typed E1 reached real iframe success only after final yes. |
| Full regression | `pytest -q` | PASS | `178 passed, 2 warnings` |
| Screenshot review | `reports/screenshots/phase4-{en,hi,bn}-{390,1280}.png` | PASS | Six responsive language screenshots generated and visually reviewed. |

Notes:

- Browser voice input remains a single-result convenience path; endpointing/STT work is intentionally deferred to Phase 5.
- No real bank or government site is contacted; all portal actions target the local demo portals.
- Missing Bengali/Hindi browser voices are reported once while text remains prominent.

Next: Phase 5. Reply `continue`.
