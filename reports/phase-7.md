# Phase 7 — LLM routing and evaluation

## Delivered

- Provider-neutral `LLMClient` protocol with Anthropic Messages and OpenAI-compatible HTTP clients.
- Strict `RouteDecision` Pydantic validation (`extra="forbid"`), one retry for invalid JSON, 1.5-second provider timeout, and deterministic fallback.
- Injection-resistant routing prompt: the utterance is explicitly treated as data, never as instructions.
- Multilingual JSONL fixture with 224 rows across English, Hindi, Bengali, and code-mixed speech, with fixed dev/test splits.
- Evaluator reports: `eval-test.json`, `eval-test.md`, and `eval-test-confusion.csv`.

## Results

The held-out test split contains 112 rows. Exact route accuracy is **91.96%**, and named-entity accuracy is **100%** across 9 named-entity rows. The dev split is retained separately at 84.82%; router tuning was performed against dev before the held-out test run.

No LLM API key was configured, so the production route used the deterministic keyword fallback. Live provider behavior remains unverified by design.

## Verification

- `ruff check .` — passed
- `pytest -q` — 194 passed, 2 warnings
