# Phase 0 defect audit

The requested zip was not present in the supplied locations. The observations below are therefore marked `OBSERVED`, `NOT REPRODUCED (no zip)`, or `FIXED IN PHASE 0`.

| ID | Result | Evidence / reproduction |
|---|---|---|
| D1 | OBSERVED | `apps/mock-portals/` is absent; no mock HTML portal service exists in the tree. |
| D2 | OBSERVED | `services/api/dialog.py` contains the current narrow prototype flow; no registry-driven form engine is present. |
| D3 | NOT REPRODUCED (no zip) | The supplied prior-build transcript was unavailable; digit confirmation is not covered by the six current tests. |
| D4 | OBSERVED | Current source has no bank-offer state or three-option bank-selection flow. |
| D5 | OBSERVED | `services/api/router.py` is keyword-only and there is no `LLMClient`; the current prototype has no documented low-confidence gate. |
| D6 | OBSERVED | Current session entities are top-level and the form flow has no explicit re-route policy. |
| D7 | OBSERVED | Whole-word command matching is not present in the current entity/dialog implementation. |
| D8 | OBSERVED | No explicit transition table or illegal-transition exception is present in the current dialog implementation. |
| D9 | OBSERVED | Current `parse_amount` is not the required multilingual parser and has no Phase 1 corpus. |
| D10 | OBSERVED | `apps/web/app.js` has no endpointing thresholds, slow mode, or pause read-back implementation. |
| D11 | OBSERVED | Current `/v1/stt` is explicitly a typed demo response; live Wispr REST calls are not implemented. |
| D12 | OBSERVED | Current UI contains hard-coded strings and no consent/privacy checkpoint flow. |
| D13 | OBSERVED | `apps/extension` has static files, but no verified connected background/side-panel protocol or DOM sensitivity enforcement. |
| D14 | FIXED IN PHASE 0 | Compose previously required `.env` and exposed a separate nginx service; compose now uses one API service and optional `.env`. |
| D15 | OBSERVED | `pytest -q` produced `6 passed`; no Playwright, accessibility, safety, or screenshot gates exist yet. |
| D16 | OBSERVED | Several original modules used compressed statements; `services/api/main.py` was expanded and formatted in this phase. |

## Salvage or rewrite

| File / area | Decision | Reason |
|---|---|---|
| `services/api/dialog.py` | Rewrite in Phase 2 | Prototype is not an explicit state machine. |
| `services/api/router.py` | Rewrite in Phase 2 | Needs confidence, clarification, and registry-driven routing. |
| `apps/web/app.js` | Rewrite in Phase 4 | Needs ES modules, endpointing, actions, and portal bridge. |
| `apps/extension/content.js` | Rewrite in Phase 5 | Needs origin, DOM, and sensitive-field enforcement. |
| `packages/registries/*.json` | Salvage as starting data | Registry concept and identifiers are useful, but Phase 1 validation is still required. |
| `services/api/entities.py` | Salvage selectively | Redaction instinct is useful; parsers require Phase 1 replacement and tests. |
| `apps/web/index.html`, `styles.css` | Salvage scaffold | Existing DEMO MODE shell is suitable for Phase 0 and will be expanded later. |
